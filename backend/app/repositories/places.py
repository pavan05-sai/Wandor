"""
MongoDB repository for Place operations.
"""
from typing import Any, Dict, List, Optional
from pymongo import UpdateOne
from app.db.mongodb import get_db
from app.repositories.base import EntityDoc


def _place_from_doc(doc: Optional[dict]) -> Optional[EntityDoc]:
    if not doc:
        return None
    d = dict(doc)
    d["id"] = d.get("place_id", str(doc.get("_id", "")))
    return EntityDoc(d)


class PlaceRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.places

    def get_by_id(self, place_id: str) -> Optional[EntityDoc]:
        doc = self.col.find_one({"$or": [{"place_id": place_id}, {"id": place_id}]})
        return _place_from_doc(doc)

    def list_by_destination(
        self,
        destination_id: str,
        kind: Optional[str] = None,
        category: Optional[str] = None,
        indoor: Optional[bool] = None,
        max_cost: Optional[int] = None
    ) -> List[EntityDoc]:
        query: Dict[str, Any] = {"destination_id": destination_id}
        if kind:
            query["kind"] = kind
        if category:
            query["category"] = category
        if indoor is not None:
            query["indoor"] = bool(indoor)
        if max_cost is not None:
            query["cost_amount"] = {"$lte": int(max_cost)}

        docs = list(self.col.find(query))
        return [_place_from_doc(d) for d in docs if d]

    def bulk_create_or_update(self, places_data: List[dict]) -> None:
        if not places_data:
            return
        ops = []
        for p in places_data:
            place_id = p.get("id") or p.get("place_id")
            if not place_id:
                continue
            doc = dict(p)
            doc["place_id"] = place_id
            doc.pop("_id", None)
            ops.append(
                UpdateOne(
                    {"$or": [{"place_id": place_id}, {"id": place_id}]},
                    {"$set": doc},
                    upsert=True
                )
            )
        if ops:
            self.col.bulk_write(ops, ordered=False)
