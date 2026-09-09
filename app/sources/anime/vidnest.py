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
    
    def get_series(self, anilist_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[list[WebResponse]]:
        if not anilist_id or not episode: return
        result: list[WebResponse] = []
        url_sub = f"{self.base_url}/anime/{anilist_id}/{episode}/sub"
        result_sub = self.get_stream(url_sub, stop_event, title="Vidnest (SUB)")
        if result_sub:
            result.append(result_sub)

        url_dub = f"{self.base_url}/anime/{anilist_id}/{episode}/dub"
        result_dub = self.get_stream(url_dub, stop_event, title="Vidnest (DUB)")
        if result_dub:
            result.append(result_dub)
        return result if result else None

if __name__ == "__main__":
    scraper = VidnestScraper()
    response = scraper.get_series("165159", "127")
    print(response)
  