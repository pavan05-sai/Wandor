"""
MongoDB repository for User and UserPreference operations.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from bson import ObjectId
from app.db.mongodb import get_db
from app.repositories.base import EntityDoc, to_id_filter


def _default_preferences() -> Dict[str, Any]:
    return {
        "interests": ["beaches", "heritage", "food"],
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


def _user_from_doc(doc: Optional[dict]) -> Optional[EntityDoc]:
    if not doc:
        return None
    d = dict(doc)
    d["id"] = str(doc["_id"])
    if "preferences" not in d or not d["preferences"]:
        d["preferences"] = _default_preferences()
    # Ensure preferences is also an EntityDoc for attribute access
    if isinstance(d["preferences"], dict) and not isinstance(d["preferences"], EntityDoc):
        d["preferences"] = EntityDoc(d["preferences"])
    return EntityDoc(d)


class UserRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.users

    def get_by_id(self, user_id: Union[str, int, ObjectId]) -> Optional[EntityDoc]:
        flt = to_id_filter(user_id)
        doc = self.col.find_one(flt)
        return _user_from_doc(doc)

    def get_by_email(self, email: str) -> Optional[EntityDoc]:
        if not email:
            return None
        doc = self.col.find_one({"email": email.lower().strip()})
        return _user_from_doc(doc)

    def create(self, email: str, password_hash: str, display_name: str) -> EntityDoc:
        now = datetime.now(timezone.utc)
        doc = {
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "display_name": display_name.strip(),
            "created_at": now,
            "preferences": _default_preferences(),
        }
        res = self.col.insert_one(doc)
        doc["_id"] = res.inserted_id
        return _user_from_doc(doc)

    def get_preferences(self, user_id: Union[str, int, ObjectId]) -> Optional[EntityDoc]:
        user = self.get_by_id(user_id)
        if not user:
            return None
        prefs = user.get("preferences")
        if isinstance(prefs, dict):
            return EntityDoc(prefs) if not isinstance(prefs, EntityDoc) else prefs
        return EntityDoc(_default_preferences())

    def update_preferences(self, user_id: Union[str, int, ObjectId], pref_data: dict) -> Optional[EntityDoc]:
        user = self.get_by_id(user_id)
        if not user:
            return None

        current = dict(user.get("preferences") or _default_preferences())
        current.update(pref_data)
        current["updated_at"] = datetime.now(timezone.utc)

        flt = to_id_filter(user_id)
        self.col.update_one(flt, {"$set": {"preferences": current}})
        return EntityDoc(current)
