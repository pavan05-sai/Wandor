import copy
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any
from fastapi import APIRouter, Depends
from app.api.dependencies import get_owned_trip
from app.core.errors import NotFoundError
from app.models.database import get_db
from app.repositories.base import EntityDoc
from app.repositories.entities import ShareRepository
from app.repositories.versions import VersionRepository
from app.schemas.common import success_response
from app.schemas.shares import ShareCreateRequest, ShareResponse

router = APIRouter(tags=["Sharing"])


def _iso(dt: Any) -> str:
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt or "")


@router.post("/trips/{trip_id}/share")
def create_share_link(
    share_req: ShareCreateRequest,
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    token = secrets.token_hex(16)  # 32 characters hex string
    expires_at = datetime.now(timezone.utc) + timedelta(days=share_req.expiry_days or 30)

    repo = ShareRepository(db)
    share = repo.create(
        trip_id=trip.id,
        token=token,
        expires_at=expires_at,
        version_pinned=share_req.version_pinned
    )
    url = f"/shared/{token}"
    return success_response(
        ShareResponse(
            token=token,
            url=url,
            expires_at=_iso(expires_at),
            created_at=_iso(share.created_at)
        ).model_dump()
    )


@router.delete("/trips/{trip_id}/share")
def revoke_share(
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    repo = ShareRepository(db)
    repo.revoke_by_trip(trip.id)
    return success_response({"revoked": True})


@router.get("/shared/{token}")
def get_shared_itinerary(token: str, db: Any = Depends(get_db)):
    """Public read-only sanitized itinerary view (no auth required)."""
    share_repo = ShareRepository(db)
    share = share_repo.get_by_token(token)
    if not share or share.revoked:
        raise NotFoundError("Shared trip link not found or has been revoked")

    if share.expires_at:
        now = datetime.now(timezone.utc)
        exp = share.expires_at
        if hasattr(exp, "replace"):
            exp = exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp
            if now > exp:
                raise NotFoundError("Shared link has expired")

    version_repo = VersionRepository(db)
    if share.version_pinned:
        version_row = version_repo.get_by_version(share.trip_id, share.version_pinned)
    else:
        version_row = version_repo.get_latest(share.trip_id)

    if not version_row or not version_row.json:
        raise NotFoundError("Itinerary not available")

    # Sanitize itinerary per Section 18 (no user email, no private notes, clean view)
    it_data = copy.deepcopy(version_row.json)
    it_data["notes"] = [n for n in it_data.get("notes", []) if n.get("origin") != "private"]

    return success_response({
        "shared": True,
        "token": token,
        "itinerary": it_data
    })
