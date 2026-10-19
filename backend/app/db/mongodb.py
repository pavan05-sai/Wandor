"""
MongoDB connection management using PyMongo.
Provides database access for all repositories and FastAPI dependencies.
"""
import logging
from typing import Generator, Optional
from pymongo import MongoClient, ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database
from app.core.config import settings

logger = logging.getLogger("mongodb")

_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        connect_db()
    return _client


def get_db() -> Database:
    global _db
    if _db is None:
        connect_db()
    return _db


def db_dependency() -> Generator[Database, None, None]:
    """FastAPI dependency for yielding database session."""
    yield get_db()


def connect_db() -> Database:
    global _client, _db

    uri = settings.MONGODB_URI or "mongodb://localhost:27017"
    db_name = settings.MONGODB_DB_NAME or "wandor"

    if _client is not None and _db is not None:
        try:
            _client.admin.command("ping")
            return _db
        except Exception:
            _client = None
            _db = None

    logger.info(f"Connecting to MongoDB at {uri} (db: {db_name})...")
    _client = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=20000,
        maxPoolSize=50,
        minPoolSize=5,
    )

    try:
        _client.admin.command("ping")
    except Exception as e:
        _client = None
        _db = None
        raise RuntimeError(f"Failed to connect to MongoDB: {e}") from e

    _db = _client[db_name]
    logger.info(f"Connected to MongoDB database: {db_name}")
    _create_indexes(_db)
    return _db


def close_db() -> None:
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed.")


def init_db() -> None:
    """Initialize MongoDB connection and ensure indexes."""
    connect_db()


def _create_indexes(db: Database) -> None:
    try:
        db.users.create_indexes([
            IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email"),
            IndexModel([("sqlite_id", ASCENDING)], name="idx_users_sqlite_id"),
        ])
        db.trips.create_indexes([
            IndexModel([("user_id", ASCENDING)], name="idx_trips_user_id"),
            IndexModel([("sqlite_id", ASCENDING)], name="idx_trips_sqlite_id"),
            IndexModel([("destination_id", ASCENDING)], name="idx_trips_destination_id"),
            IndexModel([("updated_at", DESCENDING)], name="idx_trips_updated_at"),
        ])
        db.itinerary_versions.create_indexes([
            IndexModel([("trip_id", ASCENDING), ("version", ASCENDING)], unique=True, name="idx_versions_trip_version"),
            IndexModel([("trip_id", ASCENDING)], name="idx_versions_trip_id"),
            IndexModel([("sqlite_trip_id", ASCENDING)], name="idx_versions_sqlite_trip_id"),
        ])
        db.places.create_indexes([
            IndexModel([("place_id", ASCENDING)], unique=True, name="idx_places_place_id"),
            IndexModel([("destination_id", ASCENDING)], name="idx_places_destination_id"),
            IndexModel([("kind", ASCENDING)], name="idx_places_kind"),
        ])
        db.expenses.create_indexes([
            IndexModel([("trip_id", ASCENDING)], name="idx_expenses_trip_id"),
            IndexModel([("sqlite_trip_id", ASCENDING)], name="idx_expenses_sqlite_trip_id"),
            IndexModel([("spent_at", DESCENDING)], name="idx_expenses_spent_at"),
        ])
        db.notifications.create_indexes([
            IndexModel([("user_id", ASCENDING)], name="idx_notif_user_id"),
            IndexModel([("created_at", DESCENDING)], name="idx_notif_created_at"),
        ])
        db.trip_shares.create_indexes([
            IndexModel([("token", ASCENDING)], unique=True, name="idx_shares_token"),
            IndexModel([("trip_id", ASCENDING)], name="idx_shares_trip_id"),
        ])
        db.chat_messages.create_indexes([
            IndexModel([("trip_id", ASCENDING)], name="idx_chat_trip_id"),
            IndexModel([("created_at", ASCENDING)], name="idx_chat_created_at"),
        ])
        db.travel_events.create_indexes([
            IndexModel([("trip_id", ASCENDING)], name="idx_events_trip_id"),
        ])
        db.api_cache.create_indexes([
            IndexModel([("key", ASCENDING)], unique=True, name="idx_cache_key"),
            IndexModel([("provider", ASCENDING)], name="idx_cache_provider"),
        ])
    except Exception as e:
        logger.warning(f"Index creation notice: {e}")
