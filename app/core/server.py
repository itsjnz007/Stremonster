import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os, time
from typing import Any, List, Optional, Callable, Tuple, Iterator
from app.external.tmdb import Tmdb
from app.models.responses import BehaviorHints, WebResponse, TorrentResponse
from app.sources import torrentio as torrentio_module
from flask import Flask, request
from flask.wrappers import Response
from app.core.logger import Logger
from app.config import MANIFEST_CATALOG, MANIFEST_TORRENTS, MANIFEST_WEB, TUNNEL_URL
from app.core.caching import TmdbCache, WebCache, TorrentCache, IgnoreSourceCache, ProcessingCache
from app.core.multithreading import MultiThreading
from app.core.proxy import respond_with, Proxy
from app.external.anilist import AniBridgeV3Resolver
from app.sources.general import flicky as flicky, vidking as vidking, vidsrc as vidsrc, cineby as cineby, vidlink as vidlink, viduki as viduki
from app.sources.anime import miruro as miruro, vidnest as vidnest, four_animo as four_animo
from app.sources.regional import tamilblasters as tamilblasters
from app.core.catalog import Catalog

logger = Logger("server")
app = Flask(__name__)

thread_pool_web = MultiThreading(max_workers=3)
thread_pool_torrent = MultiThreading(max_workers=1)

tmdb_cache = TmdbCache()
web_cache = WebCache()
torrent_cache = TorrentCache()
ignore_source_cache = IgnoreSourceCache()
processing_cache = ProcessingCache()
catalog = Catalog(tmdb_cache)

catalog.build_catalog(pages=1)  # Pre-build catalog on startup
anibride = AniBridgeV3Resolver()

# General Scrapers
flicky_scraper = flicky.FlickyScraper()
vidking_scraper = vidking.VidkingScraper()
vidsrc_scraper = vidsrc.VidsrcScraper()
cineby_scraper = cineby.CinebyScraper()
vidlink_scraper = vidlink.VidlinkScraper()
viduki_scraper = viduki.VidukiScraper()

# Anime Scrapers
four_animo_scraper = four_animo.FourAnimoScraper()
miruro_scraper = miruro.MiruroScraper()
vidnest_scraper = vidnest.VidnestScraper()

# Regional Scrapers
tamilblasters_scraper = tamilblasters.TamilBlasters()

tmdb_client = Tmdb(tmdb_cache)


# Web-based links addon (fast, no torrents)
@app.route('/web/manifest.json')
def web_manifest() -> Response:
    return respond_with(MANIFEST_WEB)

# Torrent addon (slower but comprehensive)
@app.route('/torrent/manifest.json')
def torrent_manifest() -> Response:
    return respond_with(MANIFEST_TORRENTS)

# TMDB Catalogs addon
@app.route('/catalog/manifest.json')
def catalog_manifest() -> Response:
    return respond_with(MANIFEST_CATALOG)

@app.route('/catalog/catalog/<media_type>/<catalog_id>.json')
def get_catalog(media_type: str, catalog_id: str) -> Response:
    try:
        result = catalog.get_catalog(catalog_id)
        if result:
            return respond_with(result)
        else:
            logger.warning(f"No catalog found for {catalog_id}")
            return Response("Failed to fetch catalog", status=500)
    except Exception as e:
        logger.error(f"Error fetching catalog {catalog_id}: {e}")
        return Response("Failed to fetch catalog", status=500)

@app.route('/web/stream/<type>/<id>.json')
def get_web_stream(type: str, id: str) -> Response:
    logger.info(f"GET /web/stream/{type}/{id}.json")
    if type not in ('movie', 'series'): 
        return respond_with({'error': 'Invalid type'})
    
    start_time = time.time()
    user_agent = request.headers.get('User-Agent')
    logger.debug(f"User-Agent: {user_agent}")

    def build_unified_stream_url(fileIdx: int) -> str:
        if not TUNNEL_URL:
            raise Exception("TUNNEL_URL is not set. Please set it in the config.")
        return TUNNEL_URL + f"/stream?id={id}&fileIdx={fileIdx}"
    
    def build_web_response(streams: List[WebResponse], unified: bool = False) -> List[WebResponse]:
        imdb_id = id.split(':')[0] if type == 'series' else id
        return [WebResponse(
            title = "Stream from\n" + streams[idx]['title'],
            name = "Play",
            url = streams[idx]['url'] if not unified else build_unified_stream_url(idx),
            headers = {},
            subtitles = streams[idx]['subtitles'],
            origin = streams[idx]['origin'],
            behaviorHints = BehaviorHints(
                bingeGroup=imdb_id
            ),
            cacheMaxAge=0,
            staleRevalidate=0,
            staleError=0
        ) for idx in range(len(streams))]

    def append_id_to_streams(streams: List[WebResponse]) -> List[WebResponse]:
        return [
            {
                **stream,
                'url': stream['url'] + f'&id={id}'
            }
            for stream in streams
        ]
    
    def calculate() -> List[WebResponse] | None:

        def process_results(tasks: List[Callable[[Any], Optional[List[WebResponse]]]]) -> List[WebResponse] | None:
            results_iter = thread_pool_web.get_all(tasks)
            first_result: Optional[List[WebResponse]] = next(results_iter, None)
            if first_result:
                first_result = append_id_to_streams(first_result)
                logger.debug(f"First result obtained, caching and draining remaining results for ID {id}, first result: {first_result}")
                web_cache.set(id, first_result)
                def drain_remaining(iterator: Iterator[Optional[List[WebResponse]]]) -> None:
                    for response in iterator:
                        if response:
                            response = append_id_to_streams(response)
                            web_cache.extend(id, response)

                thread_pool_web.run_in_background(lambda _, iterator=results_iter: drain_remaining(iterator))
                if not TUNNEL_URL: raise Exception("TUNNEL_URL is not set. Please set it in the config.")
                if not user_agent: return build_web_response(first_result)
                else: return build_web_response(first_result, unified=True)

        movie_scrapers: List[Tuple[Callable[[str], Optional[List[WebResponse]]], str]] = [
            (lambda tmdb_id: [result] if (result := flicky_scraper.get_movie(tmdb_id)) else None, 'flicky'),
            (lambda tmdb_id: [result] if (result := cineby_scraper.get_movie(tmdb_id)) else None, 'cineby'),
            (lambda tmdb_id: [result] if (result := vidsrc_scraper.get_movie(tmdb_id)) else None, 'vidsrc'),
            (lambda tmdb_id: [result] if (result := vidlink_scraper.get_movie(tmdb_id)) else None, 'vidlink'),
            (lambda tmdb_id: [result] if (result := viduki_scraper.get_movie(tmdb_id)) else None, 'viduki'),
            (lambda tmdb_id: [result] if (result := vidking_scraper.get_movie(tmdb_id)) else None, 'vidking'),
        ]

        series_scrapers: List[Tuple[Callable[[str, str, str], Optional[List[WebResponse]]], str]] = [
            (lambda tmdb, s, e: [result] if (result := flicky_scraper.get_series(tmdb, s, e)) else None, 'flicky'),
            (lambda tmdb, s, e: [result] if (result := cineby_scraper.get_series(tmdb, s, e)) else None, 'cineby'),
            (lambda tmdb, s, e: [result] if (result := vidsrc_scraper.get_series(tmdb, s, e)) else None, 'vidsrc'),
            (lambda tmdb, s, e: [result] if (result := vidlink_scraper.get_series(tmdb, s, e)) else None, 'vidlink'),
            (lambda tmdb, s, e: [result] if (result := viduki_scraper.get_series(tmdb, s, e)) else None, 'viduki'),
            (lambda tmdb, s, e: [result] if (result := vidking_scraper.get_series(tmdb, s, e)) else None, 'vidking'),
        ]

        anime_series_scrapers: List[Tuple[Callable[[str, str, str, str], Optional[List[WebResponse]]], str]] = [
            (lambda ani_id, ani_eps, mal_id, mal_eps: [result] if (result := four_animo_scraper.get_series(ani_id, str(ani_eps))) else None, '4anime'),
            (lambda ani_id, ani_eps, mal_id, mal_eps: [result] if (result := vidnest_scraper.get_series(ani_id, str(ani_eps))) else None, 'vidnest'),
            (lambda ani_id, ani_eps, mal_id, mal_eps: [result] if (result := miruro_scraper.get_series(mal_id, str(mal_eps))) else None, 'miruro'),
            (lambda ani_id, ani_eps, mal_id, mal_eps: [result] if (result := miruro_scraper.get_series(ani_id, str(ani_eps))) else None, 'miruro'),
        ]

        if type == 'movie':
            tmdb_id = tmdb_client.imdb_to_tmdb(id)
            if not tmdb_id:
                logger.warning(f"No TMDB ID found for IMDB ID {id}")
                return None
            
            # Regional logic
            orig_lang = tmdb_client.get_original_lang(id)
            release_year = tmdb_client.get_release_year(id)
            if orig_lang in ['ta', 'ml', 'kn', 'hi'] and release_year:
                title = tmdb_client.get_title(id)
                if title:
                    results = tamilblasters_scraper.get_movie(title, year=release_year, threadpool=thread_pool_web)
                    if results:
                        web_cache.set(id, results)
                        return build_web_response(results)
            
            tasks_movie: List[Callable[[str], Optional[List[WebResponse]]]] = [
                lambda _, f=func: f(tmdb_id or "unknown")
                for func, _ in movie_scrapers
            ]
            return process_results(tasks_movie)

        else:  # Series
            imdb_id, season, episode = id.split(':')
            tmdb_id = tmdb_client.imdb_to_tmdb(imdb_id)
            if not tmdb_id:
                logger.warning(f"No TMDB ID found for IMDB ID {imdb_id}")
                return None
            
            orig_lang = tmdb_client.get_original_lang(imdb_id)
            if orig_lang == "ja":
                mal_id, mal_eps = anibride.get_mal_info(imdb_id, season, episode)
                ani_id, ani_eps = anibride.get_anilist_info(imdb_id, season, episode)

                tasks_anime_series: List[Callable[[Tuple[str, str, str, str]], Optional[List[WebResponse]]]] = [
                    lambda _, f=func: f(ani_id, str(ani_eps), mal_id, str(mal_eps))
                    for func, _ in anime_series_scrapers
                ] 
                return process_results(tasks_anime_series)

            else:
                tasks_series: List[Callable[[Tuple[str, str, str]], Optional[List[WebResponse]]]] = [
                    lambda _, f=func: f(tmdb_id or "unknown", season, episode)
                    for func, _ in series_scrapers
                ]
                return process_results(tasks_series)

    cache = web_cache.get(id, 60*3)
    if cache: 
        stream_index: Optional[int] = cache.get("current_index")
        stream_group: list[list[WebResponse]] = cache.get("streams", [])
        if not stream_group or stream_index is None or stream_index >= len(stream_group):
            logger.error(f"Cache for {id} is invalid or empty...")
            return respond_with({'streams': []})
        logger.info("Returning cached web result...")
        if not user_agent: formatted_result = {'streams': build_web_response(append_id_to_streams(stream_group[stream_index]))}
        else: formatted_result = {'streams': build_web_response(append_id_to_streams(stream_group[stream_index]), unified=True)}
        logger.info(f"Responding with: {formatted_result}")
        return respond_with(formatted_result)

    logger.info("Cache invalid, recalculating...")
    processing_cache.start(id, 'web')
    streams = calculate()
    if streams:
        processing_cache.finish(id, 'web', True)
        return respond_with({'streams': streams})
    processing_cache.finish(id, 'web', False)

    logger.info(f"Total time taken: {time.time() - start_time:.2f}s")
    return respond_with({'streams': []})



@app.route('/torrent/stream/<type>/<id>.json')
def get_torrent_stream(type: str, id: str) -> Response:
    logger.info(f"GET /torrent/stream/{type}/{id}.json")
    if type not in ('movie', 'series'): return respond_with({'error': 'Invalid type'})
    start_time = time.time()

    def calculate():
        if type == "movie":
            logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
            return torrentio_module.get_movie(id, thread_pool_torrent, True)
        else:
            logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
            return torrentio_module.get_series(id, thread_pool_torrent, True)
        
    def respond_otherwise(results: dict[str, List[TorrentResponse]]):
        # If web is still processing, wait briefly for it to finish (so we prefer web results)
        status = processing_cache.get_status(id) or {}
        web_status = status.get('web') or {}
        wait_total, wait_step, wait_limit = 0.0, 0.1, 30
        while web_status.get('processing') and wait_total < wait_limit:
            time.sleep(wait_step)
            wait_total += wait_step
            status = processing_cache.get_status(id) or {}
            web_status = status.get('web') or {}
        if web_status.get('completed') and not web_status.get('has_results'):
            return respond_with(results)
        return respond_with({'streams': []})
        
    cache = torrent_cache.get(key=id, upto_mins=60*3)
    if cache:
        logger.info("Returning cached torrent result...")
        return respond_otherwise(cache)
    else:
        processing_cache.start(id, 'torrent')
        result = calculate()
        processing_cache.finish(id, 'torrent', bool(result))
        if result:
            formatted_result = {'streams': result}
            torrent_cache.set(id, formatted_result)
            return respond_otherwise(formatted_result)

            
    
    logger.info(f"Total time taken to fetch torrent stream: {time.time() - start_time:.2f} seconds")
    logger.warning(f"No torrent stream found for {type} with ID {id}")
    return respond_with({'streams': []})
        
@app.route('/stream')
def stream() -> Response:
    logger.info(f"GET /stream")
    return Proxy.stream()

@app.route("/stream.m3u8")
def proxy_m3u8():
    """Proxy endpoint for M3U8 playlists - ends with .m3u8 for Android compatibility"""
    return Proxy.proxy()

@app.route("/stream.ts")
def proxy_stream_ts():
    """Proxy endpoint for TS segments - ends with .ts for Android compatibility"""
    return Proxy.proxy()

@app.route("/stream.mp4")
def proxy_stream_mp4():
    return Proxy.proxy()

@app.route("/proxy")
def proxy() -> Response | tuple[dict[str, str], int]:
    return Proxy.proxy()


if __name__ == "__main__":
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        logger.info("Starting server...")
    
    app.run(host="0.0.0.0", port=8000, debug=True)
