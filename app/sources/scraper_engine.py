import sys
from pathlib import Path
from typing import Optional, Callable

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.proxy import Proxy
from app.core.scraper import Scraper
from app.models.responses import WebResponse
from app.core.multithreading import MultiThreading
from app.core.logger import Logger
from threading import Event

logger = Logger("general")
thread_pool = MultiThreading(max_workers=9)


class ScraperEngine(Scraper):

    def __init__(
        self,
        source: str,
        movie_sources: Optional[list[str]] = None,
        series_sources: Optional[list[str]] = None,
        anime_series_sources: Optional[list[str]] = None,
    ):
        super().__init__(headless=True, source=source)

        self.movie_sources = movie_sources or []
        self.series_sources = series_sources or []
        self.anime_series_sources = anime_series_sources or []

    def _run_sources(
        self,
        sources: list[str],
        worker_factory: Callable[[str], Callable[[Event], Optional[WebResponse]]]
    ) -> Optional[WebResponse]:

        if not sources:
            raise ValueError("No sources configured")

        tasks = [(url, worker_factory(url)) for url in sources]

        # print(f"tasks - > {len(tasks)} - {tasks}")

        result = thread_pool.get_first([fn for _, fn in tasks])

        if not result:
            return None

        # fallback to first source
        origin = sources[0]

        result["url"] = Proxy.get_proxy_url(
            result["url"],
            origin=origin
        )

        return result

    def get_movie(self, tmdb_id: str) -> Optional[WebResponse]:
        return self._run_sources(
            self.movie_sources,
            lambda url: lambda event: self.get_stream(url % tmdb_id, event)
        )

    def get_series(
        self,
        tmdb_id: str,
        season: str,
        episode: str
    ) -> Optional[WebResponse]:

        return self._run_sources(
            self.series_sources,
            lambda url: lambda event: self.get_stream(
                url % (tmdb_id, season, episode, event)
            )
        )

    def get_anime_series(
        self,
        anilist_id: str,
        episode: str
    ) -> Optional[WebResponse]:

        return self._run_sources(
            self.anime_series_sources,
            lambda url: lambda event: self.get_stream(
                url % (anilist_id, episode, event)
            )
        )
    
class GeneralScraper(ScraperEngine):
    def __init__(self):
        movie_sources = [
            "https://www.vidsrc.wtf/1/movie/%s",
            "https://flickystream.su/player/movie/%s",
            "https://vidking.net/embed/movie/%s",
            "https://www.vidsrc.wtf/1/movie/%s",
            "https://flickystream.su/player/movie/%s",
            "https://vidking.net/embed/movie/%s",
            "https://www.vidsrc.wtf/1/movie/%s",
            "https://flickystream.su/player/movie/%s",
            "https://vidking.net/embed/movie/%s",
        ]

        series_sources = [
            "https://www.vidsrc.wtf/1/tv/%s/%s/%s",
            "https://flickystream.su/player/tv/%s/%s/%s",
            "https://vidking.net/embed/movie/%s/%s/%s"
        ]
        super().__init__(source="general", movie_sources=movie_sources, series_sources=series_sources)

class AnimeScraper(ScraperEngine):
    def __init__(self):
        series_sources = [
            "https://vidnest.fun/anime/%s/%s/sub"
            "https://www.miruro.tv/watch/%s/%s",
            # "https://vidking.net/embed/movie/%s/%s/%s"
        ]
        super().__init__(source="general", anime_series_sources=series_sources)

if __name__ == "__main__":
    scraper = GeneralScraper()
    scraper.get_movie("936075")
    # scraper = AnimeScraper()
    # scraper.get_anime_series('21', '1000')