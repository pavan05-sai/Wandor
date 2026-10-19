"""
MongoDB repository for Trip operations.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from bson import ObjectId
from app.db.mongodb import get_db
from app.repositories.base import EntityDoc, to_id_filter, to_object_id


def _trip_from_doc(doc: Optional[dict]) -> Optional[EntityDoc]:
    if not doc:
        return None
    d = dict(doc)
    d["id"] = str(doc["_id"])
    d["user_id"] = str(doc.get("user_id", ""))
    d["title"] = doc.get("title", "")
    d["destination_id"] = doc.get("destination_id", "")
    d["start_date"] = doc.get("start_date", "")
    d["end_date"] = doc.get("end_date", "")
    d["num_days"] = doc.get("num_days", 1)
    d["budget"] = doc.get("budget", 30000)
    d["adults"] = doc.get("adults", 2)
    d["children"] = doc.get("children", 0)
    d["status"] = doc.get("status", "active")
    d["current_version"] = doc.get("current_version", 0)
    d["mode"] = doc.get("mode", "live")
    d["created_at"] = doc.get("created_at") or datetime.now(timezone.utc)
    d["updated_at"] = doc.get("updated_at") or datetime.now(timezone.utc)
    return EntityDoc(d)


class TripRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.trips

    def get_by_id(self, trip_id: Union[str, int, ObjectId]) -> Optional[EntityDoc]:
        flt = to_id_filter(trip_id)
        doc = self.col.find_one(flt)
        return _trip_from_doc(doc)

    def get_by_id_and_user(
        self, trip_id: Union[str, int, ObjectId], user_id: Union[str, int, ObjectId]
    ) -> Optional[EntityDoc]:
        trip_flt = to_id_filter(trip_id)
        user_flt = to_id_filter(user_id, id_field="user_id", sqlite_field="sqlite_user_id")
        combined = {"$and": [trip_flt, user_flt]}
        doc = self.col.find_one(combined)
        return _trip_from_doc(doc)

    def list_by_user(self, user_id: Union[str, int, ObjectId]) -> List[EntityDoc]:
        user_flt = to_id_filter(user_id, id_field="user_id", sqlite_field="sqlite_user_id")
        docs = list(self.col.find(user_flt).sort("updated_at", -1))
        return [_trip_from_doc(d) for d in docs if d]

    def create(
        self,
        user_id: Union[str, int, ObjectId],
        title: str,
        destination_id: str,
        start_date: str,
        end_date: str,
        num_days: int,
        budget: int = 30000,
        adults: int = 2,
        children: int = 0,
        mode: str = "live"
    ) -> EntityDoc:
        user_oid = to_object_id(user_id) or str(user_id)
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": user_oid,
            "title": title,
            "destination_id": destination_id,
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days,
            "budget": budget,
            "adults": adults,
            "children": children,
            "status": "active",
            "current_version": 0,
            "mode": mode,
            "created_at": now,
            "updated_at": now,
        }
        res = self.col.insert_one(doc)
        doc["_id"] = res.inserted_id
        return _trip_from_doc(doc)

    def update_version_pointer(self, trip_id: Union[str, int, ObjectId], version: int) -> Optional[EntityDoc]:
        flt = to_id_filter(trip_id)
        now = datetime.now(timezone.utc)
        self.col.update_one(flt, {"$set": {"current_version": version, "updated_at": now}})
        return self.get_by_id(trip_id)

    def delete(self, trip_or_id: Union[EntityDoc, str, int, ObjectId]) -> None:
        trip_id = trip_or_id.id if hasattr(trip_or_id, "id") else (
            trip_or_id.get("id") if isinstance(trip_or_id, dict) else trip_or_id
        )
        flt = to_id_filter(trip_id)
        self.col.delete_one(flt)
