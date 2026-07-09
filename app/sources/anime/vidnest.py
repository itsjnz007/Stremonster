import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class VidnestScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, base_url="https://vidnest.fun", source="vidnest",
                          stream_url_pattern= r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/|/seg)\S*')
    
    def get_series(self, anilist_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/anime/{anilist_id}/{episode}/sub"
        result = self.get_stream(url, stop_event, title="Web | Vidnest (Anime)")
        return result
    
if __name__ == "__main__":
    scraper = VidnestScraper()
    response = scraper.get_series("166613", "12")
    print(response)
  