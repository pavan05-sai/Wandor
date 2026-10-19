from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.repositories.base import EntityDoc
from app.repositories.entities import NotificationRepository
from app.repositories.trips import TripRepository
from app.repositories.versions import VersionRepository
from app.schemas.changeset import ChangeSet
from app.schemas.itinerary import CanonicalItinerary, RouteLeg
from app.services.routing import RoutingService
from app.workers.budget import BudgetEngine
from app.workers.changeset import ChangeSetApplier
from app.workers.diff import ItineraryDiffEngine
from app.workers.optimizer import ScheduleOptimizer
from app.workers.validator import ItineraryValidator

logger = get_logger("orchestrator_pipeline")


class PipelineResult:
    def __init__(
        self,
        success: bool,
        itinerary: CanonicalItinerary,
        diff: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[Any]] = None
    ):
        self.success = success
        self.itinerary = itinerary
        self.diff = diff
        self.errors = errors or []
        self.warnings = warnings or []


class OrchestratorPipeline:
    @classmethod
    def run_pipeline(
        cls,
        db: Any,
        trip: Any,
        base_itinerary: CanonicalItinerary,
        changeset: ChangeSet,
        created_by: str,
        change_summary: str,
        catalog_places: List[Any]
    ) -> PipelineResult:
        place_by_id = {p.id: p for p in catalog_places}

        # 1. Apply ChangeSet on a copy
        try:
            modified_it, affected_days = ChangeSetApplier.apply_changeset(
                itinerary=base_itinerary,
                changeset=changeset,
                catalog_places=place_by_id
            )
        except ValidationError as ve:
            return PipelineResult(
                success=False,
                itinerary=base_itinerary,
                errors=[ve.message]
            )

        # 2. Optimize affected days
        hotel_place = place_by_id.get(modified_it.accommodation.place_id)
        for day in modified_it.days:
            if day.day_number in affected_days:
                acts = [place_by_id[it.place_id] for it in day.items if it.type == "activity" and it.place_id in place_by_id]
                rests = [place_by_id[it.place_id] for it in day.items if it.type == "meal" and it.place_id in place_by_id]
                reasons = {it.place_id: it.reason for it in day.items}
                factors = {it.place_id: it.reason_factors for it in day.items}

                re_optimized = ScheduleOptimizer.optimize_day_schedule(
                    day_number=day.day_number,
                    date_str=day.date,
                    theme=day.theme,
                    activities=acts,
                    restaurants=rests,
                    hotel=hotel_place,
                    reasons_map=reasons,
                    factors_map=factors
                )
                re_optimized.weather = day.weather
                # Preserve locked flags
                for new_item in re_optimized.items:
                    for old_item in day.items:
                        if new_item.place_id == old_item.place_id:
                            new_item.locked = old_item.locked
                day.items = re_optimized.items
                day.routes = re_optimized.routes
                day.totals = re_optimized.totals

        # 3. Route Calculation (OSRM / Haversine) for affected days
        for day in modified_it.days:
            if day.day_number in affected_days:
                for leg in day.routes:
                    from_item = next((i for i in day.items if i.id == leg.from_item), None)
                    to_item = next((i for i in day.items if i.id == leg.to_item), None)
                    if from_item and to_item:
                        route_data = RoutingService.calculate_leg(
                            db=db,
                            lat1=from_item.lat,
                            lng1=from_item.lng,
                            lat2=to_item.lat,
                            lng2=to_item.lng,
                            mode=leg.mode
                        )
                        leg.distance_km = route_data["distance_km"]
                        leg.duration_min = route_data["duration_min"]
                        leg.geometry = route_data["geometry"]
                        leg.source = route_data["source"]
                        leg.cost = int(leg.distance_km * 25)

        # 4. Budget Engine
        modified_it.budget = BudgetEngine.calculate_budget(
            days=modified_it.days,
            accommodation=modified_it.accommodation,
            travelers=modified_it.trip.travelers,
            total_limit=modified_it.budget.total_limit,
            preferences=modified_it.preferences,
            reserve_pct=modified_it.budget.reserve_pct
        )

        # 5. Validate (Rules V1 to V12)
        val_result = ItineraryValidator.validate(
            itinerary=modified_it,
            catalog_places=place_by_id,
            previous_version=base_itinerary
        )

        if not val_result.is_valid:
            logger.warning(f"Pipeline validation failed: {val_result.errors}")
            return PipelineResult(
                success=False,
                itinerary=base_itinerary,
                errors=val_result.errors,
                warnings=val_result.warnings
            )

        # 6. Diff calculation
        diff = ItineraryDiffEngine.calculate_diff(base_itinerary, modified_it)

        # 7. Persist Version N+1
        new_version_num = base_itinerary.version + 1
        modified_it.version = new_version_num
        modified_it.parent_version = base_itinerary.version
        modified_it.created_by = created_by
        modified_it.change_summary = change_summary or diff["summary"]
        modified_it.warnings = val_result.warnings

        version_repo = VersionRepository(db)
        version_repo.create(
            trip_id=trip.id,
            version=new_version_num,
            parent_version=base_itinerary.version,
            json_data=modified_it.model_dump(),
            created_by=created_by,
            change_summary=modified_it.change_summary,
            change_set_json=changeset.model_dump()
        )

        trip_repo = TripRepository(db)
        trip_repo.update_version_pointer(trip.id, new_version_num)

        # 8. Notification
        noti_repo = NotificationRepository(db)
        noti_repo.create(
            user_id=trip.user_id,
            trip_id=trip.id,
            type="itinerary_change",
            title=f"Itinerary Updated (v{new_version_num})",
            body=f"{modified_it.change_summary}. {diff['summary']}.",
            severity="info"
        )

        return PipelineResult(
            success=True,
            itinerary=modified_it,
            diff=diff,
            warnings=val_result.warnings
        )
