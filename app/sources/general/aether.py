import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event


class AetherScraper(Scraper):
    def __init__(self):
        super().__init__(source="aether", base_url="https://aether.bar/")

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/media/tmdb-movie-{tmdb_id}"
        result = self.get_stream(url, stop_event)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/media/tmdb-tv-{tmdb_id}/{season}/{episode}"
        result = self.get_stream(url, stop_event)
        return result
    

if __name__ == "__main__":
    scraper = AetherScraper()

    res = scraper.get_movie("969681")
    print(f"Response: {res}")