import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class MiruroScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, base_url="https://www.miruro.tv", source="miruro",
                          stream_url_pattern= r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/|/seg)\S*',log_requests=True)
    
    def get_series(self, animal_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/watch/{animal_id}?ep={episode}"
        result = self.get_stream(url, stop_event, title="Web | Miruro (Anime)")
        return result
    

if __name__ == "__main__":
    scraper = MiruroScraper()
    imdb_id = "tt21209804"
    from app.external.anilist import AniBridgeV3Resolver
    anilist = AniBridgeV3Resolver()
    anilist_id, eps = anilist.get_anilist_info(imdb_id, "1", "8")
    response = scraper.get_series(anilist_id, str(eps))
    print(response)