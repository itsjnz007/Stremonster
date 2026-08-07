# from re import match
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from app.core.parsers import Parsers
from app.models.metadata import Metadata
import asyncio
from app.core.scraper import Scraper
from app.core.proxy import Proxy

parsers = Parsers()

class Moviesda(Scraper):
    async def search_page(self, url: str) -> list[WebResponse]:
        try:
            assert Scraper._browser is not None
            context = await Scraper._browser.new_context()
            page = await context.new_page()
            await page.goto(url)
            search_data = await page.evaluate("""
                () => {
                    const items = Array.from(document.querySelectorAll('div.f'));
                    return items.map(item => {
                        const link = item.querySelector('a');
                        return {
                            text: link?.innerText.trim() || '',
                            url: link?.href || ''
                        };
                    });
                }
            """)

            search_results: list[Metadata] = []
            for item in search_data:
                if item['text']:
                    meta = parsers.parse_metadata(item['text'], item['url'])
                    search_results.append(meta)

            from pprint import pprint
            # print("\nresults ->")
            # pprint(search_results)

            search_matches = parsers.find_all_matches(input_title=self.title, input_year=self.year, metadata_list=search_results)
            # print("\nmatches ->")
            # pprint(search_matches)

            page.on("download", lambda download: download.cancel())
            self.subtitle_timeout = 0

            results: list[WebResponse] = []

            for search_match in search_matches:
                await page.goto(search_match.url)
                quality_data = await page.evaluate("""
                    () => {
                        const items = Array.from(document.querySelectorAll('.file-item'));
                        return items.map(item => {
                            const link = item.querySelector('a.file-item-link');
                            const badge = item.querySelector('.file-item-badge')?.innerText.trim() || '';
                            const metaText = item.querySelector('.file-item-meta')?.innerText.trim() || '';
                            
                            // Extract Hits and Size using regex
                            const hitsMatch = metaText.match(/Hits:\\s*(\\d+)/i);
                            const sizeMatch = metaText.match(/Size:\\s*([\\d\\.]+\\s*[KMGT]?B)/i);

                            return {
                                text: link?.innerText.trim() || '',
                                url: link?.href || '',
                                resolution: badge,
                                hits: hitsMatch ? hitsMatch[1] : '',
                                size: sizeMatch ? sizeMatch[1] : ''
                            };
                        });
                    }
                """)

                for res in reversed(quality_data):
                    try:
                        await page.goto(res['url'])
                        download_data_1 = await page.evaluate("""
                            () => {
                                const link = document.querySelector('a.dwnLink');
                                if (!link) return null;
                                
                                return {
                                    text: link.getAttribute('title') || link.innerText.trim(),
                                    url: link.href
                                };
                            }
                        """)

                        await page.goto(download_data_1['url'])
                        download_data_2 = await page.evaluate("""
                            () => {
                                const link = document.querySelector('a.dwnLink');
                                if (!link) return null;

                                const buttonText = link.querySelector('td.dl-btn')?.innerText.trim() || '';

                                return {
                                    title: link.getAttribute('title') || '',
                                    url: link.href,
                                    buttonText: buttonText
                                };
                            }
                        """)
                        pprint(download_data_2)

                        stream = await self._get_stream_async(download_data_2['url'], title=f"Tamilblasters{' (' + ' + '.join(lang.title() for lang in search_match.languages) + ')' if search_match.languages else ''}", name=search_match.quality)
                        if stream: 
                            results.append(stream)
                            break  # Exit the loop after successfully getting a stream

                    except Exception as e:
                        self.logger.error(f"Error processing quality data: {e}")
                        continue

            return results

        except Exception as e:
            self.logger.error(f"Hook error: {e}")
            return []


    def __init__(self):
        super().__init__(source="moviesda",
                         timeout=500,
                         base_url="https://www.moviesda.vision",
                         )
    
    def get_movie(self, title: str, year: str) -> list[WebResponse]:
        self.title, self.year = title, year
        url = f"{self.base_url}/mobile/search?find={title}&per_page=1"

        self._ensure_browser()
        future = asyncio.run_coroutine_threadsafe(self.search_page(url), self._loop) # type: ignore
        responses = future.result(timeout=60)

        for response in responses: 
            response = Proxy.get_proxy_url(response)

        return responses
        

if __name__ == "__main__":
    scraper = Moviesda()
    print(
        scraper.get_movie("dark giant", "2026")
    )