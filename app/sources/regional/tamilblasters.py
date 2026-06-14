import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from typing import Optional
from threading import Event
from playwright.async_api import Page
# from app.external.tmdb import Tmdb
# from app.core.caching import TmdbCache

class TamilBlasters(Scraper):
    def __init__(self):
        async def search_hook(page: Page):
            try:
                first_url = await page.evaluate("document.querySelector('.posts-wrapper article:first-child a')?.href")
                if not first_url: return
                await page.goto(first_url)

            except Exception as e:
                print(f"Hook error: {e}")

        super().__init__(headless=True, source="tamilblasters",
                          page_hook=search_hook)
        self.base_url = "https://www.1tamilblasters.republican/"
    
    def get_movie(self, title: str, language: str = "tamil", stop_event: Optional[Event] = None) -> Optional[WebResponse]:
        url = f"{self.base_url}?s={title}+{language}"
        result = self.get_stream(url, stop_event, title=f"Web | {language.title()}")
        if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
        return result
        

# if __name__ == "__main__":
    # scraper = FourAnimoScraper()
    # print(scraper.get_movie('tt33372494'))