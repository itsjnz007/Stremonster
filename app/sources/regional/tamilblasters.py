import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from app.core.parsers import Parsers
from app.models.metadata import Metadata
import asyncio
from app.core.multithreading import MultiThreading
from app.core.scraper import Scraper

parsers = Parsers()

class TamilBlasters(Scraper):
    async def search_page(self, url: str) -> list[Metadata]:
        try:
            assert Scraper._browser is not None
            context = await Scraper._browser.new_context()
            page = await context.new_page()
            await page.goto(url)
            raw_data = await page.evaluate("""
                () => {
                    const articles = Array.from(document.querySelectorAll('.posts-wrapper article'));
                    return articles.map(article => ({
                        text: article.innerText || '',
                        url: article.querySelector('a')?.href || ''
                    }));
                }
            """)

            results: list[Metadata] = []
            for item in raw_data:
                if item['text']:
                    meta = parsers.parse_metadata(item['text'], item['url'])
                    results.append(meta)

            # from pprint import pprint
            # print("\nresults ->")
            # pprint(results)

            matches = parsers.find_all_matches(input_title=self.title, input_year=self.year, metadata_list=results)
            # print("\nmatches ->")
            # pprint(matches)
            return matches

        except Exception as e:
            self.logger.error(f"Hook error: {e}")
            return []

    def __init__(self):
        super().__init__(headless=True, source="tamilblasters", log_requests=False, timeout=10000)
        self.base_url = "https://www.1tamilblasters.republican"
    
    def get_movie(self, title: str, year: str, threadpool: MultiThreading) -> list[WebResponse]:
        self.title, self.year = title, year
        url = f"{self.base_url}/?s={title}"

        self._ensure_browser()
        future = asyncio.run_coroutine_threadsafe(self.search_page(url), self._loop) # type: ignore
        results = future.result(timeout=60)

        responses = [
            r for r in threadpool.get_all([
                lambda event, r=m: self.get_stream(
                    r.url, 
                    event, 
                    title=f"Web | Tamilblasters{' | ' + ' + '.join(lang.title() for lang in r.languages) if r.languages else ''}"
                ) for m in results
            ]) if r
        ]   
        for response in responses: response['url'] = Proxy.get_proxy_url(response['url'], origin=self.base_url)

        return responses
        

if __name__ == "__main__":
    scraper = TamilBlasters()
    threading = MultiThreading()
    print(
        scraper.get_movie("Blast", "2026", threading)
    )