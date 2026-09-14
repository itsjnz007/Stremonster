import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class YomiScraper(Scraper):
    def __init__(self):
        super().__init__(base_url="https://cinextream.cc", source="yomi",
                          stream_url_pattern= r'https?://\S*(?:\.m3u)\S*',
                          headless=False
                          )
    
    def get_series(self, anilist_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[list[WebResponse]]:
        if not anilist_id or not episode: return
        result: list[WebResponse] = []
        
        url_sub = f"{self.base_url}/api/embed/anime/sub/{anilist_id}/{episode}"
        result_sub = self.get_stream(url_sub, stop_event, title="Yomi (SUB)")
        if result_sub:
            result.append(result_sub)

        url_sub = f"{self.base_url}/api/embed/anime/dub/{anilist_id}/{episode}"
        result_sub = self.get_stream(url_sub, stop_event, title="Yomi (DUB)")
        if result_sub:
            result.append(result_sub)

        return result if result else None

if __name__ == "__main__":
    scraper = YomiScraper()
    response = scraper.get_series("165159", "127")
    print(response)
  