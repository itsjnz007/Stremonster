import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event

class VidplayScraper(Scraper):
    def __init__(self):
        super().__init__(source="vidplay",
                          stream_url_pattern= r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/mp4|stream\?session=)\S*',
                          base_url="https://vidplay.to/"
                          )
    
    def get_series(self, imdb_id: str, tmdb_id: Optional[str], season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/stream/embed?imdbid={imdb_id}&type=series&season={season}&episode={episode}" + f"&tmdbid={tmdb_id}" if tmdb_id else ""
        result = self.get_stream(url, stop_event, title=f"{self.source.title()} (Anime)")
        return result
        

if __name__ == "__main__":
    scraper = VidplayScraper()
    print(scraper.get_series('tt0434665', '30984', '1', '1'))