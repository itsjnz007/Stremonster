import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class VidsrcScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="vidsrc", base_url="https://www.vidsrc.wtf")

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/1/movie/{tmdb_id}"
        result = self.get_stream(url, stop_event, title="Web | Vidsrc")
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/1/tv/{tmdb_id}/{season}/{episode}"
        result = self.get_stream(url, stop_event, title="Web | Vidsrc")
        return result

if __name__ == "__main__":
    test_movie_id = "687163"  # John Wick: Chapter 4
    test_series_id = "1399"    # Game of Thrones

    scraper = VidsrcScraper()
    
    print(f"Testing movie ID {test_movie_id}...")
    movie_response = scraper.get_movie(test_movie_id)
    print(f"Movie response: {movie_response}")

    print(f"Testing serues ID {test_series_id}...")
    series_response = scraper.get_series(test_series_id, "1", "1")
    print(f"Movie response: {series_response}")
