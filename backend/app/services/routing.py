import math
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.entities import CacheRepository

logger = get_logger("routing_service")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class RoutingService:
    _last_request_time = 0.0
    _circuit_open_until = 0.0
    _consecutive_failures = 0

    @classmethod
    def calculate_leg(
        cls,
        db: Any,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float,
        mode: str = "taxi"
    ) -> Dict:
        # Distance between points
        cache_repo = CacheRepository(db)
        cache_key = f"osrm:{lat1:.4f}:{lng1:.4f}:{lat2:.4f}:{lng2:.4f}:{mode}"

        # 1. Check cache
        cached = cache_repo.get(cache_key)
        if cached:
            val = cached["value"]
            val["source"] = "cache"
            return val

        # 2. Check demo mode or circuit breaker
        now = time.time()
        if settings.DEMO_MODE == "on" or now < cls._circuit_open_until:
            return cls._haversine_estimate(lat1, lng1, lat2, lng2, mode)

        # 3. Throttle 1 rps to respect OSRM public demo server policy
        elapsed = now - cls._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        cls._last_request_time = time.time()

        # 4. Attempt OSRM
        try:
            profile = "driving" if mode in ["taxi", "auto", "car"] else ("foot" if mode == "walk" else "driving")
            url = f"{settings.OSRM_URL}/route/v1/{profile}/{lng1},{lat1};{lng2},{lat2}?overview=simplified&geometries=geojson"
            with httpx.Client(timeout=4.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    routes = data.get("routes", [])
                    if routes:
                        r = routes[0]
                        dist_km = round(r.get("distance", 0.0) / 1000.0, 1)
                        dur_min = max(5, int(r.get("duration", 0.0) / 60.0))
                        coords = r.get("geometry", {}).get("coordinates", [])
                        # GeoJSON coordinates are [lng, lat], convert to [lat, lng] for leaflet
                        lat_lng_coords = [[c[1], c[0]] for c in coords] if coords else [[lat1, lng1], [lat2, lng2]]

                        result = {
                            "distance_km": dist_km,
                            "duration_min": dur_min,
                            "geometry": lat_lng_coords,
                            "source": "live"
                        }

                        # Save to cache
                        cache_repo.set(
                            key=cache_key,
                            provider="osrm",
                            value_json=result,
                            ttl_seconds=settings.ROUTE_CACHE_TTL_SECONDS
                        )
                        cls._consecutive_failures = 0
                        return result
                    else:
                        raise Exception("No routes found in OSRM response")
                else:
                    raise Exception(f"OSRM returned status {res.status_code}")
        except Exception as e:
            logger.warning(f"OSRM live routing failed: {e}. Falling back to haversine estimate.")
            cls._consecutive_failures += 1
            if cls._consecutive_failures >= 3:
                cls._circuit_open_until = time.time() + 60.0
                logger.warning("OSRM circuit breaker tripped for 60 seconds.")
            return cls._haversine_estimate(lat1, lng1, lat2, lng2, mode)

    @classmethod
    def _haversine_estimate(cls, lat1: float, lng1: float, lat2: float, lng2: float, mode: str) -> Dict:
        raw_dist = haversine_km(lat1, lng1, lat2, lng2)
        dist_km = round(raw_dist * 1.3, 1)  # 1.3 circuity factor

        speed_kmh = 30.0 if mode in ["taxi", "auto", "car"] else (15.0 if mode == "scooter" else 4.5)
        dur_min = max(5, int((dist_km / speed_kmh) * 60) + 5)

        return {
            "distance_km": dist_km,
            "duration_min": dur_min,
            "geometry": [[lat1, lng1], [lat2, lng2]],
            "source": "estimated"
        }
