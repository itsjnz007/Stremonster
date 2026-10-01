import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class Cinejoy(Scraper):
    def __init__(self):
        super().__init__(source="cinejoy", base_url="https://cinejoy.pk",
                         log_requests=True,
                        #  headless=False,
                         )

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/watch/movie/{tmdb_id}"
        result = self.get_stream(url, stop_event)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/watch/tv/{tmdb_id}/{season}/{episode}"
        result = self.get_stream(url, stop_event)
        return result

if __name__ == "__main__":
    scraper = Cinejoy()
    
    series_response = scraper.get_series("3308", "5", "1")
    print(f"Series response: {series_response}")
