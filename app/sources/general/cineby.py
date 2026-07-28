import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
from playwright.async_api import Page
import asyncio


async def click_play_button(page: Page, stop_event: Optional[Event]) -> None:
    for i in range(10): 
        if stop_event and stop_event.is_set(): return
        play_button = page.locator("button").first
        try: await play_button.click(force=True, timeout=500)
        except: pass
        await asyncio.sleep(0.2)
        print(f'button click {i}')


class CinebyScraper(Scraper):
    def __init__(self):
        super().__init__(source="cineby", base_url="https://player.videasy.to", page_hook=click_play_button)

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/movie/{tmdb_id}"
        # url = f"{self.base_url}/movie/{tmdb_id}?play=true"
        result = self.get_stream(url, stop_event, title="Cineby")
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}"
        # url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}?play=true"
        result = self.get_stream(url, stop_event, title="Cineby")
        return result
    

if __name__ == "__main__":
    scraper = CinebyScraper()

    series_response = scraper.get_movie("1325734")
    print(f"Series response: {series_response}")