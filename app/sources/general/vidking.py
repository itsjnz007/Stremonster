import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class VidkingScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="vidking", base_url="https://vidking.net")

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/embed/movie/{tmdb_id}"
        result = self.get_stream(url, stop_event=stop_event, title="Web | Vidking")
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/embed/tv/{tmdb_id}/{season}/{episode}"
        result = self.get_stream(url, stop_event, title="Web | Vidking")
        return result
    

if __name__ == "__main__":
    test_movie_id = "687163"

    scraper = VidkingScraper()
    
    print(f"Testing movie ID {test_movie_id}...")
    movie_response = scraper.get_movie(test_movie_id)
    print(f"Movie response: {movie_response}")

    # series_response = scraper.get_series(test_series_id, "1", "1")
    # print(f"Series response: {series_response}")