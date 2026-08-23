import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.responses import WebResponse, BehaviorHints
from app.core.multithreading import MultiThreading
from typing import List, Callable, Any, Optional, Iterator, Tuple
from app.core.logger import Logger
import logging
from app.sources.general import flicky as flicky, vidking as vidking, vidsrc as vidsrc, cineby as cineby, \
    vidnest as vidnest_general, viduki as viduki, fmovies as fmovies, \
    videasy as videasy, aether as aether
from app.sources.anime import miruro as miruro, vidnest as vidnest, four_animo as four_animo, \
    yomi as yomi
from app.sources.regional import tamilblasters as tamilblasters, moviesda as moviesda
from app.core.caching import TmdbCache, WebCache
from app.config import TUNNEL_URL
from app.external.tmdb import Tmdb
from app.external.anilist import AniBridgeV3Resolver

# General Scrapers
flicky_scraper = flicky.FlickyScraper()
vidking_scraper = vidking.VidkingScraper()
vidsrc_scraper = vidsrc.VidsrcScraper()
cineby_scraper = cineby.CinebyScraper()
vidnest_general_scraper = vidnest_general.VidnestScraper()
viduki_scraper = viduki.VidukiScraper()
fmovies_scraper = fmovies.FmoviesScraper()
videasy_scraper = videasy.VideasyScraper()
aether_scraper = aether.AetherScraper()

# Anime Scrapers
four_animo_scraper = four_animo.FourAnimoScraper()
miruro_scraper = miruro.MiruroScraper()
vidnest_scraper = vidnest.VidnestScraper()
yomi_scraper = yomi.YomiScraper()

# Regional Scrapers
tamilblasters_scraper = tamilblasters.TamilBlasters()
moviesda_scraper = moviesda.Moviesda()

# Other
anibride = AniBridgeV3Resolver()


class StreamExtractor:
    web_cache = WebCache()
    tmdb_cache = TmdbCache()
    tmdb_client = Tmdb(tmdb_cache)
    logger = Logger(f"extractor.stream", level=logging.DEBUG)
    threadpool = MultiThreading(max_workers=3)

    def __init__(self) -> None: pass

    def build_unified_stream_url(self, id: str, content_type: Optional[str] = None) -> str:
        if not TUNNEL_URL:
            raise Exception("TUNNEL_URL is not set. Please set it in the config.")
        if content_type == 'video/mp4': return TUNNEL_URL + f"/redirect.mp4?id={id}"
        if content_type == 'application/vnd.apple.mpegurl': return TUNNEL_URL + f"/redirect.m3u8?id={id}"
        return TUNNEL_URL + f"/redirect?id={id}"
    
    def build_web_response(self, id: str, type: str, streams: List[WebResponse], stream_idx: int, unified: bool = False) -> List[WebResponse]:
        imdb_id = id.split(':')[0] if type == 'series' else id
        if len(streams) > 1: unified = False
        return [WebResponse(
            title = "Stream from\n" + streams[idx]['title'],
            name = streams[idx]['name'],
            url = streams[idx]['url']+f"&index={stream_idx}:{idx}" if not unified else self.build_unified_stream_url(id, streams[idx]['contentType']),
            headers = {},
            subtitles = streams[idx]['subtitles'],
            contentType = streams[idx]['contentType'],
            behaviorHints = BehaviorHints(
                bingeGroup=imdb_id
            ),
            cacheMaxAge=0,
            staleRevalidate=0,
            staleError=0
        ) for idx in range(len(streams))]

    def extract(self, id: str, type: str, seek: int = 1, user_agent: Optional[str] = None) -> List[WebResponse] | None:
        cache: Optional[dict[str, Any]] = self.web_cache.get(id)
        current_index: int = cache.get('current_index', 0) if cache else 0
        stream_length: int = len(cache.get('streams', [])) if cache else 0
        seek_state: int = cache.get('seek_state', 0) if cache else 0

        
        def append_id_to_streams(streams: List[WebResponse]) -> List[WebResponse]:
            return [
                {
                    **streams[idx],
                    'url': streams[idx]['url'] + f"&id={id}"
                }
                for idx in range(len(streams))
            ]
        

        def process_results(tasks: List[Callable[[Any], Optional[List[WebResponse]]]], seek: int) -> List[WebResponse] | None:
            nonlocal seek_state
            self.logger.warning(f"Using states 'current_index': {current_index}, 'stream_length': {stream_length}, 'seek_state': {seek_state}")
            results_iter = self.threadpool.get_all(tasks[seek_state:seek_state+seek])
            seek_state += seek
            first_result: Optional[List[WebResponse]] = next(results_iter, None)


            if first_result:
                first_result = append_id_to_streams(first_result)
                self.logger.debug(f"First result obtained, caching and draining remaining results for ID {id}, first result: {first_result}")
                self.web_cache.set(id, first_result) if not seek_state else self.web_cache.extend(id, first_result, seek_state=seek_state)

                def drain_remaining(iterator: Iterator[Optional[List[WebResponse]]]) -> None:
                    for _, response in enumerate(iterator, start=1):
                        if response:
                            response = append_id_to_streams(response)
                            self.web_cache.extend(id, response, seek_state=seek_state)

                self.threadpool.run_in_background(lambda _, iterator=results_iter: drain_remaining(iterator))
                if not TUNNEL_URL: raise Exception("TUNNEL_URL is not set. Please set it in the config.")
                if not user_agent: return self.build_web_response(id, type, first_result, 0, unified=True)
                else: return self.build_web_response(id, type, first_result, 0, unified=True)

            elif len(tasks)>seek_state:
                return process_results(tasks=tasks, seek=1)
            self.logger.warning(f"Stream seek exceeded available tasks. Ignoring stream fetch for id '{id}'.")

        movie_scrapers: List[Tuple[Callable[[str], Optional[List[WebResponse]]], str]] = [
            # (lambda tmdb_id: [result] if (result := aether_scraper.get_movie(tmdb_id)) else None, 'aether'),
            (lambda tmdb_id: [result] if (result := viduki_scraper.get_movie(tmdb_id)) else None, 'viduki'),
            (lambda tmdb_id: [result] if (result := videasy_scraper.get_movie(tmdb_id)) else None, 'videasy'),
            (lambda tmdb_id: [result] if (result := vidnest_general_scraper.get_movie(tmdb_id)) else None, 'vidnest'),
            (lambda tmdb_id: [result] if (result := vidsrc_scraper.get_movie(tmdb_id)) else None, 'vidsrc'),
            (lambda tmdb_id: [result] if (result := fmovies_scraper.get_movie(tmdb_id)) else None, 'fmovies'),
            # (lambda tmdb_id: [result] if (result := cineby_scraper.get_movie(tmdb_id)) else None, 'cineby'),
            (lambda tmdb_id: [result] if (result := flicky_scraper.get_movie(tmdb_id)) else None, 'flicky'),
            # (lambda tmdb_id: [result] if (result := vidking_scraper.get_movie(tmdb_id)) else None, 'vidking'),
        ]

        series_scrapers: List[Tuple[Callable[[str, str, str], Optional[List[WebResponse]]], str]] = [
            # (lambda tmdb, s, e: [result] if (result := aether_scraper.get_series(tmdb, s, e)) else None, 'aether'),
            (lambda tmdb, s, e: [result] if (result := viduki_scraper.get_series(tmdb, s, e)) else None, 'viduki'),
            (lambda tmdb, s, e: [result] if (result := videasy_scraper.get_series(tmdb, s, e)) else None, 'videasy'),
            (lambda tmdb, s, e: [result] if (result := vidnest_general_scraper.get_series(tmdb, s, e)) else None, 'vidlink'),
            (lambda tmdb, s, e: [result] if (result := vidsrc_scraper.get_series(tmdb, s, e)) else None, 'vidsrc'),
            (lambda tmdb, s, e: [result] if (result := fmovies_scraper.get_series(tmdb, s, e)) else None, 'fmovies'),
            # (lambda tmdb, s, e: [result] if (result := cineby_scraper.get_series(tmdb, s, e)) else None, 'cineby'),
            (lambda tmdb, s, e: [result] if (result := flicky_scraper.get_series(tmdb, s, e)) else None, 'flicky'),
            # (lambda tmdb, s, e: [result] if (result := vidking_scraper.get_series(tmdb, s, e)) else None, 'vidking'),
        ]

        anime_series_scrapers: List[Tuple[Callable[[Optional[str], Optional[str], Optional[str], Optional[str], str, Optional[str], str, str], Optional[List[WebResponse]]], str]] = [
            (lambda ani_id, ani_eps, mal_id, mal_eps, imdb_id, tmdb_id, season, episode: [result] if (result := yomi_scraper.get_series(ani_id, ani_eps)) else None, 'yomi'),
            (lambda ani_id, ani_eps, mal_id, mal_eps, imdb_id, tmdb_id, season, episode: [result] if (result := miruro_scraper.get_series(mal_id, mal_eps)) else None, 'miruro'),
            (lambda ani_id, ani_eps, mal_id, mal_eps, imdb_id, tmdb_id, season, episode: [result] if (result := miruro_scraper.get_series(ani_id, ani_eps)) else None, 'miruro'),
            (lambda ani_id, ani_eps, mal_id, mal_eps, imdb_id, tmdb_id, season, episode: [result] if (result := vidnest_scraper.get_series(ani_id, ani_eps)) else None, 'vidnest'),
            (lambda ani_id, ani_eps, mal_id, mal_eps, imdb_id, tmdb_id, season, episode: [result] if (result := four_animo_scraper.get_series(ani_id, ani_eps)) else None, '4anime'),
        ]

        if type == 'movie':
            tmdb_id = self.tmdb_client.imdb_to_tmdb(id)
            if not tmdb_id:
                self.logger.warning(f"No TMDB ID found for IMDB ID {id}")
                return None
            
            # Regional logic
            orig_lang = self.tmdb_client.get_original_lang(id)
            release_year = self.tmdb_client.get_release_year(id)
            if orig_lang in ['ta', 'ml', 'kn', 'hi'] and release_year:
                title = self.tmdb_client.get_title(id)
                if title:
                    results = moviesda_scraper.get_movie(title, year=release_year)
                    if not results: results = tamilblasters_scraper.get_movie(title, year=release_year, threadpool=self.threadpool)
                    if results:
                        self.web_cache.set(id, results)
                        return self.build_web_response(id, type, results, 0, unified=True)
            
            tasks_movie: List[Callable[[str], Optional[List[WebResponse]]]] = [
                lambda _, f=func: f(tmdb_id or "unknown")
                for func, _ in movie_scrapers
            ]
            return process_results(tasks_movie, seek)

        else:  # Series
            imdb_id, season, episode = id.split(':')
            tmdb_id = self.tmdb_client.imdb_to_tmdb(imdb_id)
            if not tmdb_id:
                self.logger.warning(f"No TMDB ID found for IMDB ID {imdb_id}")
                return None
            
            orig_lang = self.tmdb_client.get_original_lang(imdb_id)
            if orig_lang == "ja":
                mal_id, mal_eps = anibride.get_mal_info(imdb_id, season, episode)
                ani_id, ani_eps = anibride.get_anilist_info(imdb_id, season, episode)

                tasks_anime_series: List[Callable[[Tuple[Any]], Optional[List[WebResponse]]]] = [
                    lambda _, f=func: f(ani_id, ani_eps, mal_id, mal_eps, id, tmdb_id, season, episode)
                    for func, _ in anime_series_scrapers
                ] 
                return process_results(tasks_anime_series, seek)

            else:
                tasks_series: List[Callable[[Tuple[str, str, str]], Optional[List[WebResponse]]]] = [
                    lambda _, f=func: f(tmdb_id or "unknown", season, episode)
                    for func, _ in series_scrapers
                ]
                return process_results(tasks_series, seek)


if __name__ == '__main__':
    extractor  = StreamExtractor()

    print(extractor.extract('tt22084616', 'movie'))
