from typing import Any, Callable, Dict, List, Optional
from app.repositories.places import PlaceRepository
from app.schemas.itinerary import CanonicalItinerary, Travelers
from app.services.routing import RoutingService
from app.services.weather import WeatherService
from app.workers.budget import BudgetEngine
from app.workers.candidates import CandidateRetriever


class ToolRegistry:
    def __init__(self, db: Any = None, itinerary: Optional[CanonicalItinerary] = None, destination_id: str = "dest_goa"):
        self.db = db
        self.itinerary = itinerary
        self.destination_id = destination_id
        self.place_repo = PlaceRepository(db)

    def get_candidates(
        self,
        kind: Optional[str] = None,
        category: Optional[str] = None,
        indoor: Optional[bool] = None,
        max_cost: Optional[int] = None,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        places = self.place_repo.list_by_destination(self.destination_id)
        prefs = self.itinerary.preferences if self.itinerary else None
        results = CandidateRetriever.retrieve(
            places=places,
            kind=kind,
            preferences=prefs,
            category=category,
            indoor=indoor,
            max_cost=max_cost,
            limit=limit
        )
        return [r.model_dump() for r in results]

    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        p = self.place_repo.get_by_id(place_id)
        if p:
            return {
                "id": p.id,
                "name": p.name,
                "kind": p.kind,
                "category": p.category,
                "lat": p.lat,
                "lng": p.lng,
                "cost_amount": p.cost_amount,
                "duration_min": p.duration_min,
                "open_from": p.open_from,
                "open_to": p.open_to,
                "closed_days": p.closed_days,
                "indoor": p.indoor,
                "rating": p.rating,
                "description": p.description,
                "booking_url": p.booking_url
            }
        return None

    def get_weather(self, day_id: Optional[str] = None) -> List[Dict[str, Any]]:
        lat, lng = 15.4909, 73.8278
        if self.itinerary:
            lat = self.itinerary.trip.destination.lat
            lng = self.itinerary.trip.destination.lng
            num_days = self.itinerary.trip.num_days
        else:
            num_days = 4

        forecast = WeatherService.get_forecast(self.db, self.destination_id, lat, lng, num_days)
        return [f.model_dump() for f in forecast]

    def estimate_costs(self, place_ids: List[str]) -> Dict[str, Any]:
        places = [self.place_repo.get_by_id(pid) for pid in place_ids if self.place_repo.get_by_id(pid)]
        total = sum(p.cost_amount for p in places if p)
        return {
            "num_places": len(places),
            "estimated_item_cost": total,
            "places": [{"id": p.id, "name": p.name, "cost": p.cost_amount} for p in places if p]
        }

    def get_day_summary(self, day_id: str) -> Optional[Dict[str, Any]]:
        if not self.itinerary:
            return None
        for day in self.itinerary.days:
            if day.id == day_id:
                return {
                    "day_id": day.id,
                    "day_number": day.day_number,
                    "date": day.date,
                    "theme": day.theme,
                    "items": [{"id": i.id, "name": i.name, "start": i.start_time, "end": i.end_time, "cost": i.cost.amount, "locked": i.locked} for i in day.items],
                    "totals": day.totals.model_dump()
                }
        return None

    def explain_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        if not self.itinerary:
            return None
        for day in self.itinerary.days:
            for item in day.items:
                if item.id == item_id:
                    return {
                        "id": item.id,
                        "name": item.name,
                        "category": item.category,
                        "reason": item.reason,
                        "reason_factors": item.reason_factors,
                        "alternatives": item.alt_ids
                    }
        return None

    def estimate_travel_time(self, place_id_a: str, place_id_b: str, mode: str = "taxi") -> Dict[str, Any]:
        p_a = self.place_repo.get_by_id(place_id_a)
        p_b = self.place_repo.get_by_id(place_id_b)
        if not p_a or not p_b:
            return {"error": "Place not found"}
        return RoutingService.calculate_leg(self.db, p_a.lat, p_a.lng, p_b.lat, p_b.lng, mode)

    def get_tool_for_agent(self, agent_name: str) -> Dict[str, Callable]:
        all_tools = {
            "get_candidates": self.get_candidates,
            "get_place_details": self.get_place_details,
            "get_weather": self.get_weather,
            "estimate_costs": self.estimate_costs,
            "get_day_summary": self.get_day_summary,
            "explain_item": self.explain_item,
            "estimate_travel_time": self.estimate_travel_time
        }

        allowlists = {
            "planner": ["get_candidates", "get_weather", "get_place_details", "estimate_costs", "estimate_travel_time"],
            "replanner": ["get_candidates", "get_weather", "get_place_details", "estimate_costs", "get_day_summary", "estimate_travel_time"],
            "concierge": ["get_day_summary", "get_place_details", "get_weather", "explain_item"]
        }

        allowed_keys = allowlists.get(agent_name.lower(), [])
        return {k: all_tools[k] for k in allowed_keys if k in all_tools}
