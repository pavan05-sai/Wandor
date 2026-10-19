"""
Migration script: SQLite (travel_planner.db) -> MongoDB (wandor)
Migrates all users, preferences, places, trips, itinerary versions, expenses,
notifications, trip shares, events, chat messages, and cache into MongoDB.
"""
import os
import sys
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING, IndexModel

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings


def parse_json_safe(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return val


def parse_datetime_safe(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        return val


def run_migration():
    sqlite_path = backend_dir / "travel_planner.db"
    if not sqlite_path.exists():
        sqlite_path = backend_dir.parent / "travel_planner.db"
    if not sqlite_path.exists():
        print(f"Error: SQLite database not found at {sqlite_path}")
        return False

    print(f"Reading SQLite database from: {sqlite_path}")
    con = sqlite3.connect(str(sqlite_path))
    con.row_factory = sqlite3.Row

    mongo_uri = settings.MONGODB_URI or "mongodb://localhost:27017"
    db_name = settings.MONGODB_DB_NAME or "wandor"
    print(f"Connecting to MongoDB at: {mongo_uri}, database: {db_name}")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[db_name]

    # Test connection
    client.admin.command("ping")
    print("Connected to MongoDB successfully.")

    # 1. Migrate Users & User Preferences
    user_rows = con.execute("SELECT * FROM users").fetchall()
    pref_rows = con.execute("SELECT * FROM user_preferences").fetchall()
    pref_by_user = {}
    for p in pref_rows:
        p_dict = dict(p)
        pref_by_user[p_dict["user_id"]] = {
            "interests": parse_json_safe(p_dict.get("interests")) or [],
            "pace": p_dict.get("pace") or "relaxed",
            "budget_level": p_dict.get("budget_level") or "mid",
            "transport_modes": parse_json_safe(p_dict.get("transport_modes")) or ["taxi", "walk"],
            "accommodation_type": p_dict.get("accommodation_type") or "hotel",
            "dietary": parse_json_safe(p_dict.get("dietary")) or [],
            "avoid": parse_json_safe(p_dict.get("avoid")) or [],
            "mobility": p_dict.get("mobility") or "standard",
            "home_city": p_dict.get("home_city"),
            "updated_at": parse_datetime_safe(p_dict.get("updated_at")) or datetime.now(timezone.utc),
        }

    user_id_map = {}  # sqlite_user_id -> ObjectId
    for u in user_rows:
        u_dict = dict(u)
        old_id = u_dict["id"]
        # Check if already exists in mongo
        existing = db.users.find_one({"email": u_dict["email"].lower().strip()})
        if existing:
            new_id = existing["_id"]
            user_id_map[old_id] = new_id
            db.users.update_one(
                {"_id": new_id},
                {"$set": {
                    "sqlite_id": old_id,
                    "preferences": pref_by_user.get(old_id, {})
                }}
            )
        else:
            new_id = ObjectId()
            user_id_map[old_id] = new_id
            user_doc = {
                "_id": new_id,
                "sqlite_id": old_id,
                "email": u_dict["email"].lower().strip(),
                "password_hash": u_dict["password_hash"],
                "display_name": u_dict["display_name"],
                "created_at": parse_datetime_safe(u_dict.get("created_at")) or datetime.now(timezone.utc),
                "preferences": pref_by_user.get(old_id, {})
            }
            db.users.insert_one(user_doc)
    print(f"Migrated {len(user_rows)} users (with preferences).")

    # 2. Migrate Places
    place_rows = con.execute("SELECT * FROM places").fetchall()
    places_migrated = 0
    for p in place_rows:
        p_dict = dict(p)
        place_id = p_dict["id"]
        doc = {
            "place_id": place_id,
            "destination_id": p_dict.get("destination_id"),
            "name": p_dict.get("name"),
            "kind": p_dict.get("kind"),
            "category": p_dict.get("category"),
            "lat": float(p_dict["lat"]) if p_dict.get("lat") is not None else 0.0,
            "lng": float(p_dict["lng"]) if p_dict.get("lng") is not None else 0.0,
            "description": p_dict.get("description", ""),
            "rating": float(p_dict["rating"]) if p_dict.get("rating") is not None else 4.0,
            "cost_amount": int(p_dict["cost_amount"]) if p_dict.get("cost_amount") is not None else 0,
            "cost_per": p_dict.get("cost_per", "person"),
            "duration_min": int(p_dict["duration_min"]) if p_dict.get("duration_min") is not None else 60,
            "open_from": p_dict.get("open_from", "09:00"),
            "open_to": p_dict.get("open_to", "18:00"),
            "closed_days": parse_json_safe(p_dict.get("closed_days")) or [],
            "indoor": bool(p_dict.get("indoor", False)),
            "source": p_dict.get("source", "seed"),
            "verified": bool(p_dict.get("verified", True)),
            "booking_url": p_dict.get("booking_url"),
            "tags": parse_json_safe(p_dict.get("tags")) or [],
        }
        db.places.update_one({"place_id": place_id}, {"$set": doc}, upsert=True)
        places_migrated += 1
    print(f"Migrated {places_migrated} places.")

    # 3. Migrate Trips
    trip_rows = con.execute("SELECT * FROM trips").fetchall()
    trip_id_map = {}  # sqlite_trip_id -> ObjectId
    for t in trip_rows:
        t_dict = dict(t)
        old_id = t_dict["id"]
        old_user_id = t_dict["user_id"]
        new_user_id = user_id_map.get(old_user_id)
        if not new_user_id:
            # Fallback to demo user if missing
            demo_user = db.users.find_one({"email": "demo@tripplanner.ai"})
            new_user_id = demo_user["_id"] if demo_user else ObjectId()

        existing = db.trips.find_one({"sqlite_id": old_id})
        if existing:
            new_id = existing["_id"]
            trip_id_map[old_id] = new_id
        else:
            new_id = ObjectId()
            trip_id_map[old_id] = new_id
            trip_doc = {
                "_id": new_id,
                "sqlite_id": old_id,
                "user_id": new_user_id,
                "sqlite_user_id": old_user_id,
                "title": t_dict["title"],
                "destination_id": t_dict["destination_id"],
                "start_date": t_dict["start_date"],
                "end_date": t_dict["end_date"],
                "num_days": int(t_dict.get("num_days", 1)),
                "budget": int(t_dict.get("budget", 30000)),
                "adults": int(t_dict.get("adults", 2)),
                "children": int(t_dict.get("children", 0)),
                "status": t_dict.get("status", "active"),
                "current_version": int(t_dict.get("current_version", 0)),
                "mode": t_dict.get("mode", "live"),
                "created_at": parse_datetime_safe(t_dict.get("created_at")) or datetime.now(timezone.utc),
                "updated_at": parse_datetime_safe(t_dict.get("updated_at")) or datetime.now(timezone.utc),
            }
            db.trips.insert_one(trip_doc)
    print(f"Migrated {len(trip_rows)} trips.")

    # 4. Migrate Itinerary Versions
    ver_rows = con.execute("SELECT * FROM itinerary_versions").fetchall()
    ver_migrated = 0
    for v in ver_rows:
        v_dict = dict(v)
        old_trip_id = v_dict["trip_id"]
        new_trip_id = trip_id_map.get(old_trip_id)
        if not new_trip_id:
            continue
        v_num = int(v_dict["version"])
        doc = {
            "sqlite_id": v_dict["id"],
            "trip_id": new_trip_id,
            "sqlite_trip_id": old_trip_id,
            "version": v_num,
            "parent_version": int(v_dict["parent_version"]) if v_dict.get("parent_version") is not None else None,
            "json": parse_json_safe(v_dict.get("json")) or {},
            "created_by": v_dict.get("created_by") or "unknown",
            "change_summary": v_dict.get("change_summary") or "",
            "change_set_json": parse_json_safe(v_dict.get("change_set_json")),
            "created_at": parse_datetime_safe(v_dict.get("created_at")) or datetime.now(timezone.utc),
        }
        db.itinerary_versions.update_one(
            {"trip_id": new_trip_id, "version": v_num},
            {"$set": doc},
            upsert=True
        )
        ver_migrated += 1
    print(f"Migrated {ver_migrated} itinerary versions.")

    # 5. Migrate Expenses
    exp_rows = con.execute("SELECT * FROM expenses").fetchall()
    exp_migrated = 0
    for e in exp_rows:
        e_dict = dict(e)
        old_trip_id = e_dict["trip_id"]
        new_trip_id = trip_id_map.get(old_trip_id)
        if not new_trip_id:
            continue
        doc = {
            "sqlite_id": e_dict["id"],
            "trip_id": new_trip_id,
            "sqlite_trip_id": old_trip_id,
            "day_id": e_dict.get("day_id"),
            "category": e_dict.get("category", "misc"),
            "amount": int(e_dict.get("amount", 0)),
            "note": e_dict.get("note"),
            "spent_at": parse_datetime_safe(e_dict.get("spent_at")) or datetime.now(timezone.utc),
        }
        db.expenses.update_one(
            {"sqlite_id": e_dict["id"]},
            {"$set": doc},
            upsert=True
        )
        exp_migrated += 1
    print(f"Migrated {exp_migrated} expenses.")

    # 6. Migrate Notifications
    notif_rows = con.execute("SELECT * FROM notifications").fetchall()
    notif_migrated = 0
    for n in notif_rows:
        n_dict = dict(n)
        old_user_id = n_dict["user_id"]
        new_user_id = user_id_map.get(old_user_id)
        if not new_user_id:
            continue
        old_trip_id = n_dict.get("trip_id")
        new_trip_id = trip_id_map.get(old_trip_id) if old_trip_id else None
        doc = {
            "sqlite_id": n_dict["id"],
            "user_id": new_user_id,
            "sqlite_user_id": old_user_id,
            "trip_id": new_trip_id,
            "sqlite_trip_id": old_trip_id,
            "type": n_dict.get("type", "system"),
            "title": n_dict.get("title", ""),
            "body": n_dict.get("body", ""),
            "severity": n_dict.get("severity", "info"),
            "read": bool(n_dict.get("read", False)),
            "created_at": parse_datetime_safe(n_dict.get("created_at")) or datetime.now(timezone.utc),
            "due_at": parse_datetime_safe(n_dict.get("due_at")),
        }
        db.notifications.update_one(
            {"sqlite_id": n_dict["id"]},
            {"$set": doc},
            upsert=True
        )
        notif_migrated += 1
    print(f"Migrated {notif_migrated} notifications.")

    # 7. Migrate Trip Shares
    share_rows = con.execute("SELECT * FROM trip_shares").fetchall()
    for s in share_rows:
        s_dict = dict(s)
        new_trip_id = trip_id_map.get(s_dict["trip_id"])
        if not new_trip_id:
            continue
        doc = {
            "sqlite_id": s_dict["id"],
            "trip_id": new_trip_id,
            "sqlite_trip_id": s_dict["trip_id"],
            "token": s_dict["token"],
            "expires_at": parse_datetime_safe(s_dict.get("expires_at")),
            "revoked": bool(s_dict.get("revoked", False)),
            "version_pinned": int(s_dict["version_pinned"]) if s_dict.get("version_pinned") is not None else None,
            "created_at": parse_datetime_safe(s_dict.get("created_at")) or datetime.now(timezone.utc),
        }
        db.trip_shares.update_one({"token": s_dict["token"]}, {"$set": doc}, upsert=True)
    print(f"Migrated {len(share_rows)} trip shares.")

    # 8. Migrate Travel Events
    event_rows = con.execute("SELECT * FROM travel_events").fetchall()
    for ev in event_rows:
        ev_dict = dict(ev)
        new_trip_id = trip_id_map.get(ev_dict["trip_id"])
        if not new_trip_id:
            continue
        doc = {
            "sqlite_id": ev_dict["id"],
            "trip_id": new_trip_id,
            "sqlite_trip_id": ev_dict["trip_id"],
            "type": ev_dict.get("type", "status"),
            "day_id": ev_dict.get("day_id"),
            "severity": ev_dict.get("severity", "info"),
            "payload": parse_json_safe(ev_dict.get("payload")) or ev_dict.get("payload"),
            "source": ev_dict.get("source", "system"),
            "handled_version": ev_dict.get("handled_version"),
            "created_at": parse_datetime_safe(ev_dict.get("created_at")) or datetime.now(timezone.utc),
        }
        db.travel_events.update_one({"sqlite_id": ev_dict["id"]}, {"$set": doc}, upsert=True)
    print(f"Migrated {len(event_rows)} travel events.")

    # 9. Migrate Chat Messages
    chat_rows = con.execute("SELECT * FROM chat_messages").fetchall()
    for c in chat_rows:
        c_dict = dict(c)
        new_trip_id = trip_id_map.get(c_dict["trip_id"])
        if not new_trip_id:
            continue
        doc = {
            "sqlite_id": c_dict["id"],
            "trip_id": new_trip_id,
            "sqlite_trip_id": c_dict["trip_id"],
            "role": c_dict.get("role", "user"),
            "content": c_dict.get("content", ""),
            "intent": c_dict.get("intent"),
            "version_before": c_dict.get("version_before"),
            "version_after": c_dict.get("version_after"),
            "created_at": parse_datetime_safe(c_dict.get("created_at")) or datetime.now(timezone.utc),
        }
        db.chat_messages.update_one({"sqlite_id": c_dict["id"]}, {"$set": doc}, upsert=True)
    print(f"Migrated {len(chat_rows)} chat messages.")

    # 10. Migrate API Cache
    cache_rows = con.execute("SELECT * FROM api_cache").fetchall()
    for ca in cache_rows:
        ca_dict = dict(ca)
        doc = {
            "key": ca_dict["key"],
            "provider": ca_dict["provider"],
            "response_json": parse_json_safe(ca_dict.get("value_json")),
            "fetched_at": parse_datetime_safe(ca_dict.get("fetched_at")),
            "ttl_seconds": ca_dict.get("ttl_seconds", 86400),
            "expires_at": datetime.now(timezone.utc),
        }
        db.api_cache.update_one({"key": ca_dict["key"]}, {"$set": doc}, upsert=True)
    print(f"Migrated {len(cache_rows)} api cache entries.")

    # 11. Create MongoDB Indexes
    print("Creating MongoDB indexes...")
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
        print("Indexes created successfully.")
    except Exception as e:
        print(f"Index creation note: {e}")

    con.close()
    client.close()
    print("Migration from SQLite to MongoDB completed successfully!")
    return True


if __name__ == "__main__":
    run_migration()
