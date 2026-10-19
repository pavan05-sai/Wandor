from typing import Optional, Union
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: Union[int, str]
    user_id: Union[int, str]
    trip_id: Optional[Union[int, str]] = None
    type: str
    title: str
    body: str
    severity: str
    read: bool
    created_at: str
    due_at: Optional[str] = None
