import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class AnikotoScraper(Scraper):
    def __init__(self):
        super().__init__(base_url="https://megaplay.buzz", source="anikoto", stream_url_pattern=r'https?://\S*(?:master\.m3u8)\S*')
    
    def get_series(self, mal_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        if not mal_id or not episode: return
        url = f"{self.base_url}/stream/mal/{mal_id}/{episode}/sub"
        result = self.get_stream(url, stop_event, title="Anikoto (Anime)")
        return result
    

if __name__ == "__main__":
    scraper = AnikotoScraper()
    response = scraper.get_series("21", "1")
    print(response)