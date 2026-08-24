import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
import requests, re

class YomiScraper(Scraper):
    def __init__(self):
        super().__init__(source="yomi",
                          base_url="https://yomi.to"
                          )
    
    def get_series(self, mal_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"https://megaplay.buzz/stream/mal/{mal_id}/{episode}/sub"
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
                        json.get('tracks', [])
                    )
        

if __name__ == "__main__":
    scraper = YomiScraper()
    print(scraper.get_series('56566', '129'))