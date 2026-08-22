import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class VidnestScraper(Scraper):
    def __init__(self):
        super().__init__(base_url="https://vidnest.fun", source="vidnest",
                          stream_url_pattern= r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/|/seg)\S*')
    
    def get_series(self, anilist_id: Optional[str], episode: Optional[str], stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        if not anilist_id or not episode: return
        url = f"{self.base_url}/anime/{anilist_id}/{episode}/sub"
        result = self.get_stream(url, stop_event, title="Vidnest (Anime)")
        return result
    
if __name__ == "__main__":
    scraper = VidnestScraper()
    response = scraper.get_series("165159", "127")
    print(response)
  