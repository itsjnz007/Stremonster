# from re import match
import sys
from pathlib import Path
from typing import Optional
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.scraper import Scraper
from app.models.responses import WebResponse
from app.core.parsers import Parsers
from app.models.metadata import Metadata
import asyncio
from app.core.scraper import Scraper
from pprint import pprint

parsers = Parsers()

class TamilMv(Scraper):
    async def search_page(self, url: str) -> list[WebResponse]:
        context = None
        page = None
        try:
            assert Scraper._browser is not None
            context = await Scraper._browser.new_context()
            assert context
            page = await context.new_page()
            await page.goto(url)

            await page.wait_for_selector("#results a.sRow", timeout=15000)

            # 2. Extract everything under #results cleanly using page.evaluate()
            search_data = await page.evaluate("""
                () => {
                    const rows = Array.from(document.querySelectorAll('#results a.sRow'));
                    return rows.map(row => {
                        const url = row.href;
                        const titleEl = row.querySelector('.sTitle');
                        
                        return {
                            text: titleEl ? titleEl.innerText.trim() : '',
                            url: url
                        };
                    });
                }
            """)

            # print(search_data)
            search_results: list[Metadata] = []
            for item in search_data:
                if item['text']:
                    meta = parsers.parse_metadata(item['text'], item['url'])
                    search_results.append(meta)

            # pprint(search_results)

            search_matches = parsers.find_all_matches(input_title=self.title, input_year=self.year, metadata_list=search_results)
            # print("\nmatches ->")
            pprint(search_matches)

            results: list[WebResponse] = []

            for search_match in search_matches:
                await page.goto(search_match.url)

                download_items = await page.evaluate("""
                    () => {
                        const buttons = Array.from(document.querySelectorAll('a.download-button'));
                        return buttons.map(btn => {
                            // Find the closest preceding <strong> element that contains the file release title info
                            let prevEl = btn.previousElementSibling;
                            let titleText = null;

                            while (prevEl) {
                                // Look for elements that look like a header/title block (usually a strong tag or containing resolution details)
                                if (prevEl.tagName === 'STRONG' || prevEl.querySelector('strong')) {
                                    const strongTag = prevEl.tagName === 'STRONG' ? prevEl : prevEl.querySelector('strong');
                                    const text = strongTag.innerText.trim();
                                    // Filter out non-title elements like the torrent filename or formatting tags
                                    if (text && !text.endsWith('.torrent') && !text.includes('MAGNET') && text.length > 15) {
                                        titleText = text.replace(':', '').trim();
                                        break;
                                    }
                                }
                                prevEl = prevEl.previousElementSibling;
                            }

                            // Fallback: search backwards through previous siblings text nodes or elements
                            if (!titleText) {
                                // Walk up text nodes / elements backwards to find the nearest title block
                                let walker = btn.previousSibling;
                                while (walker) {
                                    if (walker.nodeType === Node.ELEMENT_NODE) {
                                        if (walker.tagName === 'STRONG') {
                                            titleText = walker.innerText.replace(':', '').trim();
                                            break;
                                        }
                                        const foundStrong = walker.querySelector('strong');
                                        if (foundStrong) {
                                            titleText = foundStrong.innerText.replace(':', '').trim();
                                            break;
                                        }
                                    }
                                    walker = walker.previousSibling;
                                }
                            }

                            return {
                                name: titleText || "Unknown Title",
                                url: btn.href
                            };
                        });
                    }
                """)
                # print(f"-> Direct Link Found: {download_items}\n")

                for download_item in download_items:
                    try:
                        await page.goto(download_item['url'])
                        destination_url = await page.evaluate("""
                            () => {
                                const ctaBtn = document.querySelector('a#cta');
                                return ctaBtn ? ctaBtn.href : null;
                            }
                        """)
                        # print("Destination url -> ", destination_url)

                        await page.goto(destination_url)
                        final_download_url = await page.evaluate("""
                            () => {
                                const btn = document.querySelector('.download-grid a.download-btn');
                                return btn ? btn.href : null;
                            }
                        """)
                        # print("final download btn url -> ", final_download_url)

                        response = WebResponse( # type: ignore
                            title=f"Tamilmv{' (' + ' + '.join(lang.title() for lang in search_match.languages) + ')' if search_match.languages else ''}" or "Web",
                            name=search_match.quality or "1080p / 720p",
                            url=final_download_url,
                            subtitles=[]
                        )
                        results.append(response)
                        break

                    except Exception as e:
                        self.logger.error(f"Error processing quality data: {e}")
                        continue



            return results

        except Exception as e:
            self.logger.error(f"Hook error: {e}")
            return []

        finally:
            try:
                if page:
                    await page.close()
            except Exception: pass
            try:
                if context:
                    await context.close()
            except Exception: pass


    def __init__(self):
        super().__init__(source="moviesda",
                         timeout=500,
                         base_url="https://www.1tamilmv.lease",
                        #  headless=False
                         )
    
    def get_movie(self, title: str, year: Optional[str]) -> list[WebResponse]:
        self.title, self.year = title, year
        url = f"{self.base_url}/search?q={title}"

        self._ensure_browser()
        future = asyncio.run_coroutine_threadsafe(self.search_page(url), self._loop) # type: ignore
        responses = future.result(timeout=60)

        [res.update({'contentType': 'video/mp4'}) for res in responses]


        return responses
        

if __name__ == "__main__":
    scraper = TamilMv()
    print(
        scraper.get_movie("gatta kusthi 2", "2026")
    )