import sys
import os, logging
from pathlib import Path
from typing import Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.logger import Logger
from app.core.caching import TmdbCache
import requests
from app.config import CATALOG_BUILDER

logger = Logger("tmdb", level=logging.DEBUG)

class Tmdb:
    def __init__(self, cache: TmdbCache):
        # Use provided api_key, fall back to environment variable
        api_key = os.getenv("TMDB_API_KEY")
        if not api_key:
            raise ValueError("TMDB_API_KEY not provided and not set in environment")

        self.base_url = "https://api.themoviedb.org/3"
        self.image_base = "https://image.tmdb.org/t/p/w500"
        self.cache = cache
        self.api_key = api_key

    def find(self, imdb_id: str) -> Optional[dict[str, Any]]:
        find_cache = self.cache.get(imdb_id)

        if find_cache:
            logger.debug(f"Found cached find response for IMDB ID {imdb_id}")
            return find_cache
        
        url = f"{self.base_url}/find/{imdb_id}"
        params = {
            "api_key": self.api_key,
            "external_source": "imdb_id"
        }

        try:
            res = requests.get(url, params=params, timeout=5).json()
            # Cache the complete find API response
            self.cache.set("find", {imdb_id: res})
            return res
        except requests.RequestException as e:
            logger.error(f"Error fetching find API for IMDB ID {imdb_id}: {e}")
            return None
        
    def imdb_to_tmdb(self, imdb_id: str) -> Optional[str]:
        """Convert IMDB ID to TMDB ID using cached find API responses"""
        find_response = self.find(imdb_id)
        if not find_response:
            logger.info(f"No find response for IMDB ID {imdb_id}")
            return None
        
        # Check movie results first
        if find_response.get("movie_results"):
            tmdb_id = find_response["movie_results"][0].get("id")
            logger.debug(f"Found TMDB ID {tmdb_id} for movie IMDB ID {imdb_id}")
            return str(tmdb_id)
        
        # Check TV results next
        if find_response.get("tv_results"):
            tmdb_id = find_response["tv_results"][0].get("id")
            logger.debug(f"Found TMDB ID {tmdb_id} for TV IMDB ID {imdb_id}")
            return str(tmdb_id)
        
        logger.info(f"No TMDB ID found in find response for IMDB ID {imdb_id}")
        return None
    
    def tmdb_to_imdb(self, tmdb_id: str, media_type: str) -> Optional[str]:
        cache_key = "imdb_to_tmdb"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            imdb_id = cached_result.get(str(tmdb_id))
            if imdb_id: 
                logger.debug(f"Found cached IMDB ID {imdb_id} for TMDB ID {tmdb_id}")
                return imdb_id

        url = f"{self.base_url}/{media_type}/{tmdb_id}"
        params = {
            "api_key": self.api_key
        }

        try:
            res = requests.get(url, params=params, timeout=5).json()
            imdb_id = res.get("imdb_id")
            if imdb_id:
                logger.debug(f"Found IMDB ID {imdb_id} for TMDB ID {tmdb_id}")
                self.cache.set(cache_key, {str(tmdb_id): imdb_id})  # Cache just the IMDB ID
                return imdb_id
            else:
                logger.info(f"No IMDB ID found for TMDB ID {tmdb_id}")
                return None
        except requests.RequestException as e:
            logger.error(f"Error fetching TMDB details for TMDB ID {tmdb_id}: {e}")
            return None
    
    def get_original_lang(self, imdb_id: str) -> Optional[str]:
        find_response = self.find(imdb_id)

        if not find_response:
            logger.info(f"No find response for IMDB ID {imdb_id}")
            return None
        
        # Check movie results first
        if find_response.get("movie_results"):
            tmdb_id = find_response["movie_results"][0].get("original_language")
            return tmdb_id
        
        # Check TV results next
        if find_response.get("tv_results"):
            tmdb_id = find_response["tv_results"][0].get("original_language")
            return tmdb_id
        
    def get_title(self, imdb_id: str) -> Optional[str]:
        find_response = self.find(imdb_id)

        if not find_response:
            logger.info(f"No find response for IMDB ID {imdb_id}")
            return None
        
        # Check movie results first
        if find_response.get("movie_results"):
            tmdb_id = find_response["movie_results"][0].get("title")
            return tmdb_id
        
        # Check TV results next
        if find_response.get("tv_results"):
            tmdb_id = find_response["tv_results"][0].get("title")
            return tmdb_id
        

class TmdbCatalog(Tmdb):
    def __init__(self, cache: TmdbCache):
        super().__init__(cache)

    def _getter(self, url: str, pages: int = 1) -> Optional[dict[str, Any]]:
        all_results = []
        for page in range(1, pages + 1):
            params = {
                "api_key": self.api_key,
                "page": page
            }

            try:
                res = requests.get(url, params=params, timeout=5).json()
                all_results.extend(res.get("results", []))
            except requests.RequestException as e:
                logger.error(f"Error fetching data from {url} page {page}: {e}")
                continue
        
        return {"results": all_results} if all_results else None
    
    def get_catalog(self, pages: int = 1) -> Optional[dict[str, Any]]:
        catalog = {}
        
        for region, media_types in CATALOG_BUILDER.items():
            for media_type, categories in media_types.items():
                for category, url in categories.items():
                    logger.info(f"Fetching catalog for {region} - {media_type} - {category}")
                    catalog_id = f"{region}_{media_type}_{category}"
                    results = self._getter(url, pages)
                    
                    if results and results.get("results"):
                        metas = []
                        for item in results["results"]:
                            # Handle both movie and TV show response formats
                            title = item.get("title") or item.get("name", "")
                            poster_path = item.get("poster_path")
                            tmdb_id = item.get("id")
                            
                            if tmdb_id and title:  # Only include items with id and title
                                meta = {
                                    "id": self.tmdb_to_imdb(str(tmdb_id), media_type),
                                    "type": "movie" if media_type == "movie" else "series",
                                    "name": title,
                                    "poster": f"{self.image_base}{poster_path}" if poster_path else None
                                }
                                metas.append(meta)
                        
                        catalog[catalog_id] = {"metas": metas}
                    else:
                        catalog[catalog_id] = {"metas": []}
        
        return catalog if catalog else None

if __name__ == "__main__":
    cache = TmdbCache()
    tmdb = TmdbCatalog(cache)
    test_imdb_id = "tt1375666"
    tmdb_id = tmdb.imdb_to_tmdb(test_imdb_id)
    print(f"TMDB ID for IMDB ID {test_imdb_id}: {tmdb_id}")
    print("IMDB to TMDB mapping:")
    imdb_id = tmdb.tmdb_to_imdb(tmdb_id, "movie")
    print(f"IMDB ID for TMDB ID {tmdb_id}: {imdb_id}")