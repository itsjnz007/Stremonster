import sys
import asyncio
import threading, logging
from pathlib import Path

from app.core.proxy import Proxy
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.async_api import Browser, async_playwright, Request
from app.models.responses import *
import re, time
from app.core.logger import Logger
from urllib.parse import urlparse
from threading import Event
from typing import Optional, Callable, Awaitable
from playwright.async_api import Page, Playwright, BrowserContext

STREAM_URL_PATTERN = r'https?://\S*(?:\.m3u8|\.mp4|/hls/|/stream/|/mp4)\S*'
SUBTITLE_PATTERN   = r'https?://\S*[._/?&#=-](?:vtt|srt|ass)(?:\W|$)'
# AD_BLOCK_LIST = [
#     "**/adsense/**",
#     "**/doubleclick.net/**",
#     "**/google-analytics.com/**",
#     "**/googletagmanager.com/**",
#     "**/analytics.js",
#     "**/adservice/**",
# ]

class Scraper:
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _loop_thread: Optional[threading.Thread] = None
    _loop_ready = threading.Event()
    _browser_lock = threading.Lock()
    
    def __init__(self, 
                 base_url: str,
                 headless: bool = True, 
                 source: str = "scraper", 
                 timeout: int = 30000, 
                 subtitle_timeout: float = 0, 
                 stream_url_pattern: str = STREAM_URL_PATTERN, 
                 subtitle_url_pattern: str = SUBTITLE_PATTERN,
                 log_requests: bool = False,
                 page_hook: Optional[Callable[[Page], Awaitable[None]]] = None,
                 context_hook: Optional[Callable[[BrowserContext], Awaitable[None]]] = None
    ):
        self.logger = Logger(f"scraper.{source}", level=logging.DEBUG)
        self.source = source.upper()
        self.timeout = timeout
        self.subtitle_timeout = subtitle_timeout
        self.headless = headless
        self.stream_url_pattern = stream_url_pattern
        self.subtitle_url_pattern = subtitle_url_pattern
        self.log_requests = log_requests
        self.page_hook = page_hook
        self.context_hook = context_hook
        self.base_url = base_url

    def _start_loop(self):
        Scraper._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(Scraper._loop)
        Scraper._loop_ready.set()
        Scraper._loop.run_forever()

    def _ensure_loop(self):
        if Scraper._loop and Scraper._loop.is_running():
            return

        Scraper._loop_ready.clear()
        Scraper._loop_thread = threading.Thread(
            target=self._start_loop,
            daemon=True,
            name=f"playwright-loop-{self.source}",
        )
        Scraper._loop_thread.start()
        if not Scraper._loop_ready.wait(timeout=10):
            raise RuntimeError("Playwright event loop failed to start")

    async def _start_browser_async(self):
        Scraper._playwright = await async_playwright().start()
        Scraper._browser = await Scraper._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            ignore_default_args=["--enable-automation"],
        )
        self.logger.info("Browser instance successfully launched in background")

    def _ensure_browser(self):
        self._ensure_loop()
        if Scraper._browser is not None:
            # if self.context:
            #     return
            return

        with Scraper._browser_lock:
            if Scraper._browser is not None:
                # if self.context:
                #     return
                return

            assert Scraper._loop is not None
            future = asyncio.run_coroutine_threadsafe(self._start_browser_async(), Scraper._loop)
            future.result(timeout=30)

    async def _get_stream_async(self, url: str, stop_event: Optional[Event] = None,
                                title: Optional[str] = None,
                                name: Optional[str] = None) -> Optional[WebResponse]:
        if stop_event and stop_event.is_set(): return
        domain = urlparse(url).netloc
        assert Scraper._browser is not None
        # assert self.context is not None
        context = await Scraper._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 854, "height": 480},
            locale="en-US",
            java_script_enabled=True,
        )
        page = await context.new_page()

        stream_url: Optional[str] = None
        stream_headers: Optional[dict[str, Any]] = None
        subtitle_urls: list[str] = []
        start_time = time.time()

        def handle_request(request: Request):
            nonlocal stream_url
            nonlocal stream_headers
            if self.log_requests: self.logger.info(f"Request -> {request.url}")
            if re.search(self.stream_url_pattern, request.url, re.I):
                stream_url = request.url
                raw_headers = request.headers
                clean_headers: dict[str, Any] = {}
                
                for key, value in raw_headers.items():
                    # Strip outer escaped or duplicate quotes if present
                    cleaned_val = value.replace('\"', '')
                    clean_headers[key.lower()] = cleaned_val
                
                stream_headers = {}
                if clean_headers.get('referer'): stream_headers['referer'] = clean_headers['referer']
                if clean_headers.get('origin'): stream_headers['origin'] = clean_headers['origin']
                self.logger.info(f"🎥 Stream from {domain}: {stream_url}")

        try:
            # await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "stylesheet", "font"] else route.continue_())
            # await page.route("**/*", lambda route: 
            #     # route.abort() if any(pattern in route.request.url for pattern in AD_BLOCK_LIST) 
            #     # else route.continue_()
            # )
            if self.context_hook: await self.context_hook(context)
            page.on("request", handle_request)
            await page.goto(url)
            if self.page_hook: await self.page_hook(page)

            start_time = time.time()
            while not stream_url:
                if stop_event and stop_event.is_set(): 
                    self.logger.info(f"❌ Task skipped for {domain}")
                    return
                if time.time() - start_time > (self.timeout / 1000): break
                await asyncio.sleep(0.1)

            # for _ in range(int(self.timeout / 500)):
            #     if stop_event and stop_event.is_set(): 
            #         self.logger.debug(f"Stopping task due to a stop_event")
            #         break
            #     try:
            #         stream_request = await page.wait_for_event(
            #             "request",
            #             predicate=lambda req: bool(re.search(self.stream_url_pattern, req.url, re.I)),
            #             timeout=self.timeout,
            #         )
            #         stream_url = stream_request.url
            #         self.logger.info(f"🎥 Stream from {domain}: {stream_url}")
            #     except Exception:
            #         self.logger.warning(f"Timeout! No stream found within {self.timeout / 1000:.2f}s")

            # if stream_url and self.subtitle_timeout > 0:
            #     try:
            #         subtitle_response = await page.wait_for_event(
            #             "response",
            #             predicate=lambda resp: bool(re.search(self.subtitle_url_pattern, resp.url, re.I)),
            #             timeout=self.subtitle_timeout,
            #         )
            #         if subtitle_response.url not in subtitle_urls:
            #             subtitle_urls.append(subtitle_response.url)
            #             self.logger.info(f"💬 Subtitles: {subtitle_response.url}")
            #     except Exception:
            #         self.logger.warning(f"Timeout! No subtitle found within {self.subtitle_timeout:.2f}s after stream detection")

            if stream_url:
                return WebResponse(
                    title=title or self.source.title(),  # TODO: Extract actual title from page content if needed
                    name=name or "1080p / 720p",
                    url=stream_url,
                    subtitles=subtitle_urls,
                    headers=stream_headers
                )

        except Exception as e:
            self.logger.error(f"Scraping error: {e}")
            if stream_url:
                return WebResponse(
                    title=title or "Web",
                    name=name or "1080p / 720p",
                    url=stream_url,
                    subtitles=subtitle_urls,
                )

        finally:
            elapsed_ms = int((time.time() - start_time) * 1000)
            self.logger.info(f"Response time: {elapsed_ms / 1000:.2f}s")
            try: await page.close()
            except Exception: pass
            try:
                await context.close()
            except Exception:
                pass
        
        self.logger.info(f"END {url}")

        return None

    def get_stream(self, url: str, stop_event: Optional[Event] = None,
                   title: Optional[str] = None,
                   name: Optional[str] = None) -> Optional[WebResponse]:
        self._ensure_browser()
        assert Scraper._loop is not None

        self.logger.info(f"GET stream: {url}")

        future = asyncio.run_coroutine_threadsafe(self._get_stream_async(url, stop_event, title=title, name=name), Scraper._loop)
        try:
            result = future.result(timeout=(self.timeout / 1000) + 15)
            if result: 
                result = Proxy.get_proxy_url(result)
                if result: 
                    return result
        except Exception as e:
            self.logger.error(f"Scraping error: {e}")
            return None

    @classmethod
    async def _shutdown_async(cls):
        if Scraper._browser is not None:
            try:
                # if context is not None: await context.close()
                await Scraper._browser.close()
            except Exception:
                pass
            # self.context = None
            Scraper._browser = None

        if Scraper._playwright is not None:
            try:
                await Scraper._playwright.stop()
            except Exception:
                pass
            Scraper._playwright = None

    @classmethod
    def shutdown(cls):
        print("Closing browser and cleaning system processes...")
        if Scraper._loop and Scraper._loop.is_running():
            asyncio.run_coroutine_threadsafe(cls._shutdown_async(), Scraper._loop).result(timeout=30)
            Scraper._loop.call_soon_threadsafe(Scraper._loop.stop)
            if Scraper._loop_thread is not None:
                Scraper._loop_thread.join(timeout=5)
        print("🧹 Clean shutdown complete.")

import atexit
atexit.register(Scraper.shutdown)


if __name__ == "__main__":
    test_url = "https://flickystream.su/player/movie/687163"

    scraper = Scraper(headless=True, source="flickystream", base_url="https://flickystream.su")
    response = scraper.get_stream(test_url)
    print(f"Response: {response}")