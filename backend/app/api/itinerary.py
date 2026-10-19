from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, status
from app.api.dependencies import get_owned_trip
from app.core.errors import NotFoundError, ValidationError
from app.models.database import get_db
from app.orchestrator.context import build_agent_context
from app.orchestrator.orchestrator import Orchestrator
from app.orchestrator.pipeline import OrchestratorPipeline
from app.repositories.base import EntityDoc
from app.repositories.places import PlaceRepository
from app.repositories.trips import TripRepository
from app.repositories.versions import VersionRepository
from app.schemas.changeset import ChangeOp, ChangeSet, OpType
from app.schemas.common import success_response
from app.schemas.itinerary import CanonicalItinerary
from app.schemas.trips import TripSettingsUpdate
from app.workers.diff import ItineraryDiffEngine

router = APIRouter(prefix="/trips/{trip_id}", tags=["Itinerary"])


def _iso(dt: Any) -> str:
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt or "")


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_itinerary(
    regenerate: bool = Query(default=False),
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    itinerary, trace, alternatives = Orchestrator.generate_trip(db, trip.id, regenerate=regenerate)
    return success_response({
        "itinerary": itinerary.model_dump(),
        "trace": trace,
        "alternatives": [a.model_dump() for a in alternatives]
    }, provenance=itinerary.provenance.model_dump())


@router.get("/versions")
def list_versions(
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    version_repo = VersionRepository(db)
    versions = version_repo.list_by_trip(trip.id)
    return success_response([
        {
            "version": v.version,
            "parent_version": v.parent_version,
            "created_by": v.created_by,
            "change_summary": v.change_summary,
            "created_at": _iso(v.created_at)
        }
        for v in versions
    ])


@router.get("/versions/{version_num}")
def get_version(
    version_num: int,
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    version_repo = VersionRepository(db)
    v = version_repo.get_by_version(trip.id, version_num)
    if not v:
        raise NotFoundError(f"Version {version_num} not found")
    return success_response(v.json)


@router.get("/diff")
def get_version_diff(
    from_version: int = Query(alias="from"),
    to_version: int = Query(alias="to"),
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    version_repo = VersionRepository(db)
    v_from = version_repo.get_by_version(trip.id, from_version)
    v_to = version_repo.get_by_version(trip.id, to_version)

    if not v_from or not v_to:
        raise NotFoundError("One or both requested versions not found")

    it_from = CanonicalItinerary(**v_from.json)
    it_to = CanonicalItinerary(**v_to.json)

    diff = ItineraryDiffEngine.calculate_diff(it_from, it_to)
    return success_response(diff)


@router.post("/versions/{version_num}/revert")
def revert_version(
    version_num: int,
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    reverted_it = Orchestrator.revert_trip(db, trip.id, version_num)
    res_dict = reverted_it.model_dump()
    res_dict["itinerary"] = reverted_it.model_dump()
    res_dict["reverted_to"] = version_num
    res_dict["current_version"] = reverted_it.version
    return success_response(res_dict)


@router.patch("/items/{item_id}")
def edit_item(
    item_id: str,
    op_req: Dict[str, Any],
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    """Manual item edits: lock, unlock, remove, move, or update booking ref."""
    ctx = build_agent_context(db, trip.id)
    if not ctx.itinerary:
        raise ValidationError("No itinerary generated")

    op_name = op_req.get("op", "").upper()

    # Handle booking reference update directly
    if "booking_ref" in op_req or op_name == "BOOKING_REF":
        for d in ctx.itinerary.days:
            for it in d.items:
                if it.id == item_id:
                    if not it.booking:
                        from app.schemas.itinerary import BookingRef
                        it.booking = BookingRef()
                    it.booking.ref = op_req.get("booking_ref") or op_req.get("ref")
                    # Save version
                    new_v = ctx.itinerary.version + 1
                    ctx.itinerary.version = new_v
                    ctx.itinerary.change_summary = f"Updated booking reference for {it.name}"
                    VersionRepository(db).create(trip.id, new_v, ctx.itinerary.model_dump(), "user_edit", ctx.itinerary.change_summary)
                    TripRepository(db).update_version_pointer(trip.id, new_v)
                    return success_response({"itinerary": ctx.itinerary.model_dump()})
        raise NotFoundError(f"Item '{item_id}' not found")

    # ChangeSet op
    change_op = ChangeOp(
        op=OpType(op_name),
        item_id=item_id,
        to_day_id=op_req.get("to_day_id"),
        new_place_id=op_req.get("new_place_id")
    )
    cs = ChangeSet(ops=[change_op], rationale=f"Manual user action: {op_name} on {item_id}")

    res = OrchestratorPipeline.run_pipeline(
        db=db,
        trip=trip,
        base_itinerary=ctx.itinerary,
        changeset=cs,
        created_by="user_edit",
        change_summary=cs.rationale,
        catalog_places=ctx.catalog_places
    )

    if not res.success:
        raise ValidationError(f"Could not apply change: {', '.join(res.errors)}")

    return success_response({
        "itinerary": res.itinerary.model_dump(),
        "diff": res.diff
    })


@router.post("/alternatives/{alt_id}/apply")
def apply_alternative(
    alt_id: str,
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    ctx = build_agent_context(db, trip.id)
    if not ctx.itinerary:
        raise ValidationError("No itinerary generated")

    target_alt = next((a for a in ctx.itinerary.alternatives if a.id == alt_id), None)
    if not target_alt:
        raise NotFoundError(f"Alternative '{alt_id}' not found")

    ops_data = target_alt.change_set.get("ops", [])
    cs = ChangeSet(
        ops=[ChangeOp(**op) for op in ops_data],
        rationale=f"Applied alternative: {target_alt.label}"
    )

    res = OrchestratorPipeline.run_pipeline(
        db=db,
        trip=trip,
        base_itinerary=ctx.itinerary,
        changeset=cs,
        created_by="alternative_apply",
        change_summary=cs.rationale,
        catalog_places=ctx.catalog_places
    )

    if not res.success:
        raise ValidationError(f"Failed to apply alternative: {', '.join(res.errors)}")

    return success_response({
        "itinerary": res.itinerary.model_dump(),
        "diff": res.diff
    })


@router.patch("/settings")
def update_trip_settings(
    settings_in: TripSettingsUpdate,
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    ctx = build_agent_context(db, trip.id)
    if not ctx.itinerary:
        raise ValidationError("No itinerary generated")

    ops = []
    if settings_in.budget:
        ops.append(ChangeOp(op=OpType.SET_BUDGET, total_limit=settings_in.budget))
    if settings_in.preferences:
        for k, v in settings_in.preferences.model_dump(exclude_unset=True).items():
            ops.append(ChangeOp(op=OpType.SET_PREFERENCE, key=k, value=v))

    cs = ChangeSet(ops=ops, rationale="Updated trip settings & preferences")

    res = OrchestratorPipeline.run_pipeline(
        db=db,
        trip=trip,
        base_itinerary=ctx.itinerary,
        changeset=cs,
        created_by="settings_update",
        change_summary="Settings updated",
        catalog_places=ctx.catalog_places
    )

    if not res.success:
        raise ValidationError(f"Could not update settings: {', '.join(res.errors)}")

    return success_response({
        "itinerary": res.itinerary.model_dump(),
        "diff": res.diff
    })


@router.post("/compiler/parse")
def compile_unstructured_text(
    req: Dict[str, Any],
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    from app.services.compiler import ItineraryCompilerService
    text = req.get("text", "")
    if not text.strip():
        raise ValidationError("Text input is required for compilation")

    ctx = build_agent_context(db, trip.id)
    result = ItineraryCompilerService.compile_text(
        text=text,
        trip=trip,
        catalog_places=ctx.catalog_places,
        existing_itinerary=ctx.itinerary
    )
    return success_response(result)


@router.post("/compiler/apply")
def apply_compiled_items(
    req: Dict[str, Any],
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    items = req.get("items", [])
    if not items:
        raise ValidationError("No items provided to apply")

    ctx = build_agent_context(db, trip.id)
    if not ctx.itinerary:
        raise ValidationError("No itinerary exists for this trip")

    # Add items to target days
    target_it = ctx.itinerary
    added_names = []
    for it_dict in items:
        target_day_id = it_dict.get("day_id") or "day_1"
        target_day = next((d for d in target_it.days if d.id == target_day_id), target_it.days[0])

        from app.schemas.itinerary import Coordinates, ItineraryItem, ItemProvenance
        item_obj = ItineraryItem(
            id=it_dict.get("id") or f"imp_{int(datetime.now().timestamp())}",
            name=it_dict.get("name", "Imported Activity"),
            type=it_dict.get("type", "activity"),
            category=it_dict.get("category", "sightseeing"),
            start_time=it_dict.get("start_time", "11:00"),
            duration_min=it_dict.get("duration_min", 90),
            cost=it_dict.get("cost", 200),
            place_id=it_dict.get("place_id"),
            coordinates=Coordinates(
                lat=it_dict.get("coordinates", {}).get("lat", 15.49),
                lng=it_dict.get("coordinates", {}).get("lng", 73.82)
            ),
            provenance=ItemProvenance(
                source="imported_document",
                confidence=it_dict.get("provenance", {}).get("confidence", 0.9)
            )
        )
        target_day.items.append(item_obj)
        added_names.append(item_obj.name)

    # Save new version
    new_version = target_it.version + 1
    target_it.version = new_version
    summary = f"Compiled & added {len(added_names)} imported items: {', '.join(added_names[:3])}"
    target_it.change_summary = summary

    VersionRepository(db).create(trip.id, new_version, target_it.model_dump(), "compiler", summary)
    TripRepository(db).update_version_pointer(trip.id, new_version)

    return success_response({
        "itinerary": target_it.model_dump(),
        "added_count": len(added_names),
        "version": new_version
    })
