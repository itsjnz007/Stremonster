import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from app.external.anilist import AniBridgeV3Resolver

class DropfileScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="dropfile",
                          stream_url_pattern= r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/|/seg)\S*')
        self.base_url = "https://dropfile.cc"
        self.anibridge = AniBridgeV3Resolver()

    def get_movie(self, tmdb_id: str) -> Optional[WebResponse]:
        url = f"{self.base_url}/player/movie/{tmdb_id}"
        result = self.get_stream(url)
        if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str) -> Optional[WebResponse]:
        anilist_id, anilist_eps = self.anibridge.get_anilist_info(tmdb_id, season, episode)
        print(anilist_id, anilist_eps)
        url = f"{self.base_url}/player/tv/anilist-{anilist_id}/1/{anilist_eps}?audio=sub&lang=en"
        result = self.get_stream(url)
        if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
        return result
    

if __name__ == "__main__":
    test_series_id = "37854"    # Fire Force

    scraper = DropfileScraper()

    series_response = scraper.get_series(test_series_id, "20", "14")
    print(f"Series response: {series_response}")