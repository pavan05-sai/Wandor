"""
MongoDB repositories for Expense, Notification, Share, Event, Chat, and Cache.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from bson import ObjectId
from app.db.mongodb import get_db
from app.repositories.base import EntityDoc, to_id_filter, to_object_id


# ---------------------------------------------------------------------------
# ExpenseRepository
# ---------------------------------------------------------------------------
class ExpenseRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.expenses

    def create(
        self,
        trip_id: Union[str, int, ObjectId],
        category: str,
        amount: int,
        day_id: Optional[str] = None,
        note: Optional[str] = None
    ) -> EntityDoc:
        trip_oid = to_object_id(trip_id) or str(trip_id)
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": trip_oid,
            "category": category,
            "amount": int(amount),
            "day_id": day_id,
            "note": note,
            "spent_at": now,
        }
        res = self.col.insert_one(doc)
        doc["_id"] = res.inserted_id
        doc["id"] = str(res.inserted_id)
        doc["trip_id"] = str(trip_oid)
        return EntityDoc(doc)

    def list_by_trip(self, trip_id: Union[str, int, ObjectId]) -> List[EntityDoc]:
        flt = to_id_filter(trip_id, id_field="trip_id", sqlite_field="sqlite_trip_id")
        docs = list(self.col.find(flt).sort("spent_at", -1))
        out = []
        for d in docs:
            item = dict(d)
            item["id"] = str(d["_id"])
            item["trip_id"] = str(d.get("trip_id", ""))
            out.append(EntityDoc(item))
        return out


# ---------------------------------------------------------------------------
# NotificationRepository
# ---------------------------------------------------------------------------
class NotificationRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.notifications

    def create(
        self,
        user_id: Union[str, int, ObjectId],
        type: str,
        title: str,
        body: str,
        severity: str = "info",
        trip_id: Optional[Union[str, int, ObjectId]] = None
    ) -> EntityDoc:
        user_oid = to_object_id(user_id) or str(user_id)
        trip_oid = (to_object_id(trip_id) or str(trip_id)) if trip_id else None

        user_flt = to_id_filter(user_id, id_field="user_id", sqlite_field="sqlite_user_id")
        dedupe_query = {
            "$and": [
                user_flt,
                {"type": type, "title": title}
            ]
        }
        if trip_id:
            trip_flt = to_id_filter(trip_id, id_field="trip_id", sqlite_field="sqlite_trip_id")
            dedupe_query["$and"].append(trip_flt)

        existing = self.col.find_one(dedupe_query)
        if existing:
            item = dict(existing)
            item["id"] = str(existing["_id"])
            return EntityDoc(item)

        now = datetime.now(timezone.utc)
        doc = {
            "user_id": user_oid,
            "trip_id": trip_oid,
            "type": type,
            "title": title,
            "body": body,
            "severity": severity,
            "read": False,
            "created_at": now,
        }
        res = self.col.insert_one(doc)
        doc["_id"] = res.inserted_id
        doc["id"] = str(res.inserted_id)
        doc["user_id"] = str(user_oid)
        if trip_oid:
            doc["trip_id"] = str(trip_oid)
        return EntityDoc(doc)

    def list_by_user(
        self, user_id: Union[str, int, ObjectId], unread_only: bool = False
    ) -> List[EntityDoc]:
        user_flt = to_id_filter(user_id, id_field="user_id", sqlite_field="sqlite_user_id")
        query: Dict[str, Any] = user_flt
        if unread_only:
            query = {"$and": [user_flt, {"read": False}]}

        docs = list(self.col.find(query).sort("created_at", -1))
        out = []
        for d in docs:
            item = dict(d)
            item["id"] = str(d["_id"])
            item["user_id"] = str(d.get("user_id", ""))
            if d.get("trip_id"):
                item["trip_id"] = str(d["trip_id"])
            out.append(EntityDoc(item))
        return out

    def mark_read(
        self, notification_id: Union[str, int, ObjectId], user_id: Union[str, int, ObjectId]
    ) -> bool:
        notif_flt = to_id_filter(notification_id)
        user_flt = to_id_filter(user_id, id_field="user_id", sqlite_field="sqlite_user_id")
        flt = {"$and": [notif_flt, user_flt]}
        res = self.col.update_one(flt, {"$set": {"read": True}})
        return res.modified_count > 0 or res.matched_count > 0


# ---------------------------------------------------------------------------
# ShareRepository
# ---------------------------------------------------------------------------
class ShareRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.trip_shares

    def create(
        self,
        trip_id: Union[str, int, ObjectId],
        token: str,
        expires_at: Optional[datetime] = None,
        version_pinned: Optional[int] = None
    ) -> EntityDoc:
        trip_oid = to_object_id(trip_id) or str(trip_id)
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": trip_oid,
            "token": token,
            "expires_at": expires_at,
            "version_pinned": version_pinned,
            "revoked": False,
            "created_at": now,
        }
        res = self.col.insert_one(doc)
        doc["_id"] = res.inserted_id
        doc["id"] = str(res.inserted_id)
        doc["trip_id"] = str(trip_oid)
        return EntityDoc(doc)

    def get_by_token(self, token: str) -> Optional[EntityDoc]:
        doc = self.col.find_one({"token": token, "revoked": False})
        if not doc:
            return None
        item = dict(doc)
        item["id"] = str(doc["_id"])
        item["trip_id"] = str(doc.get("trip_id", ""))
        return EntityDoc(item)

    def revoke_by_trip(self, trip_id: Union[str, int, ObjectId]) -> None:
        flt = to_id_filter(trip_id, id_field="trip_id", sqlite_field="sqlite_trip_id")
        self.col.update_many(flt, {"$set": {"revoked": True}})


# ---------------------------------------------------------------------------
# EventRepository
# ---------------------------------------------------------------------------
class EventRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.travel_events

    def create(
        self,
        trip_id: Union[str, int, ObjectId],
        type: str,
        day_id: Optional[str] = None,
        severity: str = "info",
        detail: str = "",
        source: str = "system",
        payload: Optional[Dict[str, Any]] = None,
        handled_version: Optional[int] = None
    ) -> EntityDoc:
        trip_oid = to_object_id(trip_id) or str(trip_id)
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": trip_oid,
            "type": type,
            "day_id": day_id,
            "severity": severity,
            "detail": detail,
            "source": source,
            "payload": payload,
            "handled_version": handled_version,
            "created_at": now,
        }
        res = self.col.insert_one(doc)
        doc["_id"] = res.inserted_id
        doc["id"] = str(res.inserted_id)
        doc["trip_id"] = str(trip_oid)
        return EntityDoc(doc)

    def list_by_trip(self, trip_id: Union[str, int, ObjectId]) -> List[EntityDoc]:
        flt = to_id_filter(trip_id, id_field="trip_id", sqlite_field="sqlite_trip_id")
        docs = list(self.col.find(flt).sort("created_at", 1))
        out = []
        for d in docs:
            item = dict(d)
            item["id"] = str(d["_id"])
            item["trip_id"] = str(d.get("trip_id", ""))
            out.append(EntityDoc(item))
        return out

    def mark_handled(self, event_id: Union[str, int, ObjectId], handled_version: int) -> bool:
        flt = to_id_filter(event_id)
        res = self.col.update_one(flt, {"$set": {"handled_version": int(handled_version)}})
        return res.modified_count > 0 or res.matched_count > 0


# ---------------------------------------------------------------------------
# ChatRepository
# ---------------------------------------------------------------------------
class ChatRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.chat_messages

    def create(
        self,
        trip_id: Union[str, int, ObjectId],
        role: str,
        content: str,
        intent: Optional[str] = None,
        version_before: Optional[int] = None,
        version_after: Optional[int] = None
    ) -> EntityDoc:
        trip_oid = to_object_id(trip_id) or str(trip_id)
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": trip_oid,
            "role": role,
            "content": content,
            "intent": intent,
            "version_before": version_before,
            "version_after": version_after,
            "created_at": now,
        }
        res = self.col.insert_one(doc)
        doc["_id"] = res.inserted_id
        doc["id"] = str(res.inserted_id)
        doc["trip_id"] = str(trip_oid)
        return EntityDoc(doc)

    add_message = create

    def list_by_trip(self, trip_id: Union[str, int, ObjectId]) -> List[EntityDoc]:
        return self.get_history(trip_id, limit=100)

    def get_history(self, trip_id: Union[str, int, ObjectId], limit: int = 50) -> List[EntityDoc]:
        flt = to_id_filter(trip_id, id_field="trip_id", sqlite_field="sqlite_trip_id")
        docs = list(self.col.find(flt).sort("created_at", 1).limit(limit))
        out = []
        for d in docs:
            item = dict(d)
            item["id"] = str(d["_id"])
            item["trip_id"] = str(d.get("trip_id", ""))
            out.append(EntityDoc(item))
        return out


# ---------------------------------------------------------------------------
# CacheRepository
# ---------------------------------------------------------------------------
class CacheRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        self.col = self.db.api_cache

    def get(self, key: str, provider: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve cached value by key.

        Args:
            key: The cache key (e.g. "weather:dest_goa:15.50:73.80:4").
            provider: Optional provider filter. If not supplied, the provider
                      is extracted from the key prefix (text before the first ':').

        Returns:
            Dict with 'value' and 'stale' keys, or None if not found.
        """
        if provider is None:
            provider = key.split(":")[0] if ":" in key else "unknown"

        doc = self.col.find_one({"key": key})
        if not doc:
            return None

        stale = False
        expires_at = doc.get("expires_at")
        if expires_at and isinstance(expires_at, datetime):
            now = datetime.now(timezone.utc)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now > expires_at:
                stale = True

        raw_value = doc.get("response_json") or doc.get("value_json")
        if raw_value is None:
            return None

        return {"value": raw_value, "stale": stale}

    def set(
        self, key: str, provider: str = "unknown",
        value: Any = None, value_json: Any = None,
        ttl_seconds: int = 86400
    ) -> None:
        from datetime import timedelta
        payload = value_json if value_json is not None else value
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        doc = {
            "key": key,
            "provider": provider,
            "response_json": payload,
            "fetched_at": now,
            "ttl_seconds": ttl_seconds,
            "expires_at": expires_at,
        }
        self.col.update_one({"key": key}, {"$set": doc}, upsert=True)
