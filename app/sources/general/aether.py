import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.models.responses import WebResponse
from typing import Optional
from threading import Event
import requests
from app.core.logger import Logger
import logging
from app.core.scraper import Scraper

logger = Logger('aether', logging.INFO)

class Nebula(Scraper):
    def __init__(self, source: str = "nebula") -> None:
        super().__init__(base_url = "https://nebula.aether.cx", source=source)
        
    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"{self.base_url}/movie/{tmdb_id}?ser=tik", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('streams', [{}])[0].get('url'))

    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}?ser=tik", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('streams', [{}])[0].get('url'))

class Lul(Scraper):
    def __init__(self, source: str = "lul") -> None:
        super().__init__(base_url = "https://lul.aether.cx", source=source)
        
    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"{self.base_url}/movie/{tmdb_id}", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('stream'))

    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('stream'))

class Link(Scraper):
    headers_2 = {
        "Origin": "https://nextgencloudfabric.com",
        "Referer": "https://nextgencloudfabric.com/"
    }
    def __init__(self, source: str = "link") -> None:
        super().__init__(base_url = "https://link.aether.cx", source=source)

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"{self.base_url}/movie/{tmdb_id}", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('stream'), headers=self.headers_2)

    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response = requests.get(f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}", headers=self.headers)
        if response.status_code in [200]: return self.build_response(response.json().get('stream'), headers=self.headers_2)
        
    

if __name__ == "__main__":
    scraper = Nebula()
    res = scraper.get_movie("634649")
    print(f"Response: {res}")

    scraper = Lul()
    res = scraper.get_movie("652")
    print(f"Response: {res}")

    scraper = Link()
    res = scraper.get_movie("652")
    print(f"Response: {res}")