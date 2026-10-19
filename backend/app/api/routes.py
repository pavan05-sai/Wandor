from typing import Any
from fastapi import APIRouter, Depends
from app.api.dependencies import get_owned_trip
from app.core.errors import NotFoundError
from app.models.database import get_db
from app.repositories.base import EntityDoc
from app.repositories.versions import VersionRepository
from app.schemas.common import success_response
from app.schemas.itinerary import CanonicalItinerary

router = APIRouter(prefix="/trips/{trip_id}/routes", tags=["Routes"])


@router.get("/{day_id}")
def get_day_routes(
    day_id: str,
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    version_repo = VersionRepository(db)
    v = version_repo.get_latest(trip.id)
    if not v or not v.json:
        raise NotFoundError("No itinerary found")

    it = CanonicalItinerary(**v.json)
    target_day = next((d for d in it.days if d.id == day_id), None)
    if not target_day:
        raise NotFoundError(f"Day '{day_id}' not found")

    provenance = it.provenance.routing if it.provenance else "estimated"
    return success_response({
        "day_id": day_id,
        "routes": [r.model_dump() for r in target_day.routes],
        "provenance": provenance
    })
