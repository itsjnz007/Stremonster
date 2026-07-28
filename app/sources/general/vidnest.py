import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class VidnestScraper(Scraper):
    def __init__(self):
        super().__init__(source="vidnest", base_url="https://vidnest.fun", 
                         stream_url_pattern=r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/|/mp4|/videos/)\S*')

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/movie/{tmdb_id}"
        result = self.get_stream(url, stop_event)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}"
        result = self.get_stream(url, stop_event)
        return result

if __name__ == "__main__":
    scraper = VidnestScraper()
    
    series_response = scraper.get_movie("1301421")
    print(f"Series response: {series_response}")
