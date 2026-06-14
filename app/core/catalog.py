import sys
from pathlib import Path
from typing import Any
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.external.tmdb import TmdbCache, TmdbCatalog
from app.core.caching import CatalogCache
from app.config import TMDB_API_KEY

class Catalog:
    def __init__(self, tmdb_cache: TmdbCache):
        if not TMDB_API_KEY: raise ValueError("TMDB_API_KEY not set in environment")
        self.tmdb_cache = tmdb_cache
        self.tmdb_catalog = TmdbCatalog(tmdb_cache)
        self.cache = CatalogCache()

    def build_catalog(self, pages: int = 1) -> dict[str, Any] | None:
        catalog_cache = self.cache.get("catalog")
        if catalog_cache: return catalog_cache

        catalog = self.tmdb_catalog.get_catalog(pages=pages)
        if catalog:
            # Cache the entire catalog
            self.cache.set("catalog", catalog)
            # Also cache each individual catalog entry
            for catalog_id, catalog_data in catalog.items():
                self.cache.set(catalog_id, catalog_data)

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
    print("Fetching catalog...")
    result = catalog.build_catalog(pages=1)
    from pprint import pprint
    pprint(result)