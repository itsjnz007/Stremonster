import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.config import GENERIC_REQUEST_TIMEOUT
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
import requests
from app.core.logger import Logger
import logging
from app.core.scraper import Scraper
from app.core.parsers import Parsers

logger = Logger('aether', logging.INFO)
parsers = Parsers()

BASE_URL = "https://showbox.codiv.dpdns.org/%7B%22cookie%22%3A%22eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3OTIxNTM0OTcsIm5iZiI6MTc5MjE1MzQ5NywiZXhwIjoxODIzMjU3NTE3LCJkYXRhIjp7InVpZCI6MjUyMjYxMSwidG9rZW4iOiJkMGZlYWViMzU1YmE4NjViODM1ZTRjOGE4ZTA1MmYwZSJ9fQ.ScnVR-lw90SgGvBhRiubrG5I4UFIJ4q3ASo89QvRqD4%22%7D"

class Showbox(Scraper):
    def __init__(self, source: str = "showbox") -> None:
        super().__init__(base_url = BASE_URL, source=source)
        
    def get_movie(self, imdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/stream/movie/{imdb_id}.json"
        self.logger.info(f"GET stream: {url}")
        response = requests.get(url, headers=self.headers, timeout=GENERIC_REQUEST_TIMEOUT)
        print(response.status_code, response.text)
        if response.status_code in [200]: 
            parsed_response = [parsers.parse_metadata(item.get('title', ''), item.get('url', '')) for item in response.json().get('streams', [])]
            print(f"Parsed response: {parsed_response}")
            filtered_response = [item for item in parsed_response if item.size_kb is not None and item.size_kb < 10 * 1024 * 1024]  # Filter out items larger than 10 GB
            print(f"Filtered response: {filtered_response}")
            sorted_response = sorted(filtered_response, key=lambda x: (x.size_kb if x.size_kb is not None else float('inf')))
            print(f"Sorted response: {sorted_response}")
            return self.build_response(sorted_response[0].url, quality=sorted_response[0].quality) if sorted_response else None

    def get_series(self, imdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/stream/series/{imdb_id}:{season}:{episode}.json"
        self.logger.info(f"GET stream: {url}")
        response = requests.get(url, headers=self.headers, timeout=GENERIC_REQUEST_TIMEOUT)
        print(response.status_code, response.text)
        if response.status_code in [200]:
            parsed_response = [parsers.parse_metadata(item.get('title', ''), item.get('url', '')) for item in response.json().get('streams', [])]
            print(f"Parsed response: {parsed_response}")
            filtered_response = [item for item in parsed_response if item.size_kb is not None and item.size_kb < 10 * 1024 * 1024]  # Filter out items larger than 10 GB
            print(f"Filtered response: {filtered_response}")
            sorted_response = sorted(filtered_response, key=lambda x: (x.size_kb if x.size_kb is not None else float('inf')))
            print(f"Sorted response: {sorted_response}")
            return self.build_response(sorted_response[0].url, quality=sorted_response[0].quality) if sorted_response else None

if __name__ == "__main__":
    showbox = Showbox()
    # print(showbox.get_movie("tt1375666"))
    print(showbox.get_series("tt0944947", "1", "1"))