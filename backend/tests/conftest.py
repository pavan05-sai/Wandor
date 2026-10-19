"""
Pytest fixtures for the Wandor backend test suite.
Uses mongomock to provide an in-memory MongoDB instance so tests run
without a real MongoDB server.
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import mongomock

from app.core.security import create_access_token, hash_password
from app.models.database import get_db
from app.repositories.users import UserRepository
from app.services.catalog import CatalogService

# ---------------------------------------------------------------------------
# Global mongomock client and database used for the entire test session
# ---------------------------------------------------------------------------
_mock_client = mongomock.MongoClient()
_mock_db = _mock_client["wandor_test"]


def _get_mock_db():
    """Return the mongomock database for test use."""
    return _mock_db


def _get_mock_db_dep():
    """FastAPI dependency override that yields the mock database."""
    yield _mock_db


@pytest.fixture(scope="session", autouse=True)
def patch_mongodb_module():
    """
    Patch app.db.mongodb globals so every repository that calls get_db()
    transparently receives the mongomock database.  Also seeds the
    catalog places into the mock DB once.
    """
    import app.db.mongodb as mongo_mod

    # Save originals
    orig_client = mongo_mod._client
    orig_db = mongo_mod._db
    orig_get_db = mongo_mod.get_db
    orig_connect = mongo_mod.connect_db

    # Override with mock
    mongo_mod._client = _mock_client
    mongo_mod._db = _mock_db
    mongo_mod.get_db = _get_mock_db
    mongo_mod.connect_db = lambda: _mock_db

    # Seed catalog places into the mock database
    CatalogService.load_seed_to_db(_mock_db)

    # Use deterministic replay mode in tests so they run hermetically and reliably
    from app.core.config import settings
    orig_llm_provider = settings.LLM_PROVIDER
    orig_demo_mode = settings.DEMO_MODE
    settings.LLM_PROVIDER = "replay"
    settings.DEMO_MODE = "on"

    yield

    # Restore originals
    settings.LLM_PROVIDER = orig_llm_provider
    settings.DEMO_MODE = orig_demo_mode
    mongo_mod._client = orig_client
    mongo_mod._db = orig_db
    mongo_mod.get_db = orig_get_db
    mongo_mod.connect_db = orig_connect


# ---------------------------------------------------------------------------
# Per-test isolation: drop user-facing collections between tests so tests
# don't leak state across each other.
# ---------------------------------------------------------------------------
_TRANSIENT_COLLECTIONS = [
    "users", "trips", "itinerary_versions", "expenses",
    "notifications", "trip_shares", "travel_events", "chat_messages",
    "api_cache",
]


@pytest.fixture(autouse=True)
def isolate_test_data():
    """Drop transient collections before each test (places are session-seeded)."""
    for col_name in _TRANSIENT_COLLECTIONS:
        _mock_db[col_name].drop()
    yield
    # Optionally drop after too for absolute cleanliness
    for col_name in _TRANSIENT_COLLECTIONS:
        _mock_db[col_name].drop()


# ---------------------------------------------------------------------------
# Database session fixture (returns the mock MongoDB database object)
# ---------------------------------------------------------------------------
@pytest.fixture
def db_session():
    """Yield the mongomock database, matching the signature expected by tests."""
    return _mock_db


# ---------------------------------------------------------------------------
# FastAPI test client with dependency override
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from app.main import app

    app.dependency_overrides[get_db] = _get_mock_db_dep
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Authenticated user fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_user():
    user_repo = UserRepository(_mock_db)
    user = user_repo.create(
        email="testuser@example.com",
        password_hash=hash_password("password123"),
        display_name="Test Explorer"
    )
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def other_user():
    user_repo = UserRepository(_mock_db)
    user = user_repo.create(
        email="other@example.com",
        password_hash=hash_password("password123"),
        display_name="Other User"
    )
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}
