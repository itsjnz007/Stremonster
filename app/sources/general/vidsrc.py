import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
from playwright.async_api import Page, BrowserContext

async def page_hook(page: Page) -> None:
    player_iframe = page.frame_locator("#player_iframe")
    target_button = player_iframe.locator("#pl_but")
    await target_button.wait_for(state="attached")
    await target_button.click()
    
async def context_hook(context: BrowserContext) -> None:
    try:
        await context.route("**/disable-devtool*", lambda route: route.abort())
        await context.add_init_script("""
            Object.defineProperty(window, 'DisableDevtool', {
                set(val) {
                    if (val && typeof val === 'object' || typeof val === 'function') {
                        val.isSuspend = true; // Neutralize the running process engine flags instantly
                    }
                    this._val = val;
                },
                get() {
                    return this._val;
                },
                configurable: true
            });
        """)
    except Exception as e:
        print(f"Context hook failed with error: {e}")
        

class VidsrcScraper(Scraper):
    def __init__(self):
        super().__init__(headless=True, source="vidsrc", 
                         base_url="https://vsembed.ru", 
                         context_hook=context_hook, 
                         page_hook=page_hook,
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
    
    response = scraper.get_movie("786892")
    print(f"Response: {response}")
