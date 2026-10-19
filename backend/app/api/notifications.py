from typing import Any
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_current_user
from app.core.errors import NotFoundError
from app.models.database import get_db
from app.notifications.service import NotificationService
from app.repositories.base import EntityDoc
from app.schemas.common import success_response
from app.schemas.notifications import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _iso(dt: Any) -> str:
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt or "")


@router.get("")
def list_notifications(
    unread: bool = Query(default=False),
    user: EntityDoc = Depends(get_current_user),
    db: Any = Depends(get_db)
):
    notis = NotificationService.list_notifications(db, user.id, unread_only=unread)
    return success_response([
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            trip_id=n.trip_id,
            type=n.type,
            title=n.title,
            body=n.body,
            severity=n.severity,
            read=n.read,
            created_at=_iso(n.created_at),
            due_at=_iso(n.due_at) if n.due_at else None
        ).model_dump()
        for n in notis
    ])


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: str,
    user: EntityDoc = Depends(get_current_user),
    db: Any = Depends(get_db)
):
    ok = NotificationService.mark_as_read(db, notification_id, user.id)
    if not ok:
        raise NotFoundError("Notification not found")
    return success_response({"marked_read": True, "id": notification_id})
