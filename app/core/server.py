import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional
from app.external.tmdb import Tmdb
from app.models.responses import WebResponse
from app.sources import torrentio as torrentio_module
from flask import Flask
from flask.wrappers import Response
import os, time
from app.core.logger import Logger
from app.config import MANIFEST_TMDB, MANIFEST_TORRENTS, MANIFEST_WEB
from app.core.caching import TmdbCache, WebCache, TorrentCache
from app.core.multithreading import MultiThreading
from app.core.proxy import respond_with, Proxy
from app.external.anilist import AniBridgeV3Resolver
from app.sources.general import flicky as flicky, vidking as vidking, vidsrc as vidsrc
from app.sources.anime import miruro as miruro, vidnest as vidnest, four_animo as four_animo

logger = Logger("server")
app = Flask(__name__)

thread_pool = MultiThreading(max_workers=3)

tmdb_cache = TmdbCache()
web_cache = WebCache()
torrent_cache = TorrentCache()
anibride = AniBridgeV3Resolver()

# General Scrapers
flicky_scraper = flicky.FlickyScraper()
vidking_scraper = vidking.VidkingScraper()
vidsrc_scraper = vidsrc.VidsrcScraper()

# Anime Scrapers
four_animo_scraper = four_animo.FourAnimoScraper()
miruro_scraper = miruro.MiruroScraper()
# vidnest_scraper = vidnest.VidnestScraper()

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
    return respond_with(MANIFEST_TMDB)

# Landing page
@app.route('/')
def index() -> Response:
    return respond_with({
        "message": "Welcome! Available endpoints: /web/manifest.json, /torrent/manifest.json, /catalog/manifest.json"
    })

@app.route('/web/stream/<type>/<id>.json')
def get_web_stream(type: str, id: str) -> Response:
    if type not in ('movie', 'series'): return respond_with({'error': 'Invalid type'})
    
    start_time = time.time()

    def calculate() -> Optional[WebResponse]:
        if type == 'movie':
            tmdb_id = tmdb_client.imdb_to_tmdb(id)
            if not tmdb_id: 
                logger.warning(f"No TMDB ID found for IMDB ID {id}")
                return
            
            result: Optional[WebResponse] = thread_pool.get_first([
                lambda event: vidking_scraper.get_movie(tmdb_id, event),
                lambda event: flicky_scraper.get_movie(tmdb_id, event),
                lambda event: vidsrc_scraper.get_movie(tmdb_id, event),
            ])
        else:
            imdb_id, season, episode = id.split(':')
            tmdb_id = tmdb_client.imdb_to_tmdb(imdb_id)
            orig_lang = tmdb_client.get_original_lang(imdb_id)
            if not tmdb_id:
                logger.warning(f"No TMDB ID found for IMDB ID {imdb_id}")
                return
            if orig_lang == "ja":
                mal_id, mal_eps = anibride.get_mal_info(imdb_id, season, episode)
                ani_id, ani_eps = anibride.get_anilist_info(imdb_id, season, episode)
                result: Optional[WebResponse] = thread_pool.get_first([
                    # lambda event: miruro_scraper.get_series(mal_id, str(mal_eps), event),
                    # lambda event: miruro_scraper.get_series(ani_id, str(ani_eps), event),
                    lambda event: four_animo_scraper.get_series(ani_id, str(ani_eps), event)
                ])
                if not result:
                    result: Optional[WebResponse] = thread_pool.get_first([
                        # lambda event: vidnest_scraper.get_series(ani_id, str(ani_eps), event),
                        lambda event: miruro_scraper.get_series(mal_id, str(mal_eps), event),
                        lambda event: miruro_scraper.get_series(ani_id, str(ani_eps), event),
                    ])

                # if not result:
                #     result: Optional[WebResponse] = web_thread_pool.get_first([
                #         lambda event: vidking_scraper.get_series(tmdb_id, season, episode, event),
                #         lambda event: flicky_scraper.get_series(tmdb_id, season, episode, event),
                #         lambda event: vidsrc_scraper.get_series(tmdb_id, season, episode, event),
                #     ])
            else:
                if not tmdb_id:
                    logger.warning(f"No TMDB ID found for IMDB ID {imdb_id}")
                    return

                result: Optional[WebResponse] = thread_pool.get_first([
                    lambda event: vidking_scraper.get_series(tmdb_id, season, episode, event),
                    lambda event: flicky_scraper.get_series(tmdb_id, season, episode, event),
                    lambda event: vidsrc_scraper.get_series(tmdb_id, season, episode, event),
                ])
        return result

    cache = web_cache.get(key=id, upto_mins=60)
    if cache: 
        logger.info("Returning cached web results...")
        return respond_with(cache)
    else:
        result = calculate()
        if result:
            formatted_result = {'streams': [result]}
            web_cache.set(id, formatted_result)
            return respond_with(formatted_result)

    logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
    logger.warning(f"No web stream found for {type} with ID {id}")
    return respond_with({'streams': []})

@app.route('/torrent/stream/<type>/<id>.json')
def get_torrent_stream(type: str, id: str) -> Response:
    if type not in ('movie', 'series'): return respond_with({'error': 'Invalid type'})
    start_time = time.time()

    def calculate():
        if type == "movie":
            logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
            return torrentio_module.get_movie(id, thread_pool, True)
        else:
            logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
            return torrentio_module.get_series(id, thread_pool, True)
        
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