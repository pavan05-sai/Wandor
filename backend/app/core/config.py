import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEMO_MODE: str = "auto"  # "auto", "on", "off"

    # MongoDB (primary database)
    MONGODB_URI: str = ""
    MONGODB_DB_NAME: str = "wandor"

    # Legacy SQLite (kept for migration reference only — do not use in production)
    DATABASE_URL: str = "sqlite:///./travel_planner.db"

    # Security
    SECRET_KEY: str = "change-this-secret-key-in-production-min-32-chars"
    JWT_SECRET: str = "change-this-jwt-secret-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # AI / LLM
    LLM_PROVIDER: str = "gemini"  # "gemini" or "replay"
    GEMINI_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_REPAIR_ATTEMPTS: int = 2

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    LLM_RATE_LIMIT_PER_MINUTE: int = 10

    # External APIs
    OSRM_URL: str = "http://router.project-osrm.org"
    OPEN_METEO_URL: str = "https://api.open-meteo.com/v1/forecast"
    NOMINATIM_URL: str = "https://nominatim.openstreetmap.org"

    # Weather Cache TTL (3 hours = 10800 seconds)
    WEATHER_CACHE_TTL_SECONDS: int = 10800
    # Route Cache TTL (7 days = 604800 seconds)
    ROUTE_CACHE_TTL_SECONDS: int = 604800

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


settings = Settings()
