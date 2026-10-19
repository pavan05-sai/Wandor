from typing import Any
from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user
from app.models.database import get_db
from app.repositories.base import EntityDoc
from app.repositories.users import UserRepository
from app.schemas.auth import UserResponse
from app.schemas.common import success_response
from app.schemas.preferences import PreferencesSchema

router = APIRouter(prefix="/users", tags=["Users"])


def _iso(dt: Any) -> str:
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt or "")


@router.get("/me")
def get_me(user: EntityDoc = Depends(get_current_user)):
    return success_response(
        UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=_iso(user.created_at))
    )


@router.get("/me/preferences")
def get_my_preferences(user: EntityDoc = Depends(get_current_user), db: Any = Depends(get_db)):
    repo = UserRepository(db)
    pref = repo.get_preferences(user.id)
    if not pref:
        return success_response(PreferencesSchema())
    return success_response(PreferencesSchema(
        interests=pref.interests or [],
        pace=pref.pace or "relaxed",
        budget_level=pref.budget_level or "mid",
        transport_modes=pref.transport_modes or ["taxi"],
        accommodation_type=pref.accommodation_type or "hotel",
        dietary=pref.dietary or [],
        avoid=pref.avoid or [],
        mobility=pref.mobility or "standard",
        home_city=pref.home_city
    ))


@router.put("/me/preferences")
def update_my_preferences(
    pref_in: PreferencesSchema,
    user: EntityDoc = Depends(get_current_user),
    db: Any = Depends(get_db)
):
    repo = UserRepository(db)
    updated = repo.update_preferences(user.id, pref_in.model_dump())
    return success_response(PreferencesSchema(
        interests=updated.interests or [],
        pace=updated.pace or "relaxed",
        budget_level=updated.budget_level or "mid",
        transport_modes=updated.transport_modes or ["taxi"],
        accommodation_type=updated.accommodation_type or "hotel",
        dietary=updated.dietary or [],
        avoid=updated.avoid or [],
        mobility=updated.mobility or "standard",
        home_city=updated.home_city
    ))
