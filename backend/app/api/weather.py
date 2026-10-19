from typing import Any
from fastapi import APIRouter, Depends
from app.api.dependencies import get_owned_trip
from app.core.errors import NotFoundError
from app.models.database import get_db
from app.orchestrator.orchestrator import Orchestrator
from app.repositories.base import EntityDoc
from app.repositories.versions import VersionRepository
from app.schemas.common import success_response
from app.schemas.itinerary import CanonicalItinerary
from app.schemas.shares import EventSimulateRequest
from app.services.catalog import CatalogService
from app.services.weather import WeatherService

router = APIRouter(prefix="/trips/{trip_id}", tags=["Weather & Events"])


@router.get("/weather")
def get_trip_weather(
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    version_repo = VersionRepository(db)
    v = version_repo.get_latest(trip.id)
    if v and v.json:
        it = CanonicalItinerary(**v.json)
        days_weather = [{"day_number": d.day_number, "date": d.date, **d.weather.model_dump()} for d in it.days]
        provenance = it.provenance.weather if it.provenance else "demo"
        return success_response({"forecast": days_weather, "provenance": provenance})

    dest = CatalogService.get_destination_by_id(trip.destination_id, db=db)
    lat = dest.lat if dest else 15.49
    lng = dest.lng if dest else 73.82
    forecast = WeatherService.get_forecast(db, trip.destination_id, lat, lng, trip.num_days)
    return success_response({
        "forecast": [f.model_dump() for f in forecast],
        "provenance": forecast[0].source if forecast else "demo"
    })


@router.post("/events/check")
def check_events(
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    events, replan_it = Orchestrator.check_conditions_and_replan(db, trip.id)
    return success_response({
        "events_detected": len(events),
        "events": events,
        "itinerary": replan_it.model_dump() if replan_it else None
    })


@router.post("/events/simulate")
def simulate_event(
    sim_req: EventSimulateRequest,
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    event_dict, replan_it = Orchestrator.simulate_event(
        db=db,
        trip_id=trip.id,
        event_type=sim_req.type,
        day_id=sim_req.day_id,
        severity=sim_req.severity,
        detail=sim_req.detail or f"Simulated {sim_req.type} alert"
    )
    return success_response({
        "event": event_dict,
        "simulated_event": event_dict,
        "itinerary": replan_it.model_dump() if replan_it else None
    })
