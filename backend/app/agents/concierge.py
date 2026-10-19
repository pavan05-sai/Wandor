import json
from typing import Any, Dict, List, Tuple
from app.agents.base import BaseAgent
from app.core.logging import get_logger
from app.schemas.chat import ConciergeReply
from app.schemas.itinerary import CanonicalItinerary
from app.tools.registry import ToolRegistry

logger = get_logger("concierge_agent")


class ConciergeAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Concierge", prompt_file="concierge.txt")

    def chat(
        self,
        message: str,
        itinerary: CanonicalItinerary,
        chat_history: List[Dict[str, str]],
        tool_registry: ToolRegistry
    ) -> Tuple[ConciergeReply, List[str]]:
        tools = tool_registry.get_tool_for_agent("concierge")
        trace: List[str] = [f"Concierge processing user message: {message!r}"]

        # Build rich context for grounded answers
        days_summary = []
        for day in itinerary.days:
            days_summary.append({
                "day": day.day_number,
                "date": day.date,
                "theme": day.theme,
                "weather": {
                    "summary": day.weather.summary if day.weather else "Unknown",
                    "rain_prob_pct": day.weather.rain_prob_pct if day.weather else 0,
                } if day.weather else None,
                "items": [
                    {
                        "id": it.id,
                        "name": it.name,
                        "type": it.type,
                        "category": it.category,
                        "start_time": it.start_time,
                        "end_time": it.end_time,
                        "cost_inr": it.cost.amount if it.cost else 0,
                        "indoor": it.indoor,
                        "locked": it.locked,
                        "reason": it.reason,
                        "reason_factors": it.reason_factors,
                    }
                    for it in day.items
                ]
            })

        budget_info = {
            "total_limit_inr": itinerary.budget.total_limit,
            "estimated_total_inr": itinerary.budget.estimated_total,
            "remaining_inr": itinerary.budget.remaining,
            "status": itinerary.budget.status,
            "per_day_inr": itinerary.budget.per_day,
            "per_person_inr": itinerary.budget.per_person,
        }

        accommodation_info = {
            "name": itinerary.accommodation.name,
            "nightly_cost_inr": itinerary.accommodation.nightly_cost,
            "nights": itinerary.accommodation.nights,
            "reason": itinerary.accommodation.reason,
        }

        prompt = f"""
Trip Context:
- Title: {itinerary.trip.title}
- Destination: {itinerary.trip.destination.name}, {itinerary.trip.destination.country}
- Dates: {itinerary.trip.start_date} to {itinerary.trip.end_date} ({itinerary.trip.num_days} days)
- Travelers: {itinerary.trip.travelers.adults} adults, {itinerary.trip.travelers.children} children
- User Preferences: Pace={itinerary.preferences.pace}, Interests={itinerary.preferences.interests}, Dietary={itinerary.preferences.dietary}

Accommodation: {json.dumps(accommodation_info, indent=2)}

Budget: {json.dumps(budget_info, indent=2)}

Itinerary (Day-by-Day):
{json.dumps(days_summary, indent=2)}

Recent Conversation History (last 6 messages):
{json.dumps(chat_history[-6:], indent=2)}

User Message: {message!r}

Classify the user intent and produce a grounded JSON response. Ground ALL factual claims in the above context only.
"""

        result_json, agent_trace = self.run_tool_loop(prompt, tools)
        trace.extend(agent_trace)

        try:
            reply = ConciergeReply(**result_json)
            trace.append(f"Classified intent: {reply.intent!r}")
            return reply, trace
        except Exception as e:
            logger.warning(f"Error parsing concierge response: {e}. Using safe fallback.")
            # Deterministic fallback based on keywords — never claims to have done anything
            msg_lower = message.lower()
            if any(k in msg_lower for k in ["cheaper", "remove", "add", "change", "replace", "swap", "move", "budget", "modify"]):
                return ConciergeReply(
                    text="I understand you want to adjust your itinerary. Could you clarify exactly which day or activity you would like to change?",
                    intent="clarify",
                    instruction=None
                ), trace
            return ConciergeReply(
                text="I am your AI travel concierge. I can answer questions about your trip, explain activity selections, or help you modify your itinerary. What would you like to know?",
                intent="answer",
                instruction=None
            ), trace
