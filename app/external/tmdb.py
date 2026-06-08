import sys
import os
from pathlib import Path
from typing import Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.logger import Logger
from app.core.caching import Caching
import requests

logger = Logger("tmdb")

class Tmdb:
    def __init__(self, cache: Caching):
        # Use provided api_key, fall back to environment variable
        api_key = os.getenv("TMDB_API_KEY")
        if not api_key:
            raise ValueError("TMDB_API_KEY not provided and not set in environment")

        self.base_url = "https://api.themoviedb.org/3"
        self.cache = cache
        self.api_key = api_key

    def find(self, imdb_id: str) -> Optional[dict[str, Any]]:
        find_cache = self.cache.get_tmdb(imdb_id)

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
            self.cache.set_tmdb(imdb_id, res)
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
            return tmdb_id
        
        # Check TV results next
        if find_response.get("tv_results"):
            tmdb_id = find_response["tv_results"][0].get("id")
            logger.debug(f"Found TMDB ID {tmdb_id} for TV IMDB ID {imdb_id}")
            return tmdb_id
        
        logger.info(f"No TMDB ID found in find response for IMDB ID {imdb_id}")
        return None
        
if __name__ == "__main__":
    cache = Caching()
    tmdb = Tmdb(cache)
    test_imdb_id = "tt1375666"  # Inception
    result = tmdb.imdb_to_tmdb(test_imdb_id)
    print(result)