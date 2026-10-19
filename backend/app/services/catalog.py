import json
import os
import re
from typing import Any, Dict, List, Optional
from app.repositories.places import PlaceRepository
from app.schemas.places import DestinationSchema
from app.services.geocoding import GeocodingService
from app.services.dynamic_places import CURATED_GLOBAL_PLACES, generate_algorithmic_places

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "data", "seed")


class CatalogService:
    _dynamic_cache: Dict[str, DestinationSchema] = {}

    @classmethod
    def get_destinations(cls, db: Optional[Any] = None) -> List[DestinationSchema]:
        """Return seed destinations along with any dynamically registered destinations."""
        dest_path = os.path.join(SEED_DIR, "destinations.json")
        destinations = []
        if os.path.exists(dest_path):
            with open(dest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                destinations = [DestinationSchema(**d) for d in data]

        # Append any cached dynamic destinations
        for dyn_dest in cls._dynamic_cache.values():
            if not any(d.id == dyn_dest.id for d in destinations):
                destinations.append(dyn_dest)

        return destinations

    @classmethod
    def get_destination_by_id(cls, destination_id: str, db: Optional[Any] = None) -> Optional[DestinationSchema]:
        """Lookup destination by ID or dynamically resolve from geocoding."""
        # 1. Check seed destinations
        dests = cls.get_destinations()
        for d in dests:
            if d.id == destination_id or d.catalog_id == destination_id:
                return d

        # 2. Check dynamic in-memory cache
        if destination_id in cls._dynamic_cache:
            return cls._dynamic_cache[destination_id]

        clean_slug = destination_id.lower().replace("dest_", "")
        if clean_slug in cls._dynamic_cache:
            return cls._dynamic_cache[clean_slug]

        # 3. Dynamic geocode fallback for any global destination
        return cls.resolve_and_register_destination(db, destination_id)

    @classmethod
    def resolve_and_register_destination(
        cls, db: Optional[Any], query: str
    ) -> Optional[DestinationSchema]:
        """Geocode and register any valid destination globally via free Nominatim."""
        geo_info = GeocodingService.geocode_destination(db, query)
        if not geo_info:
            return None

        name = geo_info["name"]
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
        if not slug:
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", query.lower()).strip("_") or "dest"
        dest_id = f"dest_{slug}"

        dest_schema = DestinationSchema(
            id=dest_id,
            catalog_id=dest_id,
            name=name,
            country=geo_info.get("country", "IN"),
            lat=geo_info["lat"],
            lng=geo_info["lng"],
            blurb=f"Discover {name}, a stunning destination with rich culture, scenic sights, and vibrant local cuisine.",
            coverage=25,
            image=None
        )

        cls._dynamic_cache[dest_id] = dest_schema
        cls._dynamic_cache[slug] = dest_schema
        cls._dynamic_cache[query.lower().strip()] = dest_schema
        return dest_schema

    @classmethod
    def search_destinations(cls, db: Optional[Any], query: str) -> List[DestinationSchema]:
        """Search global destinations: checks seed presets first, then queries free Nominatim."""
        query_clean = query.lower().strip()
        results: List[DestinationSchema] = []

        # Check existing seeds & cached
        all_known = cls.get_destinations(db=db)
        for d in all_known:
            if query_clean in d.name.lower() or query_clean in d.id.lower():
                results.append(d)

        # Also search Nominatim for global cities
        geo_results = GeocodingService.search_destinations(db, query)
        for item in geo_results:
            name = item["name"]
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
            if not slug:
                slug = re.sub(r"[^a-zA-Z0-9]+", "_", query.lower()).strip("_") or "dest"
            dest_id = f"dest_{slug}"
            if not any(r.id == dest_id for r in results):
                dest_schema = DestinationSchema(
                    id=dest_id,
                    catalog_id=dest_id,
                    name=name,
                    country=item.get("country", "IN"),
                    lat=item["lat"],
                    lng=item["lng"],
                    blurb=f"Discover {name}, featuring iconic landmarks and local experiences.",
                    coverage=25,
                    image=None
                )
                cls._dynamic_cache[dest_id] = dest_schema
                results.append(dest_schema)

        return results[:8]

    @classmethod
    def get_places_for_destination(cls, db: Any, destination_id: str) -> List[Any]:
        """Retrieve places for destination. Loads seeds or dynamically creates grounded catalog."""
        repo = PlaceRepository(db)
        places = repo.list_by_destination(destination_id)
        if places:
            return places

        # Check if seed files exist for this destination
        seed_files = {
            "dest_goa": "places_goa.json",
            "dest_jaipur": "places_jaipur.json",
            "dest_hyderabad": "places_hyderabad.json"
        }

        if destination_id in seed_files:
            cls.load_seed_to_db(db, destination_id)
            return repo.list_by_destination(destination_id)

        # Check if curated global places exist for this destination
        if destination_id in CURATED_GLOBAL_PLACES:
            repo.bulk_create_or_update(CURATED_GLOBAL_PLACES[destination_id])
            return repo.list_by_destination(destination_id)

        # For any arbitrary destination, generate grounded places around real coordinates
        dest_schema = cls.get_destination_by_id(destination_id, db=db)
        if dest_schema:
            dyn_places = generate_algorithmic_places(dest_schema)
            repo.bulk_create_or_update(dyn_places)
            return repo.list_by_destination(destination_id)

        return []

    @classmethod
    def load_seed_to_db(cls, db: Any = None, destination_id: Optional[str] = None):
        repo = PlaceRepository(db)
        files = {
            "dest_goa": "places_goa.json",
            "dest_jaipur": "places_jaipur.json",
            "dest_hyderabad": "places_hyderabad.json"
        }
        for dest, filename in files.items():
            if destination_id and dest != destination_id:
                continue
            filepath = os.path.join(SEED_DIR, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    places_data = json.load(f)
                    repo.bulk_create_or_update(places_data)
