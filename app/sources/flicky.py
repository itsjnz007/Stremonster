import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import StreamResponse
from typing import Optional


class FlickyScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="flicky", timeout=10000)

    def get_movie(self, tmdb_id: str) -> Optional[StreamResponse]:
        url = f"https://flickystream.su/player/movie/{tmdb_id}"
        return self.get_stream(url)
    
    def get_series(self, tmdb_id: str, season: str, episode: str) -> Optional[StreamResponse]:
        url = f"https://flickystream.su/player/tv/{tmdb_id}/{season}/{episode}"
        return self.get_stream(url)
    

if __name__ == "__main__":
    test_movie_id = "687163"  # John Wick: Chapter 4
    test_series_id = "1399"    # Game of Thrones

    scraper = FlickyScraper()
    
    print(f"Testing movie ID {test_movie_id}...")
    movie_response = scraper.get_movie(test_movie_id)
    print(f"Movie response: {movie_response}")

    series_response = scraper.get_series(test_series_id, "1", "1")
    print(f"Series response: {series_response}")