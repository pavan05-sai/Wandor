from typing import Any
from fastapi import APIRouter, Depends
from app.core.config import settings
from app.models.database import get_db
from app.schemas.common import success_response

router = APIRouter(tags=["System"])


@router.get("/health")
def health_check(db: Any = Depends(get_db)):
    # Check MongoDB connectivity
    db_status = "connected"
    try:
        db.command("ping")
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Providers status
    providers = {
        "gemini": "configured" if settings.GEMINI_API_KEY else "unconfigured_fallback_ready",
        "open_meteo": "active",
        "osrm": "active",
        "nominatim": "active",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "database": "mongodb"
    }

    return success_response({
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "1.0.0",
        "database": db_status,
        "database_type": "mongodb",
        "demo_mode": settings.DEMO_MODE,
        "environment": settings.ENVIRONMENT,
        "providers": providers
    })
