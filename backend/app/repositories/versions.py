"""
MongoDB repository for ItineraryVersion operations.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from bson import ObjectId
from app.db.mongodb import get_db
from app.repositories.base import EntityDoc, to_id_filter, to_object_id


def _version_from_doc(doc: Optional[dict]) -> Optional[EntityDoc]:
    if not doc:
        return None
    d = dict(doc)
    d["id"] = str(doc["_id"])
    d["trip_id"] = str(doc.get("trip_id", ""))
    d["version"] = doc.get("version", 1)
    d["parent_version"] = doc.get("parent_version")
    d["json"] = doc.get("json", {})
    d["created_by"] = doc.get("created_by", "unknown")
    d["change_summary"] = doc.get("change_summary", "")
    d["change_set_json"] = doc.get("change_set_json")
    d["created_at"] = doc.get("created_at") or datetime.now(timezone.utc)
    return EntityDoc(d)


class VersionRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.itinerary_versions

    def _trip_flt(self, trip_id: Union[str, int, ObjectId]) -> Dict[str, Any]:
        return to_id_filter(trip_id, id_field="trip_id", sqlite_field="sqlite_trip_id")

    def get_by_version(
        self, trip_id: Union[str, int, ObjectId], version: int
    ) -> Optional[EntityDoc]:
        trip_flt = self._trip_flt(trip_id)
        flt = {"$and": [trip_flt, {"version": int(version)}]}
        doc = self.col.find_one(flt)
        return _version_from_doc(doc)

    def get_latest(self, trip_id: Union[str, int, ObjectId]) -> Optional[EntityDoc]:
        trip_flt = self._trip_flt(trip_id)
        doc = self.col.find_one(trip_flt, sort=[("version", -1)])
        return _version_from_doc(doc)

    def list_by_trip(self, trip_id: Union[str, int, ObjectId]) -> List[EntityDoc]:
        trip_flt = self._trip_flt(trip_id)
        docs = list(self.col.find(trip_flt).sort("version", 1))
        return [_version_from_doc(d) for d in docs if d]

    def create(
        self,
        trip_id: Union[str, int, ObjectId],
        version: int,
        json_data: Dict[str, Any],
        created_by: str,
        change_summary: str,
        parent_version: Optional[int] = None,
        change_set_json: Optional[Dict[str, Any]] = None
    ) -> EntityDoc:
        trip_oid = to_object_id(trip_id) or str(trip_id)
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": trip_oid,
            "version": int(version),
            "parent_version": int(parent_version) if parent_version is not None else None,
            "json": json_data,
            "created_by": created_by,
            "change_summary": change_summary,
            "change_set_json": change_set_json,
            "created_at": now,
        }
        # Upsert by trip_id + version
        trip_flt = self._trip_flt(trip_id)
        flt = {"$and": [trip_flt, {"version": int(version)}]}
        self.col.update_one(flt, {"$set": doc}, upsert=True)
        saved = self.col.find_one(flt)
        return _version_from_doc(saved or doc)
