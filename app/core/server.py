import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import List, Optional, Callable, Tuple
from app.external.tmdb import Tmdb
from app.models.responses import WebResponse, ExternalWebResponse
from app.sources import torrentio as torrentio_module
from flask import Flask
from flask.wrappers import Response
import os, time
from app.core.logger import Logger
from app.config import MANIFEST_CATALOG, MANIFEST_TORRENTS, MANIFEST_WEB, TUNNEL_URL
from app.core.caching import TmdbCache, WebCache, TorrentCache, IgnoreSourceCache
from app.core.multithreading import MultiThreading
from app.core.proxy import respond_with, Proxy
from app.external.anilist import AniBridgeV3Resolver
from app.sources.general import flicky as flicky, vidking as vidking, vidsrc as vidsrc, cineby as cineby
from app.sources.anime import miruro as miruro, vidnest as vidnest, four_animo as four_animo
from app.sources.regional import tamilblasters as tamilblasters
from app.core.catalog import Catalog
from threading import Event

logger = Logger("server")
app = Flask(__name__)

thread_pool_web = MultiThreading(max_workers=3)
thread_pool_torrent = MultiThreading(max_workers=3)

tmdb_cache = TmdbCache()
web_cache = WebCache()
torrent_cache = TorrentCache()
ignore_source_cache = IgnoreSourceCache()
catalog = Catalog(tmdb_cache)

catalog.build_catalog(pages=1)  # Pre-build catalog on startup

anibride = AniBridgeV3Resolver()

# General Scrapers
flicky_scraper = flicky.FlickyScraper()
vidking_scraper = vidking.VidkingScraper()
vidsrc_scraper = vidsrc.VidsrcScraper()
cineby_scraper = cineby.CinebyScraper()

# Anime Scrapers
four_animo_scraper = four_animo.FourAnimoScraper()
miruro_scraper = miruro.MiruroScraper()

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

# Landing page
@app.route('/')
def index() -> Response:
    return respond_with({
        "message": "Welcome! Available endpoints: /web/manifest.json, /torrent/manifest.json, /catalog/manifest.json"
    })

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

@app.route('/web/ignore/<id>/<source>.json')
def ignore_source(id: str, source: str):
    source_list: List[str] = ignore_source_cache.get(id, 60*24) or []
    source_list.append(source)
    ignore_source_cache.set(id, list(set(source_list)))
    web_cache.remove(id)
    return respond_with({"message": "Current source added to ignore list. Please refresh the streaming page. "})


@app.route('/web/stream/<type>/<id>.json')
def get_web_stream(type: str, id: str) -> Response:
    logger.info(f"GET /web/stream/{type}/{id}.json")
    if type not in ('movie', 'series'): 
        return respond_with({'error': 'Invalid type'})
    
    start_time = time.time()

    def calculate(ignore_list: List[int]) -> List[WebResponse] | List[ExternalWebResponse]:
        def include_ignore_query(source: str) -> ExternalWebResponse:
            return ExternalWebResponse(
                title="Try different web source?",
                name="⭕️",
                externalUrl=f"{TUNNEL_URL}/web/ignore/{id}/{source}.json",
                subtitles=[]
            )
        
        # Registries for Scrapers
        movie_scrapers: List[Tuple[Callable[[Event, str], Optional[WebResponse]], str]] = [
            (lambda event, tmdb_id: flicky_scraper.get_movie(tmdb_id, event), 'flicky'),
            (lambda event, tmdb_id: vidking_scraper.get_movie(tmdb_id, event), 'vidking'),
            (lambda event, tmdb_id: vidsrc_scraper.get_movie(tmdb_id, event), 'vidsrc'),
            (lambda event, tmdb_id: cineby_scraper.get_movie(tmdb_id, event), 'cineby'),
        ]

        series_scrapers: List[Tuple[Callable[[Event, str, str, str], Optional[WebResponse]], str]] = [
            (lambda event, tmdb, s, e: flicky_scraper.get_series(tmdb, s, e, event), 'flicky'),
            (lambda event, tmdb, s, e: vidking_scraper.get_series(tmdb, s, e, event), 'vidking'),
            (lambda event, tmdb, s, e: vidsrc_scraper.get_series(tmdb, s, e, event), 'vidsrc'),
            (lambda event, tmdb, s, e: cineby_scraper.get_series(tmdb, s, e, event), 'cineby'),
        ]

        returnable_results: List[WebResponse] | List[ExternalWebResponse] = []
        ignore_set = set(ignore_list)

        if type == 'movie':
            tmdb_id = tmdb_client.imdb_to_tmdb(id)
            if not tmdb_id:
                logger.warning(f"No TMDB ID found for IMDB ID {id}")
                return []
            
            # Regional logic
            orig_lang = tmdb_client.get_original_lang(id)
            release_year = tmdb_client.get_release_year(id)
            if orig_lang in ['ta', 'ml', 'kn', 'hi'] and release_year:
                title = tmdb_client.get_title(id)
                if title:
                    returnable_results = tamilblasters_scraper.get_movie(title, year=release_year, threadpool=thread_pool_web)
            
            # Fallback
            if not returnable_results:
                tasks: List[Tuple[Callable[[Event, str], str], str]] = [ # type: ignore
                    (lambda event, f=func: f(Event, tmdb_id), name) # type: ignore
                    for func, name in movie_scrapers
                    if name not in ignore_set # type: ignore
                ]
                response = thread_pool_web.get_first(tasks) # type: ignore
                if response:
                    result, index = response
                    if result:
                        returnable_results = [result, include_ignore_query(index)]


        else:  # Series
            imdb_id, season, episode = id.split(':')
            tmdb_id = tmdb_client.imdb_to_tmdb(imdb_id)
            if not tmdb_id:
                logger.warning(f"No TMDB ID found for IMDB ID {imdb_id}")
                return []
            
            orig_lang = tmdb_client.get_original_lang(imdb_id)
            if orig_lang == "ja":
                mal_id, mal_eps = anibride.get_mal_info(imdb_id, season, episode)
                ani_id, ani_eps = anibride.get_anilist_info(imdb_id, season, episode)
                
                response = thread_pool_web.get_first([(lambda event: four_animo_scraper.get_series(ani_id, str(ani_eps), event), 'task1')])
                if response: 
                    result, _ = response
                    returnable_results = [result]

                if not returnable_results:
                    response = thread_pool_web.get_first([
                        (lambda event: miruro_scraper.get_series(mal_id, str(mal_eps), event), 'task1'),
                        (lambda event: miruro_scraper.get_series(ani_id, str(ani_eps), event), 'task2'),
                    ])
                    if response: 
                        result, _ = response
                        returnable_results = [result]
            else:
                tasks: List[Tuple[Callable[[Event, str, str, str], str], str]] = [
                    (lambda event, f=func: f(event, tmdb_id, season, episode), name) # type: ignore
                    for func, name in series_scrapers
                    if name not in ignore_set # type: ignore
                ]
                response = thread_pool_web.get_first(tasks) # type: ignore
                if response: 
                    result, index = response
                    returnable_results = [result, include_ignore_query(index)]

        return returnable_results

    # Execution flow
    cache = web_cache.get(key=id, upto_mins=60)
    if cache: 
        logger.info("Returning cached web results...")
        return respond_with(cache)
    
    try:
        # Ensure ignore_list is list of int
        ignore_list: List[int] = ignore_source_cache.get(id) or []
        
        calculated = calculate(ignore_list)
        results = [i for i in calculated if i]
        
        if results:
            formatted_result = {'streams': results}
            web_cache.set(id, formatted_result)
            return respond_with(formatted_result)
    except Exception as e:
        logger.error(f"Error calculating web streams. Error: {e}")
        return respond_with({"streams": []})

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
        
    cache = torrent_cache.get(key=id, upto_mins=60*24)
    if cache:
        logger.info("Returning cached torrent result...")
        return respond_with(cache)
    else:
        # wait_until(4)
        result = calculate()
        if result:
            formatted_result = {'streams': result}
            torrent_cache.set(id, formatted_result)
            return respond_with(formatted_result)
    
    logger.info(f"Total time taken to fetch torrent stream: {time.time() - start_time:.2f} seconds")
    logger.warning(f"No torrent stream found for {type} with ID {id}")
    return respond_with({'streams': []})
        

@app.route("/stream.m3u8")
def proxy_m3u8():
    """Proxy endpoint for M3U8 playlists - ends with .m3u8 for Android compatibility"""
    return Proxy.proxy_m3u8()

@app.route("/stream.ts")
def proxy_stream_ts():
    """Proxy endpoint for TS segments - ends with .ts for Android compatibility"""
    return Proxy.proxy_stream_ts()

@app.route("/proxy")
def proxy() -> Response | tuple[dict[str, str], int]:
    return Proxy.proxy()


if __name__ == "__main__":
    # Check if we're in the Flask reloader child process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        logger.info("Starting server...")
    
    app.run(host="0.0.0.0", port=8000, debug=True)