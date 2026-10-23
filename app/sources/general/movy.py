import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class MovyScraper(Scraper):
    def __init__(self):
        super().__init__(source="movy", base_url="https://www.movy.sx",
                        #  headless=False
                         )

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/movie/{tmdb_id}?play=true"
        result = self.get_stream(url, stop_event)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}?play=true"
        result = self.get_stream(url, stop_event)
        return result

if __name__ == "__main__":
    scraper = MovyScraper()
    
    series_response = scraper.get_series("48891", "5", "2")
    print(f"Series response: {series_response}")

    movie_response = scraper.get_movie("550") # Movie ID for "Fight Club"
    print(f"Movie response: {movie_response}")
