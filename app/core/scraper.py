import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional, Any
from playwright.sync_api import Browser, Request, Response, sync_playwright
from app.models.responses import *
import re, time
from app.core.logger import Logger

STREAM_URL_PATTERN = r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/)\S*'
SUBTITLE_PATTERN   = r'https?://\S*[._/?&#=-](?:vtt|srt|ass)(?:\W|$)'

class Scraper:
    def __init__(self, headless: bool = True, source: str = "scraper", timeout: int = 30000, subtitle_timeout: float = 0):
        self.logger = Logger(f"scraper.{source}")
        self.source = source.upper()
        self.timeout = timeout
        self.subtitle_timeout = subtitle_timeout
        self.headless = headless

        self.playwright_manager: Optional[Any] = None
        self.playwright: Any = None
        self.browser: Optional[Browser] = None

    def _ensure_browser(self):
        if self.browser is not None:
            return

        # Lazily start Playwright only when the first request is made
        self.playwright_manager = sync_playwright()
        self.playwright = self.playwright_manager.start()
        assert self.playwright is not None
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.logger.info("Browser instance successfully launched in background")


    def get_stream(self, url: str) -> Optional[StreamResponse]:
        """Spins up a lightweight isolated tab session, runs fast, and cleans up."""
        self._ensure_browser()
        assert self.browser is not None
        context = self.browser.new_context()
        page = context.new_page()

        stream_url: Optional[str] = None
        subtitle_urls: list[str] = []
        start_time = time.time()

        try:
            # Trigger navigation which generates network traffic
            page.goto(url)

            # 1) Wait up to `self.timeout` (default 30s) for a stream URL request
            try:
                with page.expect_event(
                    "request",
                    predicate=lambda req: bool(re.search(STREAM_URL_PATTERN, req.url, re.I)),
                    timeout=self.timeout,
                ) as stream_event:
                    stream_request: Request = stream_event.value
                    stream_url = stream_request.url
                    self.logger.info(f"🎥 Stream: {stream_url}")
            except Exception: self.logger.warning(f"Timeout! No stream found within {self.timeout / 1000:.2f}s")

            # 2) After stream wait completes, listen for any subtitle requests that may come in within the next 3s
            if stream_url and self.subtitle_timeout > 0:
                try:
                    with page.expect_event(
                        "response",
                        predicate=lambda resp: bool(re.search(SUBTITLE_PATTERN, resp.url, re.I)),
                        timeout=self.subtitle_timeout,
                    ) as sub_event:
                        subtitle_response: Response = sub_event.value
                        if subtitle_response.url not in subtitle_urls:
                            subtitle_urls.append(subtitle_response.url)
                            self.logger.info(f"💬 Subtitles: {subtitle_response.url}")
                except Exception:
                    self.logger.warning(f"Timeout! No subtitle found within {self.subtitle_timeout:.2f}s after stream detection")

            # Finalize result: success if stream_url found, otherwise failed/partial handled below
            if stream_url:
                return StreamResponse(
                    title="Play", # TODO: Extract actual title from page content if needed
                    url=stream_url,
                    subtitles=subtitle_urls
                )

        except Exception as e:
            self.logger.error(f"Scraping error: {e}")

            # If execution reaches here, either an exception occurred or no stream was found.
            if stream_url:
                return StreamResponse(
                    title="Play",  # TODO: Extract actual title from page content if needed
                    url=stream_url,
                    subtitles=subtitle_urls
                )

        finally:
            elapsed_ms = int((time.time() - start_time) * 1000)
            self.logger.info(f"Response time: {elapsed_ms / 1000:.2f}s")
            # Always clean up system processes to preserve your server memory
            page.close()
            context.close()


    def shutdown(self):
        self.logger.info(f"Closing browser and cleaning system processes...")
        if hasattr(self, 'browser') and self.browser:
            self.browser.close()
        self.logger.info("🧹 Clean shutdown complete.")


if __name__ == "__main__":
    test_url = "https://flickystream.su/player/movie/687163"

    scraper = Scraper(headless=True, source="flickystream")
    response = scraper.get_stream(test_url)
    print(f"Response: {response}")