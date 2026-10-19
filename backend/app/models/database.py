"""
Database integration module.
Routes get_db and init_db directly to MongoDB.
"""
from typing import Generator
from sqlalchemy.orm import declarative_base
from app.db.mongodb import get_db as get_mongodb, init_db as init_mongodb

Base = declarative_base()


def get_db() -> Generator:
    """Yield active MongoDB database instance for FastAPI dependencies."""
    db = get_mongodb()
    yield db


def init_db() -> None:
    """Initialize MongoDB connection and create indexes."""
    init_mongodb()


# For backward-compatibility with tests or scripts that import SessionLocal
class _SessionLocal:
    def __call__(self):
        return get_mongodb()

SessionLocal = _SessionLocal()
