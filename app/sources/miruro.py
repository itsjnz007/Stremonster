import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional

class MiruroScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="miruro", timeout=30000,
                          stream_url_pattern= r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/|/seg)\S*')
        # self.base_url = "https://www.miruro.tv"
        self.base_url = "https://vidnest.fun"
        # self.anibridge = AniBridgeV3Resolver()

    def get_movie(self, imdb_id: str) -> Optional[WebResponse]:
        return None
        url = f"{self.base_url}/watch/{imdb_id}"
        result = self.get_stream(url)
        # if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
        return result
    
    def get_series(self, animal_id: str, episode: str) -> Optional[WebResponse]:
        # url = f"{self.base_url}/watch/{animal_id}?ep={episode}"
        url = f"{self.base_url}/anime/{animal_id}/{episode}/sub"
        result = self.get_stream(url)
        if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
        return result
    

if __name__ == "__main__":
    test_series_id = "21" # One Piece

    scraper = MiruroScraper()

    series_response = scraper.get_series(test_series_id, "1166")
    print(f"Series response: {series_response}")