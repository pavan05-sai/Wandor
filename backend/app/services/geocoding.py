import time
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.entities import CacheRepository

logger = get_logger("geocoding_service")


class GeocodingService:
    _last_request_time = 0.0

    @classmethod
    def geocode_destination(cls, db: Optional[Any], query: str) -> Optional[Dict[str, Any]]:
        """Geocode a city or destination query to real coordinates and location metadata."""
        clean_q = query.lower().replace("dest_", "").replace("_", " ").strip()
        cache_key = f"nominatim_dest:{clean_q}"

        if db:
            cache_repo = CacheRepository(db)
            cached = cache_repo.get(cache_key)
            if cached and isinstance(cached.get("value"), dict):
                return cached["value"]

        now = time.time()
        elapsed = now - cls._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        cls._last_request_time = time.time()

        try:
            headers = {
                "User-Agent": "AIDynamicTravelPlanner/1.0 (free-travel-platform)",
                "accept-language": "en"
            }
            params = {"q": clean_q, "format": "json", "limit": 1, "addressdetails": 1}
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{settings.NOMINATIM_URL}/search", params=params, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if data and len(data) > 0:
                        first = data[0]
                        addr = first.get("address", {})
                        city_name = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("state") or first.get("name") or clean_q.title()
                        country_code = (addr.get("country_code") or "IN").upper()
                        result = {
                            "name": city_name,
                            "country": country_code,
                            "lat": float(first["lat"]),
                            "lng": float(first["lon"]),
                            "display_name": first.get("display_name", f"{city_name}, {country_code}")
                        }
                        if db:
                            cache_repo = CacheRepository(db)
                            cache_repo.set(cache_key, provider="nominatim", value_json=result, ttl_seconds=30 * 86400)
                        return result
        except Exception as e:
            logger.warning(f"Geocoding destination failed for '{query}': {e}")

        return None

    @classmethod
    def search_destinations(cls, db: Optional[Any], query: str) -> List[Dict[str, Any]]:
        """Search global destinations with autocomplete support via Nominatim."""
        clean_q = query.lower().replace("dest_", "").replace("_", " ").strip()
        if not clean_q or len(clean_q) < 2:
            return []

        cache_key = f"nominatim_search:{clean_q}"
        if db:
            cache_repo = CacheRepository(db)
            cached = cache_repo.get(cache_key)
            if cached and isinstance(cached.get("value"), list):
                return cached["value"]

        now = time.time()
        elapsed = now - cls._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        cls._last_request_time = time.time()

        results = []
        try:
            headers = {
                "User-Agent": "AIDynamicTravelPlanner/1.0 (free-travel-platform)",
                "accept-language": "en"
            }
            params = {"q": clean_q, "format": "json", "limit": 6, "addressdetails": 1}
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{settings.NOMINATIM_URL}/search", params=params, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    for item in data:
                        addr = item.get("address", {})
                        city_name = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("state") or item.get("name")
                        country_code = (addr.get("country_code") or "IN").upper()
                        if city_name:
                            results.append({
                                "name": city_name,
                                "country": country_code,
                                "lat": float(item["lat"]),
                                "lng": float(item["lon"]),
                                "display_name": item.get("display_name", "")
                            })
                    if db and results:
                        cache_repo = CacheRepository(db)
                        cache_repo.set(cache_key, provider="nominatim", value_json=results, ttl_seconds=7 * 86400)
        except Exception as e:
            logger.warning(f"Nominatim search failed for '{query}': {e}")

        return results
