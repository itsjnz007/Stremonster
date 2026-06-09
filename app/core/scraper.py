import sys
import asyncio
import threading, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional, Any
from playwright.async_api import Browser, async_playwright
from app.models.responses import *
import re, time
from app.core.logger import Logger

STREAM_URL_PATTERN = r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/)\S*'
SUBTITLE_PATTERN   = r'https?://\S*[._/?&#=-](?:vtt|srt|ass)(?:\W|$)'

class Scraper:
    def __init__(self, headless: bool = True, source: str = "scraper", timeout: int = 15000, subtitle_timeout: float = 0, 
                 stream_url_pattern: str = STREAM_URL_PATTERN, 
                 subtitle_url_pattern: str = SUBTITLE_PATTERN):
        self.logger = Logger(f"scraper.{source}", level=logging.DEBUG)
        self.source = source.upper()
        self.timeout = timeout
        self.subtitle_timeout = subtitle_timeout
        self.headless = headless
        self.stream_url_pattern = stream_url_pattern
        self.subtitle_url_pattern = subtitle_url_pattern

        self._playwright: Any = None
        self.browser: Optional[Browser] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_ready = threading.Event()
        self._browser_lock = threading.Lock()

    def _start_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._loop.run_forever()

    def _ensure_loop(self):
        if self._loop and self._loop.is_running():
            return

        self._loop_ready.clear()
        self._loop_thread = threading.Thread(
            target=self._start_loop,
            daemon=True,
            name=f"playwright-loop-{self.source}",
        )
        self._loop_thread.start()
        if not self._loop_ready.wait(timeout=10):
            raise RuntimeError("Playwright event loop failed to start")

    async def _start_browser_async(self):
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.logger.info("Browser instance successfully launched in background")

    def _ensure_browser(self):
        self._ensure_loop()
        if self.browser is not None:
            return

        with self._browser_lock:
            if self.browser is not None:
                return

            assert self._loop is not None
            future = asyncio.run_coroutine_threadsafe(self._start_browser_async(), self._loop)
            future.result(timeout=30)

    async def _get_stream_async(self, url: str) -> Optional[WebResponse]:
        assert self.browser is not None
        context = await self.browser.new_context()
        page = await context.new_page()

        stream_url: Optional[str] = None
        subtitle_urls: list[str] = []
        start_time = time.time()

        try:
            # page.on("request", lambda req: self.logger.debug(f"Request URL: {req.url}"))
            await page.goto(url)

            try:
                stream_request = await page.wait_for_event(
                    "request",
                    predicate=lambda req: bool(re.search(self.stream_url_pattern, req.url, re.I)),
                    timeout=self.timeout,
                )
                stream_url = stream_request.url
                self.logger.info(f"🎥 Stream: {stream_url}")
            except Exception:
                self.logger.warning(f"Timeout! No stream found within {self.timeout / 1000:.2f}s")

            if stream_url and self.subtitle_timeout > 0:
                try:
                    subtitle_response = await page.wait_for_event(
                        "response",
                        predicate=lambda resp: bool(re.search(self.subtitle_url_pattern, resp.url, re.I)),
                        timeout=self.subtitle_timeout,
                    )
                    if subtitle_response.url not in subtitle_urls:
                        subtitle_urls.append(subtitle_response.url)
                        self.logger.info(f"💬 Subtitles: {subtitle_response.url}")
                except Exception:
                    self.logger.warning(f"Timeout! No subtitle found within {self.subtitle_timeout:.2f}s after stream detection")

            if stream_url:
                return WebResponse(
                    title="Web",  # TODO: Extract actual title from page content if needed
                    name="1080p / 720p",
                    url=stream_url,
                    subtitles=subtitle_urls,
                )

        except Exception as e:
            self.logger.error(f"Scraping error: {e}")
            if stream_url:
                return WebResponse(
                    title="Web",
                    name="1080p / 720p",
                    url=stream_url,
                    subtitles=subtitle_urls,
                )

        finally:
            elapsed_ms = int((time.time() - start_time) * 1000)
            self.logger.info(f"Response time: {elapsed_ms / 1000:.2f}s")
            try:
                await page.close()
            except Exception:
                pass
            try:
                await context.close()
            except Exception:
                pass

        return None

    def get_stream(self, url: str) -> Optional[WebResponse]:
        self._ensure_browser()
        assert self._loop is not None

        future = asyncio.run_coroutine_threadsafe(self._get_stream_async(url), self._loop)
        try:
            return future.result(timeout=(self.timeout / 1000) + 15)
        except Exception as e:
            self.logger.error(f"Scraping error: {e}")
            return None

    async def _shutdown_async(self):
        if self.browser is not None:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def shutdown(self):
        self.logger.info("Closing browser and cleaning system processes...")
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown_async(), self._loop).result(timeout=30)
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread is not None:
                self._loop_thread.join(timeout=5)
        self.logger.info("🧹 Clean shutdown complete.")


if __name__ == "__main__":
    test_url = "https://flickystream.su/player/movie/687163"

    scraper = Scraper(headless=True, source="flickystream")
    response = scraper.get_stream(test_url)
    print(f"Response: {response}")