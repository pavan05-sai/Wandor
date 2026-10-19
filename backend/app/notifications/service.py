from typing import Any, List, Optional, Union
from app.repositories.base import EntityDoc
from app.repositories.entities import NotificationRepository


class NotificationService:
    @classmethod
    def list_notifications(cls, db: Any, user_id: Union[str, int], unread_only: bool = False) -> List[EntityDoc]:
        repo = NotificationRepository(db)
        return repo.list_by_user(user_id, unread_only)

    @classmethod
    def mark_as_read(cls, db: Any, notification_id: Union[str, int], user_id: Union[str, int]) -> bool:
        repo = NotificationRepository(db)
        return repo.mark_read(notification_id, user_id)
