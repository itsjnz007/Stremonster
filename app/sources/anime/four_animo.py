import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
import requests, re

class FourAnimoScraper(Scraper):
    def __init__(self):
        super().__init__(source="4animo",
                          base_url="https://cdn.4animo.xyz"
                          )
    
    def get_series(self, anilist_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/embed/hd-1/ani/{anilist_id}/{episode}/sub?k=1&autoPlay=1"
        self.logger.info(f"GET stream: {url}")
        response_1 = requests.get(url, headers=self.headers)
        if response_1.status_code in [200]:
            html = response_1.text
            match = re.search(
                r'''var\s+sourcesUrl\s*=\s*['"]([^'"]+)['"]''',
                html
            )
            if match: 
                api_path = match.groups()[0]
                response_2 = requests.get(f"{self.base_url}{api_path}", headers=self.headers)
                if response_2.status_code in [200]:
                    json = response_2.json()
                    sources = json.get('sources', []),
                    if sources:
                        source_url = self.base_url + sources[0][0].get('file')
                        tracks = [self.base_url + url for url in json.get('tracks', [])]

                        return self.build_response(
                            source_url,
                            tracks
                        )
        

if __name__ == "__main__":
    scraper = FourAnimoScraper()
    print(scraper.get_series('56566', '129'))