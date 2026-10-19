"""
MongoDB repository for ItineraryVersion operations.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger

logger = get_logger("version_repo_mongo")


def _version_from_doc(doc: dict) -> dict:
    if not doc:
        return {}
    return {
        "id": str(doc["_id"]),
        "trip_id": str(doc.get("trip_id", "")),
        "version": doc.get("version", 1),
        "parent_version": doc.get("parent_version"),
        "json": doc.get("json", {}),
        "created_by": doc.get("created_by", "unknown"),
        "change_summary": doc.get("change_summary", ""),
        "change_set_json": doc.get("change_set_json"),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
    }


class VersionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.col = db.itinerary_versions

    async def get_by_version(self, trip_id: str, version: int) -> Optional[dict]:
        try:
            trip_oid = ObjectId(trip_id)
        except (InvalidId, TypeError):
            return None
        doc = await self.col.find_one({"trip_id": trip_oid, "version": version})
        return _version_from_doc(doc) if doc else None

    async def get_latest(self, trip_id: str) -> Optional[dict]:
        try:
            trip_oid = ObjectId(trip_id)
        except (InvalidId, TypeError):
            return None
        cursor = self.col.find({"trip_id": trip_oid}).sort("version", -1).limit(1)
        docs = await cursor.to_list(length=1)
        return _version_from_doc(docs[0]) if docs else None

    async def list_by_trip(self, trip_id: str) -> List[dict]:
        try:
            trip_oid = ObjectId(trip_id)
        except (InvalidId, TypeError):
            return []
        cursor = self.col.find({"trip_id": trip_oid}).sort("version", 1)
        docs = await cursor.to_list(length=500)
        return [_version_from_doc(d) for d in docs]

    async def create(
        self,
        trip_id: str,
        version: int,
        json_data: Dict[str, Any],
        created_by: str,
        change_summary: str,
        parent_version: Optional[int] = None,
        change_set_json: Optional[Dict[str, Any]] = None
    ) -> dict:
        try:
            trip_oid = ObjectId(trip_id)
        except (InvalidId, TypeError):
            raise ValueError(f"Invalid trip_id: {trip_id}")

        # Upsert to handle idempotent generation (regenerate same version)
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": trip_oid,
            "version": version,
            "parent_version": parent_version,
            "json": json_data,
            "created_by": created_by,
            "change_summary": change_summary,
            "change_set_json": change_set_json,
            "created_at": now,
        }
        # Use upsert on trip_id + version to prevent duplicate version errors
        result = await self.col.update_one(
            {"trip_id": trip_oid, "version": version},
            {"$set": doc},
            upsert=True
        )
        if result.upserted_id:
            doc["_id"] = result.upserted_id
        else:
            # Fetch the existing doc
            existing = await self.col.find_one({"trip_id": trip_oid, "version": version})
            if existing:
                doc["_id"] = existing["_id"]
        return _version_from_doc(doc)
