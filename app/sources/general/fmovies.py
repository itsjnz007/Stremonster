import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
from playwright.async_api import Page

async def click_play_button(page: Page) -> None:
    # Matches the button on mobile (via SVG shape) and desktop (via SVG or text)
    play_button = page.locator("button:has(polygon), button:has-text('Play')").first
    
    await play_button.click()


class FmoviesScraper(Scraper):
    def __init__(self):
        super().__init__(source="fmovies", base_url="https://www.fmovies.gd", page_hook=click_play_button)

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/movie/{tmdb_id}"
        result = self.get_stream(url, stop_event)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}"
        result = self.get_stream(url, stop_event)
        return result

if __name__ == "__main__":
    scraper = FmoviesScraper()
    
    series_response = scraper.get_series("48891", "6", "6")
    print(f"Series response: {series_response}")
