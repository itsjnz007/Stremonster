import sys
from pathlib import Path
from typing import Any
import threading, datetime
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.external.tmdb import TmdbCache, TmdbCatalog
from app.core.caching import CatalogCache
from app.config import TMDB_API_KEY
from app.core.multithreading import MultiThreading
from app.core.logger import Logger

threadpool = MultiThreading(max_workers=1)
logger = Logger("Catalog")

class Catalog:
    def __init__(self, tmdb_cache: TmdbCache):
        if not TMDB_API_KEY: raise ValueError("TMDB_API_KEY not set in environment")
        self.tmdb_cache = tmdb_cache
        self.tmdb_catalog = TmdbCatalog(tmdb_cache)
        self.cache = CatalogCache()
        # Start a background scheduler that triggers an immediate catalog build
        # and then runs daily at 3:00 AM. The scheduler runs via the shared
        # `threadpool.run_in_background` which will pass a threading.Event
        # for cooperative shutdown/cancellation.
        def _daily_scheduler(event: threading.Event) -> None:
            try:
                # Trigger immediately on start
                self.build_catalog()
            except Exception as e:
                logger.error(f"Catalog initial build failed: {e}")

            while not event.is_set():
                now = datetime.datetime.now()
                # Next scheduled 3:00 AM
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run = next_run + datetime.timedelta(days=1)

                wait_seconds = (next_run - now).total_seconds()
                # Wait until the next run or until event is set
                event.wait(timeout=wait_seconds)
                if event.is_set():
                    break

                try:
                    self.build_catalog()
                except Exception as e:
                    logger.error(f"Catalog scheduled build failed: {e}")

            return None

        # Launch scheduler in background using the threadpool
        threadpool.run_in_background(_daily_scheduler)

    def build_catalog(self, pages: int = 10) -> dict[str, Any] | None:
        logger.info(f"Building catalog with {pages} pages...")
        catalog_cache = self.cache.get("catalog", 60*6)  # Cache for 6 hours
        if catalog_cache: return catalog_cache

        catalog = self.tmdb_catalog.get_catalog(pages=pages)
        if catalog:
            # Cache the entire catalog
            self.cache.set("catalog", catalog)
            # Also cache each individual catalog entry
            for catalog_id, catalog_data in catalog.items():
                self.cache.set(catalog_id, catalog_data)
        logger.info(f"Catalog build complete.")
        return catalog
    
    def get_catalog(self, catalog_id: str) -> dict[str, Any] | None:
        cached = self.cache.get(catalog_id)
        if cached: return cached
        
        catalog = self.build_catalog()
        if catalog: return catalog.get(catalog_id)
        return None

if __name__ == "__main__":
    tmdb_cache = TmdbCache()
    catalog = Catalog(tmdb_cache)
    # logger.info("Fetching catalog...")
    # result = catalog.build_catalog(pages=1)
    # from pprint import pprint
    # pprint(result)