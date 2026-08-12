import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class YomiScraper(Scraper):
    def __init__(self):
        super().__init__(source="yomi",
                          stream_url_pattern=r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/mp4)\S*',
                          base_url="https://yomi.to"
                          )
    
    def get_series(self, anilist_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/watch/{anilist_id}/{episode}"
        result = self.get_stream(url, stop_event, title=f"{self.source.title()} (Anime)")
        return result
        

if __name__ == "__main__":
    scraper = YomiScraper()
    print(scraper.get_series('178025', '13'))