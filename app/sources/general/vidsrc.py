import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
from playwright.async_api import Page

async def page_hook(page: Page, _: Optional[Event]) -> None:
    player_iframe = page.frame_locator("#player_iframe")
    target_button = player_iframe.locator("#pl_but")
    await target_button.wait_for(state="attached")
    await target_button.click()
    
class VidsrcScraper(Scraper):
    def __init__(self):
        super().__init__(source="vidsrc", 
                         base_url="https://vsembed.ru",
                         page_hook=page_hook
        )

    def get_movie(self, tmdb_id: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/embed/movie/{tmdb_id}"
        result = self.get_stream(url, stop_event)
        return result
    
    def get_series(self, tmdb_id: str, season: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/embed/tv/{tmdb_id}/{season}/{episode}"
        result = self.get_stream(url, stop_event)
        return result

if __name__ == "__main__":
    scraper = VidsrcScraper()
    
    response = scraper.get_series("48891", "6", "6")
    print(f"Response: {response}")
