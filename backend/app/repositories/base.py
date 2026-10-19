"""
Base entities and utilities for MongoDB repositories.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from bson import ObjectId
from bson.errors import InvalidId


class EntityDoc(dict):
    """
    Dictionary subclass supporting attribute access (e.g. item.id, item.name),
    key access (item['id']), and .model_dump() for FastAPI/Pydantic responses.
    """
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            return None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        try:
            del self[name]
        except KeyError:
            pass

    def model_dump(self) -> Dict[str, Any]:
        return dict(self)


def to_id_filter(id_val: Union[str, int, ObjectId], id_field: str = "_id", sqlite_field: str = "sqlite_id") -> Dict[str, Any]:
    """
    Build a filter matching ObjectId, string representation of ObjectId,
    string key, or legacy integer sqlite_id.
    """
    if id_val is None:
        return {id_field: None}

    if isinstance(id_val, ObjectId):
        return {id_field: id_val}

    clauses = []
    if isinstance(id_val, int):
        clauses.append({sqlite_field: id_val})
        clauses.append({id_field: str(id_val)})
    elif isinstance(id_val, str):
        id_str = id_val.strip()
        try:
            clauses.append({id_field: ObjectId(id_str)})
        except (InvalidId, TypeError):
            pass
        clauses.append({id_field: id_str})
        if id_str.isdigit():
            clauses.append({sqlite_field: int(id_str)})

    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def to_object_id(val: Union[str, int, ObjectId]) -> Optional[ObjectId]:
    if isinstance(val, ObjectId):
        return val
    if isinstance(val, str):
        try:
            return ObjectId(val.strip())
        except Exception:
            return None
    return None
