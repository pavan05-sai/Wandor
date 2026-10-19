from typing import Any
from fastapi import APIRouter, Depends, status
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.database import get_db
from app.repositories.users import UserRepository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.schemas.common import success_response

router = APIRouter(prefix="/auth", tags=["Auth"])


def _iso(dt: Any) -> str:
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt or "")


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Any = Depends(get_db)):
    repo = UserRepository(db)
    existing = repo.get_by_email(req.email)
    if existing:
        raise ConflictError("An account with this email already exists")

    hashed = hash_password(req.password)
    user = repo.create(email=req.email, password_hash=hashed, display_name=req.display_name)
    token = create_access_token({"sub": str(user.id), "email": user.email})

    return success_response({
        "token": token,
        "user": UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=_iso(user.created_at))
    })


@router.post("/login")
def login(req: LoginRequest, db: Any = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_email(req.email)
    if not user or not verify_password(req.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return success_response({
        "token": token,
        "user": UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=_iso(user.created_at))
    })


@router.post("/demo")
def demo_login(db: Any = Depends(get_db)):
    """One-click seeded demo user login."""
    repo = UserRepository(db)
    demo_email = "demo@tripplanner.ai"
    user = repo.get_by_email(demo_email)
    if not user:
        hashed = hash_password("demopass123")
        user = repo.create(email=demo_email, password_hash=hashed, display_name="Demo Traveler")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return success_response({
        "token": token,
        "user": UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=_iso(user.created_at))
    })
