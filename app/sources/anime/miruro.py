import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class MiruroScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="miruro",
                          stream_url_pattern= r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/|/seg)\S*',log_requests=True)
        self.base_url = "https://www.miruro.tv"
    
    def get_series(self, animal_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/watch/{animal_id}?ep={episode}"
        result = self.get_stream(url, stop_event, title="Web | Miruro (Anime)")
        if result: 
            proxy_result = Proxy.get_proxy_url(result['url'], origin=self.base_url)
            if not proxy_result: return
            result['url'] = proxy_result
            result['origin'] = self.base_url
        return result
    

if __name__ == "__main__":
    scraper = MiruroScraper()
    imdb_id = "tt21209804"
    from app.external.anilist import AniBridgeV3Resolver
    anilist = AniBridgeV3Resolver()
    anilist_id, eps = anilist.get_anilist_info(imdb_id, "1", "8")
    response = scraper.get_series(anilist_id, str(eps))
    print(response)