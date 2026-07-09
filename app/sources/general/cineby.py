import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
from playwright.async_api import Page


async def click_play_button(page: Page) -> None:
    """Click the play button on the page."""
    try:
        # Wait for the button to be visible
        await page.wait_for_selector("button svg path[d='M8 5v14l11-7z']", timeout=5000)
        
        # Find and click the play button
        play_button = await page.query_selector("button:has(svg path[d='M8 5v14l11-7z'])")
        if play_button:
            await play_button.click()
    except Exception as e:
        print(f"Could not click play button: {e}")


class CinebyScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="cineby", base_url="https://player.videasy.to", page_hook=click_play_button)
        # self.base_url = "https://cineby.cc"
        # self.base_url = "https://cineby.at"

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/movie/{tmdb_id}"
        # url = f"{self.base_url}/movie/{tmdb_id}?play=true"
        result = self.get_stream(url, stop_event, title="Web | Cineby")
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}"
        # url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}?play=true"
        result = self.get_stream(url, stop_event, title="Web | Cineby")
        return result
    

if __name__ == "__main__":
    test_movie_id = "936075"  # Michael Jackson
    test_series_id = "1399"    # Game of Thrones

    scraper = CinebyScraper()
    
    # print(f"Testing movie ID {test_movie_id}...")
    # movie_response = scraper.get_movie(test_movie_id)
    # print(f"Movie response: {movie_response}")

    series_response = scraper.get_series(test_series_id, "1", "1")
    print(f"Series response: {series_response}")