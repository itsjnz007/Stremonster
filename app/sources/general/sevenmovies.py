import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class SevenMovies(Scraper):
    def __init__(self):
        super().__init__(source="7movies", base_url="https://7movies.ac",
                        #  log_requests=True,
                        # stream_url_pattern = r'https?://\S*(?:index\.m3u8|\.mp4)\S*',
                        # headless=False,
                        )

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/movie/{tmdb_id}"
        result = self.get_stream(url, stop_event)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/tv/{tmdb_id}/watch?season={season}&episode={episode}"
        result = self.get_stream(url, stop_event)
        return result

if __name__ == "__main__":
    scraper = SevenMovies()
    
    series_response = scraper.get_series("66573", "3", "4")
    print(f"Series response: {series_response}")
