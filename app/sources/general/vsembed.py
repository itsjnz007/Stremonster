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
    target_button = player_iframe.locator("#bigPlay")
    
    try:
        await target_button.wait_for(state="visible", timeout=15000)
        await target_button.click()
    except Exception as e:
        print(f"Failed to click button: {e}")
    
class Vsembed(Scraper):
    def __init__(self):
        super().__init__(source="vsembed", 
                        base_url="https://vsembed.su",
                        page_hook=page_hook,
                        headless=False
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
    scraper = Vsembed()
    
    response = scraper.get_series("3308", "6", "10")
    print(f"Response: {response}")
