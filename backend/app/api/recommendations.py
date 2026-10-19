from typing import Any, Optional
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_owned_trip
from app.models.database import get_db
from app.orchestrator.context import build_agent_context
from app.repositories.base import EntityDoc
from app.schemas.common import success_response
from app.tools.registry import ToolRegistry

router = APIRouter(prefix="/trips/{trip_id}/recommendations", tags=["Recommendations"])


@router.get("")
def get_recommendations(
    kind: Optional[str] = Query(default=None, description="attraction, restaurant, hotel"),
    category: Optional[str] = Query(default=None),
    max_cost: Optional[int] = Query(default=None),
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    ctx = build_agent_context(db, trip.id)
    registry = ToolRegistry(db, ctx.itinerary, trip.destination_id)
    candidates = registry.get_candidates(
        kind=kind,
        category=category,
        max_cost=max_cost,
        limit=20
    )
    return success_response(candidates)
