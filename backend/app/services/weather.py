import json
import os
import time
from datetime import datetime, timezone
from typing import Any, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.entities import CacheRepository
from app.schemas.itinerary import DayWeather

logger = get_logger("weather_service")

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fixtures")


class WeatherService:
    _circuit_open_until = 0.0
    _consecutive_failures = 0

    @classmethod
    def get_forecast(
        cls,
        db: Any,
        destination_id: str,
        lat: float,
        lng: float,
        num_days: int = 4
    ) -> List[DayWeather]:
        # 1. If DEMO_MODE is "on", use fixtures directly
        if settings.DEMO_MODE == "on":
            return cls._get_fixture_forecast(destination_id, num_days)

        cache_repo = CacheRepository(db)
        cache_key = f"weather:{destination_id}:{lat:.2f}:{lng:.2f}:{num_days}"

        # 2. Check fresh cache
        cached = cache_repo.get(cache_key)
        if cached and not cached["stale"]:
            try:
                days = [DayWeather(**d) for d in cached["value"]]
                return days
            except Exception as e:
                logger.warning(f"Error parsing cached weather: {e}")

        # 3. Check circuit breaker
        now = time.time()
        if now < cls._circuit_open_until:
            logger.info("Weather circuit breaker OPEN. Using cached or demo fixture.")
            if cached:
                return [DayWeather(**d) for d in cached["value"]]
            return cls._get_fixture_forecast(destination_id, num_days)

        # 4. Attempt live Open-Meteo
        try:
            url = f"{settings.OPEN_METEO_URL}?latitude={lat}&longitude={lng}&daily=weathercode,temperature_2m_max,precipitation_probability_max&timezone=auto&forecast_days={max(num_days, 7)}"
            with httpx.Client(timeout=4.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    daily = data.get("daily", {})
                    temps = daily.get("temperature_2m_max", [])
                    rains = daily.get("precipitation_probability_max", [])
                    weathercodes = daily.get("weathercode", [])

                    forecast_days: List[DayWeather] = []
                    for i in range(num_days):
                        t_max = temps[i] if i < len(temps) else 31.0
                        r_prob = rains[i] if i < len(rains) else 10
                        code = weathercodes[i] if i < len(weathercodes) else 0

                        summary = "Sunny & clear"
                        if code in [1, 2, 3]:
                            summary = "Partly cloudy"
                        elif code in [51, 53, 55, 61, 63, 65, 80, 81]:
                            summary = "Scattered showers"
                        elif code in [95, 96, 99]:
                            summary = "Thunderstorms"

                        forecast_days.append(DayWeather(
                            summary=summary,
                            temp_max_c=float(t_max),
                            rain_prob_pct=int(r_prob),
                            source="live",
                            as_of=datetime.now(timezone.utc).isoformat()
                        ))

                    # Cache live result
                    cache_repo.set(
                        key=cache_key,
                        provider="weather",
                        value_json=[d.model_dump() for d in forecast_days],
                        ttl_seconds=settings.WEATHER_CACHE_TTL_SECONDS
                    )
                    cls._consecutive_failures = 0
                    return forecast_days
                else:
                    raise Exception(f"Open-Meteo returned status {res.status_code}")
        except Exception as e:
            logger.warning(f"Live weather fetch failed: {e}. Falling back.")
            cls._consecutive_failures += 1
            if cls._consecutive_failures >= 3:
                cls._circuit_open_until = now + 60.0
                logger.warning("Weather circuit breaker tripped for 60 seconds.")

            # Fallback to stale cache
            if cached:
                cached_data = [DayWeather(**d) for d in cached["value"]]
                for d in cached_data:
                    d.source = "cache"
                return cached_data

            # Fallback to fixture
            return cls._get_fixture_forecast(destination_id, num_days)

    @classmethod
    def _get_fixture_forecast(cls, destination_id: str, num_days: int) -> List[DayWeather]:
        fixture_file = os.path.join(FIXTURES_DIR, "weather_goa_clear.json")
        if os.path.exists(fixture_file):
            try:
                with open(fixture_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("forecast", [])
                    days: List[DayWeather] = []
                    for i in range(num_days):
                        item = items[i % len(items)]
                        days.append(DayWeather(
                            summary=item.get("summary", "Pleasant and clear"),
                            temp_max_c=item.get("temp_max_c", 31.0),
                            rain_prob_pct=item.get("rain_prob_pct", 10),
                            source="demo",
                            as_of=datetime.now(timezone.utc).isoformat()
                        ))
                    return days
            except Exception as e:
                logger.warning(f"Error loading weather fixture: {e}")

        # Safe fallback
        return [
            DayWeather(
                summary="Sunny coastal weather",
                temp_max_c=31.0,
                rain_prob_pct=10,
                source="demo",
                as_of=datetime.now(timezone.utc).isoformat()
            )
            for _ in range(num_days)
        ]
