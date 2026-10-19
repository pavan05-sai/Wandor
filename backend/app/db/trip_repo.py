"""
MongoDB repository for Trip operations.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger

logger = get_logger("trip_repo_mongo")


def _trip_from_doc(doc: dict) -> dict:
    if not doc:
        return {}
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc.get("user_id", "")),
        "title": doc.get("title", ""),
        "destination_id": doc.get("destination_id", ""),
        "start_date": doc.get("start_date", ""),
        "end_date": doc.get("end_date", ""),
        "num_days": doc.get("num_days", 1),
        "budget": doc.get("budget", 30000),
        "adults": doc.get("adults", 2),
        "children": doc.get("children", 0),
        "status": doc.get("status", "active"),
        "current_version": doc.get("current_version", 0),
        "mode": doc.get("mode", "live"),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
        "updated_at": doc.get("updated_at", datetime.now(timezone.utc)),
    }


class TripRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.col = db.trips

    async def get_by_id(self, trip_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(trip_id)
        except (InvalidId, TypeError):
            return None
        doc = await self.col.find_one({"_id": oid})
        return _trip_from_doc(doc) if doc else None

    async def get_by_id_and_user(self, trip_id: str, user_id: str) -> Optional[dict]:
        try:
            trip_oid = ObjectId(trip_id)
            user_oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        doc = await self.col.find_one({"_id": trip_oid, "user_id": user_oid})
        return _trip_from_doc(doc) if doc else None

    async def list_by_user(self, user_id: str) -> List[dict]:
        try:
            user_oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return []
        cursor = self.col.find({"user_id": user_oid}).sort("updated_at", -1)
        docs = await cursor.to_list(length=100)
        return [_trip_from_doc(d) for d in docs]

    async def create(
        self,
        user_id: str,
        title: str,
        destination_id: str,
        start_date: str,
        end_date: str,
        num_days: int,
        budget: int = 30000,
        adults: int = 2,
        children: int = 0,
        mode: str = "live"
    ) -> dict:
        try:
            user_oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            raise ValueError(f"Invalid user_id: {user_id}")

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
        result = await self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _trip_from_doc(doc)

    async def update_version_pointer(self, trip_id: str, version: int) -> Optional[dict]:
        try:
            oid = ObjectId(trip_id)
        except (InvalidId, TypeError):
            return None
        now = datetime.now(timezone.utc)
        await self.col.update_one(
            {"_id": oid},
            {"$set": {"current_version": version, "updated_at": now}}
        )
        return await self.get_by_id(trip_id)

    async def delete(self, trip_id: str) -> bool:
        try:
            oid = ObjectId(trip_id)
        except (InvalidId, TypeError):
            return False
        result = await self.col.delete_one({"_id": oid})
        return result.deleted_count > 0
