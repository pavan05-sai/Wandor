"""
MongoDB repositories for Expense, Notification, Share, Event, Chat, Cache.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger

logger = get_logger("entity_repos_mongo")


def _to_id(v: str) -> Optional[ObjectId]:
    try:
        return ObjectId(v)
    except (InvalidId, TypeError):
        return None


# ---------------------------------------------------------------------------
# ExpenseRepository
# ---------------------------------------------------------------------------
class ExpenseRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.expenses

    async def create(self, trip_id: str, category: str, amount: int,
                     day_id: Optional[str] = None, note: Optional[str] = None) -> dict:
        oid = _to_id(trip_id)
        if not oid:
            raise ValueError(f"Invalid trip_id: {trip_id}")
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": oid,
            "category": category,
            "amount": amount,
            "day_id": day_id,
            "note": note,
            "spent_at": now,
        }
        result = await self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _expense_from_doc(doc)

    async def list_by_trip(self, trip_id: str) -> List[dict]:
        oid = _to_id(trip_id)
        if not oid:
            return []
        cursor = self.col.find({"trip_id": oid}).sort("spent_at", -1)
        docs = await cursor.to_list(length=500)
        return [_expense_from_doc(d) for d in docs]


def _expense_from_doc(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "trip_id": str(doc.get("trip_id", "")),
        "day_id": doc.get("day_id"),
        "category": doc.get("category", "misc"),
        "amount": doc.get("amount", 0),
        "note": doc.get("note"),
        "spent_at": doc.get("spent_at", datetime.now(timezone.utc)),
    }


# ---------------------------------------------------------------------------
# NotificationRepository
# ---------------------------------------------------------------------------
class NotificationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.notifications

    async def create(self, user_id: str, type: str, title: str, body: str,
                     severity: str = "info", trip_id: Optional[str] = None) -> dict:
        user_oid = _to_id(user_id)
        trip_oid = _to_id(trip_id) if trip_id else None
        if not user_oid:
            raise ValueError(f"Invalid user_id: {user_id}")

        # Dedupe: same user, trip, type, title
        existing = await self.col.find_one({
            "user_id": user_oid,
            "trip_id": trip_oid,
            "type": type,
            "title": title,
        })
        if existing:
            return _notif_from_doc(existing)

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
        result = await self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _notif_from_doc(doc)

    async def list_by_user(self, user_id: str, unread_only: bool = False) -> List[dict]:
        user_oid = _to_id(user_id)
        if not user_oid:
            return []
        filt: Dict[str, Any] = {"user_id": user_oid}
        if unread_only:
            filt["read"] = False
        cursor = self.col.find(filt).sort("created_at", -1).limit(50)
        docs = await cursor.to_list(length=50)
        return [_notif_from_doc(d) for d in docs]

    async def mark_read(self, notification_id: str, user_id: str) -> bool:
        nid = _to_id(notification_id)
        uid = _to_id(user_id)
        if not nid or not uid:
            return False
        result = await self.col.update_one(
            {"_id": nid, "user_id": uid},
            {"$set": {"read": True}}
        )
        return result.modified_count > 0


def _notif_from_doc(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc.get("user_id", "")),
        "trip_id": str(doc["trip_id"]) if doc.get("trip_id") else None,
        "type": doc.get("type", "info"),
        "title": doc.get("title", ""),
        "body": doc.get("body", ""),
        "severity": doc.get("severity", "info"),
        "read": doc.get("read", False),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
    }


# ---------------------------------------------------------------------------
# ShareRepository
# ---------------------------------------------------------------------------
class ShareRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.trip_shares

    async def create(self, trip_id: str, token: str,
                     expires_at: Optional[datetime] = None,
                     version_pinned: Optional[int] = None) -> dict:
        trip_oid = _to_id(trip_id)
        if not trip_oid:
            raise ValueError(f"Invalid trip_id: {trip_id}")
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": trip_oid,
            "token": token,
            "expires_at": expires_at,
            "version_pinned": version_pinned,
            "revoked": False,
            "created_at": now,
        }
        await self.col.insert_one(doc)
        return _share_from_doc(doc)

    async def get_by_token(self, token: str) -> Optional[dict]:
        doc = await self.col.find_one({"token": token, "revoked": False})
        return _share_from_doc(doc) if doc else None

    async def revoke_by_trip(self, trip_id: str):
        trip_oid = _to_id(trip_id)
        if trip_oid:
            await self.col.update_many({"trip_id": trip_oid}, {"$set": {"revoked": True}})


def _share_from_doc(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "trip_id": str(doc.get("trip_id", "")),
        "token": doc.get("token", ""),
        "expires_at": doc.get("expires_at"),
        "version_pinned": doc.get("version_pinned"),
        "revoked": doc.get("revoked", False),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
    }


# ---------------------------------------------------------------------------
# EventRepository
# ---------------------------------------------------------------------------
class EventRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.travel_events

    async def create(self, trip_id: str, type: str, day_id: Optional[str],
                     severity: str, payload: dict, source: str = "simulated") -> dict:
        trip_oid = _to_id(trip_id)
        if not trip_oid:
            raise ValueError(f"Invalid trip_id: {trip_id}")
        now = datetime.now(timezone.utc)
        doc = {
            "trip_id": trip_oid,
            "type": type,
            "day_id": day_id,
            "severity": severity,
            "payload": payload,
            "source": source,
            "handled_version": None,
            "created_at": now,
        }
        result = await self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _event_from_doc(doc)

    async def list_by_trip(self, trip_id: str) -> List[dict]:
        trip_oid = _to_id(trip_id)
        if not trip_oid:
            return []
        cursor = self.col.find({"trip_id": trip_oid}).sort("created_at", -1)
        docs = await cursor.to_list(length=100)
        return [_event_from_doc(d) for d in docs]

    async def mark_handled(self, event_id: str, version: int):
        eid = _to_id(event_id)
        if eid:
            await self.col.update_one({"_id": eid}, {"$set": {"handled_version": version}})


def _event_from_doc(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "trip_id": str(doc.get("trip_id", "")),
        "type": doc.get("type", ""),
        "day_id": doc.get("day_id"),
        "severity": doc.get("severity", "medium"),
        "payload": doc.get("payload", {}),
        "source": doc.get("source", "simulated"),
        "handled_version": doc.get("handled_version"),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
    }


# ---------------------------------------------------------------------------
# ChatRepository
# ---------------------------------------------------------------------------
class ChatRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.chat_messages

    async def add_message(self, trip_id: str, role: str, content: str,
                          intent: Optional[str] = None,
                          version_before: Optional[int] = None,
                          version_after: Optional[int] = None) -> dict:
        trip_oid = _to_id(trip_id)
        if not trip_oid:
            raise ValueError(f"Invalid trip_id: {trip_id}")
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
        result = await self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _chat_from_doc(doc)

    async def get_history(self, trip_id: str, limit: int = 10) -> List[dict]:
        trip_oid = _to_id(trip_id)
        if not trip_oid:
            return []
        cursor = self.col.find({"trip_id": trip_oid}).sort("created_at", 1)
        docs = await cursor.to_list(length=1000)
        return [_chat_from_doc(d) for d in docs[-limit:]]


def _chat_from_doc(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "trip_id": str(doc.get("trip_id", "")),
        "role": doc.get("role", "user"),
        "content": doc.get("content", ""),
        "intent": doc.get("intent"),
        "version_before": doc.get("version_before"),
        "version_after": doc.get("version_after"),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
    }


# ---------------------------------------------------------------------------
# CacheRepository
# ---------------------------------------------------------------------------
class CacheRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.api_cache

    async def get(self, key: str) -> Optional[dict]:
        doc = await self.col.find_one({"key": key})
        if not doc:
            return None
        now = datetime.now(timezone.utc)
        fetched_at = doc.get("fetched_at", now)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        age_seconds = (now - fetched_at).total_seconds()
        is_stale = age_seconds > doc.get("ttl_seconds", 86400)
        return {
            "value": doc.get("value_json"),
            "stale": is_stale,
            "age_seconds": age_seconds,
            "fetched_at": fetched_at.isoformat(),
        }

    async def set(self, key: str, provider: str, value_json: Any, ttl_seconds: int = 86400):
        now = datetime.now(timezone.utc)
        await self.col.update_one(
            {"key": key},
            {"$set": {
                "key": key,
                "provider": provider,
                "value_json": value_json,
                "fetched_at": now,
                "ttl_seconds": ttl_seconds,
            }},
            upsert=True
        )
