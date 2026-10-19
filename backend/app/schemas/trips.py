from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.schemas.preferences import PreferencesSchema
from app.schemas.itinerary import Travelers, CanonicalItinerary


class TripCreateRequest(BaseModel):
    destination_id: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    travelers: Travelers = Field(default_factory=Travelers)
    budget: int = Field(gt=0, description="Total budget in INR")
    preferences: Optional[PreferencesSchema] = None
    title: Optional[str] = None


class TripSettingsUpdate(BaseModel):
    budget: Optional[int] = None
    num_days: Optional[int] = None
    preferences: Optional[PreferencesSchema] = None


class TripSummary(BaseModel):
    id: Union[int, str]
    user_id: Union[int, str]
    title: str
    destination_id: str
    destination_name: str
    start_date: str
    end_date: str
    num_days: int
    status: str
    current_version: int
    mode: str
    total_budget: int
    estimated_total: int
    budget_status: str
    created_at: str


class TripDetailResponse(BaseModel):
    trip: TripSummary
    itinerary: Optional[CanonicalItinerary] = None
