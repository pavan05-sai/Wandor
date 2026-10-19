"""
MongoDB repository for User and UserPreferences operations.
Replaces the SQLAlchemy UserRepository.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger

logger = get_logger("user_repo_mongo")


def _user_from_doc(doc: dict) -> dict:
    """Normalize a MongoDB user document to a plain dict."""
    if not doc:
        return {}
    return {
        "id": str(doc["_id"]),
        "email": doc.get("email", ""),
        "password_hash": doc.get("password_hash", ""),
        "display_name": doc.get("display_name", ""),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
        "preferences": doc.get("preferences", _default_prefs()),
    }


def _default_prefs() -> dict:
    return {
        "interests": [],
        "pace": "relaxed",
        "budget_level": "mid",
        "transport_modes": ["taxi", "walk"],
        "accommodation_type": "hotel",
        "dietary": [],
        "avoid": [],
        "mobility": "standard",
        "home_city": None,
        "updated_at": datetime.now(timezone.utc),
    }


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.col = db.users

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        doc = await self.col.find_one({"_id": oid})
        return _user_from_doc(doc) if doc else None

    async def get_by_email(self, email: str) -> Optional[dict]:
        doc = await self.col.find_one({"email": email.lower().strip()})
        return _user_from_doc(doc) if doc else None

    async def create(self, email: str, password_hash: str, display_name: str) -> dict:
        now = datetime.now(timezone.utc)
        doc = {
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "display_name": display_name.strip(),
            "created_at": now,
            "preferences": _default_prefs(),
        }
        result = await self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _user_from_doc(doc)

    async def get_preferences(self, user_id: str) -> Optional[dict]:
        user = await self.get_by_id(user_id)
        return user.get("preferences") if user else None

    async def update_preferences(self, user_id: str, pref_data: dict) -> Optional[dict]:
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        now = datetime.now(timezone.utc)
        pref_data["updated_at"] = now
        await self.col.update_one(
            {"_id": oid},
            {"$set": {f"preferences.{k}": v for k, v in pref_data.items()}}
        )
        return await self.get_by_id(user_id)
