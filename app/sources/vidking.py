import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional

class VidkingScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="vidking", timeout=10000)
        self.base_url = "https://vidking.net"

    def get_movie(self, tmdb_id: str) -> Optional[WebResponse]:
        url = f"{self.base_url}/embed/movie/{tmdb_id}"
        result = self.get_stream(url)
        if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str) -> Optional[WebResponse]:
        url = f"{self.base_url}/embed/tv/{tmdb_id}/{season}/{episode}"
        result = self.get_stream(url)
        if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
        return result
    

if __name__ == "__main__":
    test_movie_id = "687163"  # John Wick: Chapter 4
    test_series_id = "1399"    # Game of Thrones

    scraper = VidkingScraper()
    
    print(f"Testing movie ID {test_movie_id}...")
    movie_response = scraper.get_movie(test_movie_id)
    print(f"Movie response: {movie_response}")

    series_response = scraper.get_series(test_series_id, "1", "1")
    print(f"Series response: {series_response}")