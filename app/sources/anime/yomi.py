import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import List, Optional
from threading import Event
import requests, re

class YomiScraper(Scraper):
    def __init__(self):
        super().__init__(source="yomi",
                          base_url="https://yomi.to"
                          )
    def _get_stream(self, mal_id: str, episode: str, language: str) -> Optional[WebResponse]:
        url = f"https://megaplay.buzz/stream/mal/{mal_id}/{episode}/{language}"
        self.logger.info(f"GET stream: {url}")
        response_1 = requests.get(url, headers=self.headers)
        if response_1.status_code in [200]:
            html = response_1.text
            match = re.search(
                r'id=["\']megaplay-player["\'][^>]*'
                r'data-id=["\']([^"\']+)["\'][^>]*'
                r'data-realid=["\']([^"\']+)["\'][^>]*'
                r'data-mediaid=["\']([^"\']+)["\']',
                html
            )
            if match: 
                data_id, real_id, media_id = match.groups() # type: ignore
                response_2 = requests.get(f"https://megaplay.buzz/stream/getSources?id={data_id}&id={data_id}", headers=self.headers)
                if response_2.status_code in [200]:
                    json = response_2.json()
                    return self.build_response(
                        json.get('sources', {}).get('file'),
                        json.get('tracks', []),
                        title=f"{self.source.title()} ({language})"
                    )
    def _get_sub(self, mal_id: str, episode: str) -> Optional[WebResponse]:
        return self._get_stream(mal_id, episode, 'sub')

    def _get_dub(self, mal_id: str, episode: str) -> Optional[WebResponse]:
        return self._get_stream(mal_id, episode, 'dub')
    
    def get_series(self, mal_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[List[WebResponse]]:
        results: List[WebResponse] = []
        sub_response = self._get_sub(mal_id, episode)
        if sub_response:
            results.append(sub_response)
        dub_response = self._get_dub(mal_id, episode)
        if dub_response:
            results.append(dub_response)
        return results if results else None

if __name__ == "__main__":
    scraper = YomiScraper()
    print(scraper.get_series('21356', '1'))