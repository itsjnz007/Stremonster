import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Any, Optional, cast
from threading import Event
import requests, re
from urllib.parse import urljoin

class FourAnimoScraper(Scraper):
    def __init__(self):
        super().__init__(source="4animo",
                          base_url="https://cdn.4animo.xyz"
                          )
    
    def _get_stream(self, anilist_id: str, episode: str, language: str) -> Optional[WebResponse]:
        url = f"{self.base_url}/embed/ani/{anilist_id}/{episode}/{language}"
        self.logger.info(f"GET stream: {url}")
        response_1 = requests.get(url, headers=self.headers)
        if response_1.status_code != 200:
            return None

        match = re.search(r'''var\s+sourcesUrl\s*=\s*['"]([^'"]+)['"]''', response_1.text)
        if not match:
            self.logger.warning(f"Could not find sourcesUrl in the response for {url}")
            return None

        sources_url = urljoin(self.base_url, match.group(1))
        response_2 = requests.get(sources_url, headers=self.headers)
        if response_2.status_code != 200:
            return None

        data: dict[str, Any] = response_2.json()
        sources = data.get('sources', [])
        if not sources:
            return None

        source_url = urljoin(self.base_url, sources[0].get('file', ''))
        tracks: list[dict[str, str]] = []
        for track in data.get('tracks', []):
            if isinstance(track, dict):
                track_data = cast(dict[str, Any], track)
                tracks.append({
                    'file': urljoin(self.base_url, str(track_data.get('file', ''))),
                    'label': str(track_data.get('label', 'English')),
                })
        return self.build_response(source_url, tracks, title=f"{self.source.title()} ({language})")

    def _get_sub(self, anilist_id: str, episode: str) -> Optional[WebResponse]:
        return self._get_stream(anilist_id, episode, 'sub')

    def _get_dub(self, anilist_id: str, episode: str) -> Optional[WebResponse]:
        return self._get_stream(anilist_id, episode, 'dub')

    def get_series(self, anilist_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[list[WebResponse]]:
        results: list[WebResponse] = []
        sub_response = self._get_sub(anilist_id, episode)
        if sub_response:
            results.append(sub_response)
        dub_response = self._get_dub(anilist_id, episode)
        if dub_response:
            results.append(dub_response)
        return results if results else None

if __name__ == "__main__":
    scraper = FourAnimoScraper()
    print(scraper.get_series('21356', '1'))