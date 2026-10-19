import sys
from pathlib import Path
from contextlib import asynccontextmanager
import uuid

# Ensure backend root is always on sys.path regardless of execution context or IDE working directory
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api import (
    analytics, auth, chat, expenses, health, itinerary, notifications,
    recommendations, routes, sharing, trips, users, weather
)
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import request_id_ctx, setup_logging
from app.models.database import SessionLocal, init_db
from app.notifications.scheduler import start_scheduler, stop_scheduler
from app.services.catalog import CatalogService

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and seeds
    init_db()
    try:
        CatalogService.load_seed_to_db(SessionLocal())
    except Exception as e:
        pass

    # Start in-process background scheduler
    try:
        start_scheduler()
    except Exception:
        pass

    yield

    # Shutdown
    try:
        stop_scheduler()
    except Exception:
        pass


app = FastAPI(
    title="AI Dynamic Travel Planning Agent API",
    description="Production-quality backend for AI Dynamic Travel Planning with grounded generation, replanning, and full provenance tracking.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_origin_regex=r"^https?://([a-zA-Z0-9-]+\.)*vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_ctx.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_ctx.reset(token)


# Register centralized exception handlers
register_exception_handlers(app)

# Include Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(trips.router)
app.include_router(itinerary.router)
app.include_router(chat.router)
app.include_router(recommendations.router)
app.include_router(routes.router)
app.include_router(weather.router)
app.include_router(expenses.router)
app.include_router(notifications.router)
app.include_router(sharing.router)
app.include_router(analytics.router)


@app.get("/")
def root():
    return {
        "name": "AI Dynamic Travel Planning Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
