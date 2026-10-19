from typing import Any, Union
from fastapi import Depends
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.security import get_current_user_id
from app.models.database import get_db
from app.repositories.base import EntityDoc
from app.repositories.trips import TripRepository
from app.repositories.users import UserRepository


def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Any = Depends(get_db)
) -> EntityDoc:
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedError("User account not found")
    return user


def get_owned_trip(
    trip_id: str,
    user: EntityDoc = Depends(get_current_user),
    db: Any = Depends(get_db)
) -> EntityDoc:
    repo = TripRepository(db)
    trip = repo.get_by_id_and_user(trip_id=trip_id, user_id=user.id)
    if not trip:
        # Return 404 per Section 18 to avoid leaking trip existence
        raise NotFoundError("Trip not found")
    return trip
