"""
MongoDB repository for Place (catalog) operations.
Places use their own string IDs (e.g., "poi_goa_basilica") as primary keys,
stored in a "place_id" field alongside MongoDB _id.
"""
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger

logger = get_logger("place_repo_mongo")


def _place_from_doc(doc: dict) -> dict:
    """Return a plain dict representation of a place document."""
    d = dict(doc)
    d["id"] = doc.get("place_id", str(doc.get("_id", "")))
    d.pop("_id", None)
    return d


class PlaceRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.col = db.places

    async def list_by_destination(self, destination_id: str) -> List[dict]:
        cursor = self.col.find({"destination_id": destination_id})
        docs = await cursor.to_list(length=1000)
        return [_place_from_doc(d) for d in docs]

    async def get_by_id(self, place_id: str) -> Optional[dict]:
        doc = await self.col.find_one({"place_id": place_id})
        return _place_from_doc(doc) if doc else None

    async def bulk_create_or_update(self, places: List[Dict[str, Any]]):
        """Upsert places by their place_id field."""
        if not places:
            return
        from pymongo import UpdateOne
        ops = []
        for p in places:
            place_id = p.get("id") or p.get("place_id")
            if not place_id:
                continue
            doc = dict(p)
            doc["place_id"] = place_id
            doc.pop("id", None)
            ops.append(UpdateOne(
                {"place_id": place_id},
                {"$set": doc},
                upsert=True
            ))
        if ops:
            await self.col.bulk_write(ops, ordered=False)
