import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse, Subtitle
from typing import Optional
from threading import Event
import requests, re
from app.core.proxy import Proxy

class YomiScraper(Scraper):
    headers = {
        "Origin": "https://megaplay.buzz",
        "Referer": "https://megaplay.buzz/"
    }

    def __init__(self):
        super().__init__(source="yomi",
                          stream_url_pattern=r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/mp4)\S*',
                          base_url="https://yomi.to"
                          )

    def build_response(self, stream_url: Optional[str], subtitles: list[dict[str, str]], headers: dict[str, str] = headers) -> Optional[WebResponse]:
        if not stream_url: return
        return Proxy.get_proxy_url(WebResponse(
            url=stream_url,
            name="1080p / 720p",
            title=self.source.title()+" (Anime)",
            headers=headers,
            subtitles=[
                Subtitle(
                    id=i.get('label', 'eng'),
                    lang="eng",
                    url=i.get('file', '')
                )
                for i in subtitles
            ],
            contentType = None,
            behaviorHints = None,
            cacheMaxAge = None,
            staleRevalidate = None,
            staleError = None,
        ))
    
    def get_series(self, mal_id: Optional[str], episode: Optional[str], stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        response_1 = requests.get(f"https://megaplay.buzz/stream/mal/{mal_id}/{episode}/sub", headers=self.headers)
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
                print(response_2.text)
                if response_2.status_code in [200]:
                    json = response_2.json()
                    return self.build_response(
                        json.get('sources', {}).get('file'),
                        json.get('tracks', [])
                    )
        

if __name__ == "__main__":
    scraper = YomiScraper()
    print(scraper.get_series('56566', '129'))