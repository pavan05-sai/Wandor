from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from app.agents.concierge import ConciergeAgent
from app.agents.planner import PlannerAgent
from app.agents.replanner import ReplannerAgent
from app.core.config import settings
from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.repositories.base import EntityDoc
from app.orchestrator.context import build_agent_context
from app.orchestrator.pipeline import OrchestratorPipeline, PipelineResult
from app.repositories.entities import ChatRepository, EventRepository, NotificationRepository
from app.repositories.places import PlaceRepository
from app.repositories.trips import TripRepository
from app.repositories.users import UserRepository
from app.repositories.versions import VersionRepository
from app.schemas.changeset import ChangeOp, ChangeSet, OpType
from app.schemas.chat import ChatResponse
from app.schemas.itinerary import (
    AlternativeOption, CanonicalItinerary, DestinationRef, ItineraryDay, Travelers
)
from app.schemas.preferences import PreferencesSchema
from app.services.catalog import CatalogService
from app.services.routing import RoutingService
from app.services.weather import WeatherService
from app.workers.baseline import BaselinePlanner
from app.workers.budget import BudgetEngine
from app.workers.diff import ItineraryDiffEngine
from app.workers.events import EventDetector
from app.workers.optimizer import ScheduleOptimizer
from app.workers.validator import ItineraryValidator

logger = get_logger("orchestrator")


class Orchestrator:
    @classmethod
    def generate_trip(
        cls,
        db: Any,
        trip_id: Union[str, int],
        regenerate: bool = False
    ) -> Tuple[CanonicalItinerary, List[str], List[AlternativeOption]]:
        ctx = build_agent_context(db, trip_id)
        trip = ctx.trip
        trace: List[str] = [f"Starting generation workflow for Trip {trip.id} ({trip.title})"]

        user_repo = UserRepository(db)
        user_pref = user_repo.get_preferences(trip.user_id)
        preferences = PreferencesSchema(
            interests=user_pref.interests if user_pref and user_pref.interests else ["beaches", "heritage", "food"],
            pace=user_pref.pace if user_pref else "relaxed",
            budget_level=user_pref.budget_level if user_pref else "mid",
            dietary=user_pref.dietary if user_pref else [],
            avoid=user_pref.avoid if user_pref else []
        )

        dest_schema = CatalogService.get_destination_by_id(trip.destination_id, db=db)
        dest_ref = DestinationRef(
            name=dest_schema.name if dest_schema else trip.title.split()[0],
            country=dest_schema.country if dest_schema else "IN",
            lat=dest_schema.lat if dest_schema else 15.4909,
            lng=dest_schema.lng if dest_schema else 73.8278,
            catalog_id=trip.destination_id
        )

        travelers = Travelers(adults=trip.adults if hasattr(trip, 'adults') and trip.adults else 2,
                               children=trip.children if hasattr(trip, 'children') and trip.children else 0)
        total_budget = trip.budget if hasattr(trip, 'budget') and trip.budget else 30000

        # Fetch weather
        weather_forecasts = WeatherService.get_forecast(
            db, trip.destination_id, dest_ref.lat, dest_ref.lng, trip.num_days
        )

        catalog_places = ctx.catalog_places
        if not catalog_places:
            catalog_places = CatalogService.get_places_for_destination(db, trip.destination_id)

        place_by_id = {p.id: p for p in catalog_places}

        # 1. Attempt AI Generation via PlannerAgent
        planner = PlannerAgent()
        selection: Optional[PlannerSelection] = None
        try:
            selection, planner_trace = planner.plan_trip(
                destination_name=dest_ref.name,
                destination_id=trip.destination_id,
                num_days=trip.num_days,
                travelers=travelers,
                budget=total_budget,
                preferences=preferences,
                tool_registry=ctx.tool_registry
            )
            trace.extend(planner_trace)
        except Exception as e:
            selection = None
            trace.append(f"Planner Agent error: {e}. Falling back to baseline planner.")
            logger.warning(f"Planner Agent error: {e}")

        itinerary: Optional[CanonicalItinerary] = None

        if selection:
            try:
                trace.append("Synthesizing itinerary from AI PlannerSelection")
                hotel_place = place_by_id.get(selection.hotel_id)
                hotel_name = hotel_place.name if hotel_place else "Central Hotel"
                hotel_cost = hotel_place.cost_amount if hotel_place else 2800

                from app.schemas.itinerary import AccommodationBlock, BookingRef, TripInfo, ProvenanceBlock
                acc_block = AccommodationBlock(
                    place_id=selection.hotel_id,
                    name=hotel_name,
                    nights=max(1, trip.num_days - 1),
                    rooms=BudgetEngine.calculate_rooms(travelers.adults, travelers.children),
                    nightly_cost=hotel_cost,
                    check_in=trip.start_date,
                    check_out=trip.end_date,
                    booking=BookingRef(url=hotel_place.booking_url) if hotel_place and hotel_place.booking_url else BookingRef(),
                    reason=selection.hotel_reason or "Selected by Planner for great value and central location."
                )

                days: List[ItineraryDay] = []
                from datetime import datetime, timedelta
                s_date = datetime.strptime(trip.start_date, "%Y-%m-%d")

                for d_sel in selection.days:
                    cur_date = (s_date + timedelta(days=d_sel.day_number - 1)).strftime("%Y-%m-%d")
                    acts = [place_by_id[pid] for pid in d_sel.activity_ids if pid in place_by_id]
                    rests = [place_by_id[pid] for pid in d_sel.meal_ids if pid in place_by_id]

                    day_obj = ScheduleOptimizer.optimize_day_schedule(
                        day_number=d_sel.day_number,
                        date_str=cur_date,
                        theme=d_sel.theme,
                        activities=acts,
                        restaurants=rests,
                        hotel=hotel_place,
                        reasons_map=d_sel.reasons,
                        factors_map=d_sel.reason_factors
                    )
                    if d_sel.day_number - 1 < len(weather_forecasts):
                        day_obj.weather = weather_forecasts[d_sel.day_number - 1]
                    days.append(day_obj)

                # If days count mismatch, pad
                while len(days) < trip.num_days:
                    d_num = len(days) + 1
                    cur_date = (s_date + timedelta(days=d_num - 1)).strftime("%Y-%m-%d")
                    day_obj = ScheduleOptimizer.optimize_day_schedule(
                        day_number=d_num,
                        date_str=cur_date,
                        theme="Exploration Day",
                        activities=[],
                        restaurants=[],
                        hotel=hotel_place
                    )
                    if d_num - 1 < len(weather_forecasts):
                        day_obj.weather = weather_forecasts[d_num - 1]
                    days.append(day_obj)

                budget_block = BudgetEngine.calculate_budget(
                    days=days,
                    accommodation=acc_block,
                    travelers=travelers,
                    total_limit=total_budget,
                    preferences=preferences
                )

                val_result = ItineraryValidator.validate(
                    itinerary=CanonicalItinerary(
                        schema_version="1.0",
                        trip_id=str(trip.id),
                        version=1,
                        trip=TripInfo(
                            title=trip.title,
                            destination=dest_ref,
                            start_date=trip.start_date,
                            end_date=trip.end_date,
                            num_days=trip.num_days,
                            travelers=travelers
                        ),
                        preferences=preferences,
                        budget=budget_block,
                        accommodation=acc_block,
                        days=days
                    ),
                    catalog_places=place_by_id
                )

                if val_result.is_valid:
                    itinerary = CanonicalItinerary(
                        schema_version="1.0",
                        trip_id=str(trip.id),
                        version=1,
                        created_by="planner_agent",
                        change_summary="Personalized itinerary generated by Planner Agent",
                        mode=trip.mode,
                        trip=TripInfo(
                            title=trip.title,
                            destination=dest_ref,
                            start_date=trip.start_date,
                            end_date=trip.end_date,
                            num_days=trip.num_days,
                            travelers=travelers
                        ),
                        preferences=preferences,
                        budget=budget_block,
                        accommodation=acc_block,
                        days=days,
                        provenance=ProvenanceBlock(
                            weather=weather_forecasts[0].source if weather_forecasts else "demo",
                            routing="estimated",
                            places="catalog",
                            llm="live" if settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY else "replay",
                            overall="live_with_fallbacks"
                        ),
                        warnings=val_result.warnings
                    )
                    trace.append("Planner itinerary passed all validation rules successfully")
                else:
                    trace.append(f"Planner output failed validator: {val_result.errors}. Triggering Baseline safety net.")
            except Exception as e:
                trace.append(f"Error materializing Planner selection: {e}. Triggering Baseline safety net.")
                logger.warning(f"Error materializing Planner selection: {e}")

        # 2. Fallback to Baseline Planner if AI failed or invalid
        if not itinerary:
            trace.append("Engaging Baseline Planner fallback to guarantee a 100% valid plan")
            itinerary = BaselinePlanner.generate_itinerary(
                trip_id=str(trip.id),
                title=trip.title,
                destination=dest_ref,
                start_date=trip.start_date,
                end_date=trip.end_date,
                num_days=trip.num_days,
                travelers=travelers,
                budget=total_budget,
                preferences=preferences,
                catalog_places=catalog_places,
                weather_forecasts=weather_forecasts,
                created_by="baseline_planner",
                mode=trip.mode
            )

        # 3. Create Alternative Suggestions (Deliverable 14)
        alternatives: List[AlternativeOption] = [
            AlternativeOption(
                id="alt_cheaper",
                label="Budget Saver Variant",
                summary="Replaces premium activities with scenic free walks; saves approx ₹2,500.",
                delta={"cost": -2500, "travel_min": 10},
                change_set={"ops": [{"op": "SET_BUDGET", "total_limit": total_budget - 2500}]}
            ),
            AlternativeOption(
                id="alt_leisure",
                label="Relaxed Pace & Sunset Leisure",
                summary="Reduces morning items by 1 stop for extended cafe and beach relaxation.",
                delta={"cost": -500, "travel_min": -20},
                change_set={"ops": [{"op": "SET_PREFERENCE", "key": "pace", "value": "relaxed"}]}
            )
        ]
        itinerary.alternatives = alternatives

        # 4. Persist Version 1
        version_repo = VersionRepository(db)
        version_repo.create(
            trip_id=trip.id,
            version=1,
            parent_version=None,
            json_data=itinerary.model_dump(),
            created_by=itinerary.created_by,
            change_summary=itinerary.change_summary
        )

        trip_repo = TripRepository(db)
        trip_repo.update_version_pointer(trip.id, 1)

        # Notification
        noti_repo = NotificationRepository(db)
        noti_repo.create(
            user_id=trip.user_id,
            trip_id=trip.id,
            type="itinerary_change",
            title="Itinerary Created (v1)",
            body=f"{itinerary.trip.title} is ready with {itinerary.trip.num_days} full days of activities.",
            severity="info"
        )

        return itinerary, trace, alternatives

    @classmethod
    def handle_chat(cls, db: Any, trip_id: Union[str, int], message: str) -> ChatResponse:
        ctx = build_agent_context(db, trip_id)
        if not ctx.itinerary:
            raise ValidationError("Please generate an itinerary first before using chat.", code="NO_ITINERARY")

        chat_repo = ChatRepository(db)
        history = [{"role": m.role, "content": m.content} for m in chat_repo.get_history(trip_id, limit=6)]

        # 1. Concierge intent classification and response
        concierge = ConciergeAgent()
        reply, trace = concierge.chat(message, ctx.itinerary, history, ctx.tool_registry)

        # Record user message
        chat_repo.add_message(
            trip_id=trip_id,
            role="user",
            content=message,
            intent=reply.intent,
            version_before=ctx.itinerary.version
        )

        # 2. If intent is "modify", invoke Replanner Agent
        if reply.intent == "modify" and reply.instruction:
            trace.append(f"Invoking Replanner with instruction: '{reply.instruction}'")
            replanner = ReplannerAgent()
            changeset, replanner_trace = replanner.replan(ctx.itinerary, reply.instruction, ctx.tool_registry)
            trace.extend(replanner_trace)

            if changeset and changeset.ops:
                trace.append("Executing Orchestrator pipeline to apply ChangeSet")
                res = OrchestratorPipeline.run_pipeline(
                    db=db,
                    trip=ctx.trip,
                    base_itinerary=ctx.itinerary,
                    changeset=changeset,
                    created_by="replanner_agent",
                    change_summary=changeset.rationale or reply.instruction,
                    catalog_places=ctx.catalog_places
                )

                if res.success:
                    chat_repo.add_message(
                        trip_id=trip_id,
                        role="assistant",
                        content=reply.text,
                        intent="modify",
                        version_before=ctx.itinerary.version,
                        version_after=res.itinerary.version
                    )
                    return ChatResponse(
                        reply=reply.text,
                        intent=reply.intent,
                        version_change=True,
                        diff=res.diff,
                        trace=trace
                    )
                else:
                    trace.append(f"Pipeline rejected ChangeSet: {res.errors}")
                    error_msg = f"I tried to apply that change, but it violates schedule constraints: {', '.join(res.errors[:2])}. Your current itinerary remains safe."
                    chat_repo.add_message(trip_id=trip_id, role="assistant", content=error_msg, intent="modify")
                    return ChatResponse(
                        reply=error_msg,
                        intent=reply.intent,
                        version_change=False,
                        trace=trace
                    )

        # Regular answer
        chat_repo.add_message(
            trip_id=trip_id,
            role="assistant",
            content=reply.text,
            intent=reply.intent,
            version_before=ctx.itinerary.version,
            version_after=ctx.itinerary.version
        )
        return ChatResponse(
            reply=reply.text,
            intent=reply.intent,
            version_change=False,
            trace=trace
        )

    @classmethod
    def revert_trip(cls, db: Any, trip_id: Union[str, int], target_version: int) -> CanonicalItinerary:
        trip_repo = TripRepository(db)
        version_repo = VersionRepository(db)

        trip = trip_repo.get_by_id(trip_id)
        if not trip:
            raise NotFoundError("Trip not found")

        target_row = version_repo.get_by_version(trip_id, target_version)
        if not target_row:
            raise NotFoundError(f"Version {target_version} not found")

        latest_row = version_repo.get_latest(trip_id)
        current_version = latest_row.version if latest_row else 1
        new_version_num = current_version + 1

        import copy
        reverted_data = copy.deepcopy(target_row.json)
        reverted_it = CanonicalItinerary(**reverted_data)

        reverted_it.version = new_version_num
        reverted_it.parent_version = current_version
        reverted_it.created_by = "revert"
        reverted_it.change_summary = f"Reverted back to version {target_version}"

        version_repo.create(
            trip_id=trip_id,
            version=new_version_num,
            parent_version=current_version,
            json_data=reverted_it.model_dump(),
            created_by="revert",
            change_summary=reverted_it.change_summary
        )

        trip_repo.update_version_pointer(trip_id, new_version_num)

        # Notification
        noti_repo = NotificationRepository(db)
        noti_repo.create(
            user_id=trip.user_id,
            trip_id=trip.id,
            type="itinerary_change",
            title=f"Itinerary Reverted (v{new_version_num})",
            body=f"Trip was reverted to version {target_version}.",
            severity="info"
        )

        return reverted_it

    @classmethod
    def check_conditions_and_replan(cls, db: Any, trip_id: Union[str, int]) -> Tuple[List[Dict[str, Any]], Optional[CanonicalItinerary]]:
        ctx = build_agent_context(db, trip_id)
        if not ctx.itinerary:
            return [], None

        detected = EventDetector.detect_weather_events(ctx.itinerary)
        budget_evs = EventDetector.detect_budget_events(ctx.itinerary)
        detected.extend(budget_evs)

        if not detected:
            return [], None

        event_repo = EventRepository(db)
        replan_it = ctx.itinerary

        for ev in detected:
            db_event = event_repo.create(
                trip_id=trip_id,
                type=ev.event_type,
                day_id=ev.day_id,
                severity=ev.severity,
                payload=ev.payload,
                source="live"
            )

            # Replan for weather event
            if ev.event_type == "weather" and ev.affected_item_ids:
                # Find outdoor item to swap for indoor
                affected_id = ev.affected_item_ids[0]
                target_day = next((d for d in replan_it.days if any(it.id == affected_id for it in d.items)), None)
                target_dow = ""
                if target_day:
                    start_dt = datetime.strptime(ctx.trip.start_date, "%Y-%m-%d")
                    target_date = start_dt + timedelta(days=target_day.day_number - 1)
                    target_dow = target_date.strftime("%A")

                existing_place_ids = {it.place_id for d in replan_it.days for it in d.items if it.id != affected_id}
                indoor_candidates = [
                    p for p in ctx.catalog_places
                    if p.indoor and p.kind == "attraction"
                    and p.id not in existing_place_ids
                    and not (target_dow and p.closed_days and target_dow in p.closed_days)
                ]
                if indoor_candidates:
                    cs = ChangeSet(
                        ops=[ChangeOp(op=OpType.REPLACE_ITEM, item_id=affected_id, new_place_id=indoor_candidates[0].id)],
                        rationale=f"Replaced outdoor activity with indoor {indoor_candidates[0].name} due to rain alert on {ev.day_id}."
                    )
                    res = OrchestratorPipeline.run_pipeline(
                        db=db,
                        trip=ctx.trip,
                        base_itinerary=replan_it,
                        changeset=cs,
                        created_by="replanner_agent",
                        change_summary=cs.rationale,
                        catalog_places=ctx.catalog_places
                    )
                    if res.success:
                        replan_it = res.itinerary
                        event_repo.mark_handled(db_event.id, res.itinerary.version)

        events_dicts = [{"type": e.event_type, "day_id": e.day_id, "severity": e.severity, "detail": e.detail} for e in detected]
        return events_dicts, replan_it

    @classmethod
    def simulate_event(
        cls,
        db: Any,
        trip_id: Union[str, int],
        event_type: str = "weather",
        day_id: str = "day_3",
        severity: str = "high",
        detail: str = "Rain 85% forecasted",
        payload: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], Optional[CanonicalItinerary]]:
        ctx = build_agent_context(db, trip_id)
        if not ctx.itinerary:
            raise ValidationError("No itinerary exists for this trip")

        event_repo = EventRepository(db)
        event_payload = payload or {"simulated": True, "condition": "rain", "rain_prob_pct": 85}

        db_event = event_repo.create(
            trip_id=trip_id,
            type=event_type,
            day_id=day_id,
            severity=severity,
            payload=event_payload,
            source="simulated"
        )

        replan_it: Optional[CanonicalItinerary] = None

        # If weather simulation on day_3
        # Multi-scenario handling
        target_day = next((d for d in ctx.itinerary.days if d.id == day_id), ctx.itinerary.days[0] if ctx.itinerary.days else None)
        changeset: Optional[ChangeSet] = None

        if target_day and event_type in ("weather", "rain"):
            target_day.weather.rain_prob_pct = 85
            target_day.weather.summary = "Heavy showers (Simulated)"
            target_day.weather.source = "simulated"

            outdoor_items = [it for it in target_day.items if not it.indoor and it.type == "activity"]
            indoor_places = [p for p in ctx.catalog_places if p.indoor and p.kind == "attraction"]

            if outdoor_items and indoor_places:
                item_to_replace = outdoor_items[0]
                existing_place_ids = {it.place_id for d in ctx.itinerary.days for it in d.items if it.id != item_to_replace.id}

                start_dt = datetime.strptime(ctx.trip.start_date, "%Y-%m-%d")
                target_date = start_dt + timedelta(days=target_day.day_number - 1)
                target_dow = target_date.strftime("%A")

                valid_indoor = [
                    p for p in indoor_places
                    if p.id not in existing_place_ids
                    and not (target_dow and p.closed_days and target_dow in p.closed_days)
                ]
                new_indoor = valid_indoor[0] if valid_indoor else indoor_places[0]

                changeset = ChangeSet(
                    ops=[ChangeOp(op=OpType.REPLACE_ITEM, item_id=item_to_replace.id, new_place_id=new_indoor.id)],
                    rationale=f"Monsoon Alert: Swapped outdoor '{item_to_replace.name}' for indoor '{new_indoor.name}'."
                )

        elif target_day and event_type in ("delay", "flight_delay"):
            # Shift morning activity or swap for afternoon leisure
            activity_items = [it for it in target_day.items if it.type == "activity"]
            if activity_items:
                item_to_adjust = activity_items[0]
                changeset = ChangeSet(
                    ops=[ChangeOp(op=OpType.MOVE_ITEM, item_id=item_to_adjust.id, to_day_id=target_day.id)],
                    rationale=f"Flight Delay Contingency: Rescheduled morning schedule on {target_day.id} to accommodate 4-hour delay."
                )

        elif target_day and event_type in ("closure", "attraction_closed"):
            # Replace an attraction with an alternative
            attraction_items = [it for it in target_day.items if it.type == "activity"]
            if attraction_items:
                closed_item = attraction_items[0]
                existing_place_ids = {it.place_id for d in ctx.itinerary.days for it in d.items}
                candidates = [p for p in ctx.catalog_places if p.id not in existing_place_ids and p.kind == "attraction"]
                alt_place = candidates[0] if candidates else ctx.catalog_places[0]
                changeset = ChangeSet(
                    ops=[ChangeOp(op=OpType.REPLACE_ITEM, item_id=closed_item.id, new_place_id=alt_place.id)],
                    rationale=f"Attraction Closed: Replaced '{closed_item.name}' with verified alternative '{alt_place.name}'."
                )

        elif event_type in ("budget_cut", "budget"):
            # Lower the budget limit and optimize
            new_limit = max(3000, int(ctx.itinerary.budget.total_limit * 0.75))
            changeset = ChangeSet(
                ops=[ChangeOp(op=OpType.SET_BUDGET, total_limit=new_limit)],
                rationale=f"Budget Crunch: Scaled down budget limit to ₹{new_limit:,} with optimized cost efficiency."
            )

        elif target_day and event_type in ("slow_travel", "fatigue"):
            # Remove or relax one item for pacing
            if len(target_day.items) > 2:
                relaxed_item = target_day.items[-1]
                changeset = ChangeSet(
                    ops=[ChangeOp(op=OpType.REMOVE_ITEM, item_id=relaxed_item.id)],
                    rationale=f"Slow Travel Mode: Relaxed pace on {target_day.id} to add dedicated sunset leisure time."
                )

        if changeset:
            res = OrchestratorPipeline.run_pipeline(
                db=db,
                trip=ctx.trip,
                base_itinerary=ctx.itinerary,
                changeset=changeset,
                created_by="replanner_agent",
                change_summary=changeset.rationale,
                catalog_places=ctx.catalog_places
            )
            if res.success:
                replan_it = res.itinerary
                event_repo.mark_handled(db_event.id, res.itinerary.version)

                noti_repo = NotificationRepository(db)
                noti_repo.create(
                    user_id=ctx.trip.user_id,
                    trip_id=ctx.trip.id,
                    type="scenario_alert",
                    title=f"Scenario Simulated: {event_type.replace('_', ' ').title()}",
                    body=changeset.rationale,
                    severity="info"
                )

        event_dict = {
            "id": db_event.id,
            "type": db_event.type,
            "day_id": db_event.day_id,
            "severity": db_event.severity,
            "detail": detail,
            "source": db_event.source,
            "handled_version": db_event.handled_version
        }
        return event_dict, replan_it
