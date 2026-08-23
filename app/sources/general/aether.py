import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.models.responses import WebResponse
from typing import Optional
from threading import Event
import requests
from app.core.logger import Logger
import logging
from app.core.proxy import Proxy

logger = Logger('aether', logging.INFO)


class AetherScraper():
    def __init__(self, source: str = "aether") -> None:
        self.source = source

    headers = {
        "Origin": "https://aether.ist",
        "Referer": "https://aether.ist/",
    }

    def build_response(self, url: Optional[str], headers: dict[str, str] = headers) -> Optional[WebResponse]:
        if not url: return
        return Proxy.get_proxy_url(WebResponse(
            url=url,
            name="1080p / 720p",
            title=self.source.title(),
            headers=headers,
            subtitles=[],
            contentType = None,
            behaviorHints = None,
            cacheMaxAge = None,
            staleRevalidate = None,
            staleError = None,
        ))

class Nebula(AetherScraper):
    def __init__(self, source: str = "nebula") -> None:
        super().__init__(source)
        
    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"https://nebula.aether.cx/movie/{tmdb_id}?ser=tik", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('streams', [{}])[0].get('url'))

    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"https://nebula.aether.cx/tv/{tmdb_id}/{season}/{episode}?ser=tik", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('streams', [{}])[0].get('url'))

class Link(AetherScraper):
    headers_2 = {
        "Origin": "https://nextgencloudfabric.com",
        "Referer": "https://nextgencloudfabric.com/"
    }
    def __init__(self, source: str = "link") -> None:
        super().__init__(source)

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"https://link.aether.cx/movie/{tmdb_id}", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('stream'), headers=self.headers_2)

    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"https://link.aether.cx/tv/{tmdb_id}/{season}/{episode}", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('stream'), headers=self.headers_2)
        
    

if __name__ == "__main__":
    scraper = Link()

    res = scraper.get_series("203614", "1", "1")
    print(f"Response: {res}")