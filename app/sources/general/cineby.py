import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event


class CinebyScraper(Scraper):
    def __init__(self):
        super().__init__(headless=False, source="cineby")
        self.base_url = "https://cineby.at"

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/movie/{tmdb_id}?play=true"
        result = self.get_stream(url, stop_event, title="Web | Cineby")
        if result: 
            proxy_result = Proxy.get_proxy_url(result['url'], origin=self.base_url)
            if not proxy_result: return
            result['url'] = proxy_result
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}?play=true"
        result = self.get_stream(url, stop_event, title="Web | Cineby")
        if result: 
            proxy_result = Proxy.get_proxy_url(result['url'], origin=self.base_url)
            if not proxy_result: return
            result['url'] = proxy_result
        return result
    

if __name__ == "__main__":
    test_movie_id = "687163"  # John Wick: Chapter 4
    # test_movie_id = "1257957" # bison: kaalamaadan
    test_series_id = "1399"    # Game of Thrones

    scraper = CinebyScraper()
    
    # print(f"Testing movie ID {test_movie_id}...")
    # movie_response = scraper.get_movie(test_movie_id)
    # print(f"Movie response: {movie_response}")

    series_response = scraper.get_series(test_series_id, "1", "1")
    print(f"Series response: {series_response}")