import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
from playwright.async_api import Page

class FourAnimoScraper(Scraper):
    def __init__(self):
        async def play_button_hook(page: Page):
            try:
                # Use a more specific selector: 
                # The .jw-icon-display class is the one that appears in the center of the video
                # The :visible pseudo-class ensures we only try to click the one currently shown
                selector = ".jw-icon-display.jw-icon[aria-label='Play']:visible"
                
                # Wait for the element to be present
                await page.wait_for_selector(selector, timeout=15000)
                
                # Click the first match specifically
                await page.locator(selector).first.click(force=True)
                
                print("Successfully clicked the main display play button.")
            except Exception as e:
                print(f"Hook error: {e}")

        super().__init__(headless=True, source="4animo",
                          stream_url_pattern= r'https?://[^\s]+\?t=[^\s&]+&type=[^\s]+',
                          page_hook=play_button_hook)
        self.base_url = "https://cdn.4animo.xyz"
    
    def get_series(self, anilist_id: str, episode: str, stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}/api/embed/hd-1/ani/{anilist_id}/{episode}/sub?k=1&autoPlay=1"
        result = self.get_stream(url, stop_event, title="Web | Anime")
        if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
        return result
        

if __name__ == "__main__":
    scraper = FourAnimoScraper()
    print(scraper.get_series('21', '1000'))