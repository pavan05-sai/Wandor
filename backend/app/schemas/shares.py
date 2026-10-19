from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field


class ShareCreateRequest(BaseModel):
    expiry_days: Optional[int] = Field(default=30, gt=0, le=365)
    version_pinned: Optional[int] = None


class ShareResponse(BaseModel):
    token: str
    url: str
    expires_at: Optional[str] = None
    created_at: str


class EventSimulateRequest(BaseModel):
    type: str = Field(default="weather", description="weather, budget, closure, transport")
    day_id: Optional[str] = "day_3"
    severity: str = Field(default="high", description="low, medium, high")
    detail: Optional[str] = "Rain 85% forecasted"
    payload: Optional[Dict[str, Any]] = None


class TravelEventResponse(BaseModel):
    id: Union[int, str]
    trip_id: Union[int, str]
    type: str
    day_id: Optional[str] = None
    severity: str
    payload: Optional[Dict[str, Any]] = None
    source: str
    handled_version: Optional[int] = None
    created_at: str
