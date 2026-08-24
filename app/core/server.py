import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os, time
from typing import Optional
from app.models.responses import WebResponse
from app.sources import torrentio as torrentio_module
from flask import Flask, request
from flask.wrappers import Response
from app.core.logger import Logger
from app.config import MANIFEST_CATALOG, MANIFEST_TORRENTS, MANIFEST_WEB, USE_CACHE_UPTO
from app.core.caching import TmdbCache, WebCache, TorrentCache, ProcessingCache
from app.core.multithreading import MultiThreading
from app.core.proxy import respond_with, Proxy
from app.core.extractors import StreamExtractor
from app.core.catalog import Catalog

logger = Logger("server")
app = Flask(__name__)

thread_pool_torrent = MultiThreading(max_workers=1)

tmdb_cache = TmdbCache()
web_cache = WebCache()
torrent_cache = TorrentCache()
processing_cache = ProcessingCache()
catalog = Catalog(tmdb_cache)
stream_extractor = StreamExtractor()


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

    while processing_cache.get_status(id, 'web') and start_time+120>time.time(): time.sleep(1)

    cache = web_cache.get(id, USE_CACHE_UPTO)
    if cache: 
        stream_index: Optional[int] = cache.get("current_index")
        stream_group: list[list[WebResponse]] = cache.get("streams", [])
        if not stream_group or stream_index is None or stream_index >= len(stream_group):
            logger.error(f"Cache for {id} is invalid or empty...")
            return respond_with({'streams': []})
        logger.info("Returning cached web result...")
        if not user_agent: formatted_result = {'streams': stream_extractor.build_web_response(id, type, stream_group[stream_index], stream_index, unified=True)}
        else: formatted_result = {'streams': stream_extractor.build_web_response(id, type, stream_group[stream_index], stream_index, unified=True)}
        logger.info(f"Responding with: {formatted_result}")
        return respond_with(formatted_result)

    logger.info("Cache invalid, recalculating...")
    processing_cache.start(id, 'web')
    streams = stream_extractor.extract(id, type, seek=3, user_agent=user_agent)
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
    user_agent = request.headers.get('User-Agent', '')
    has_browser_token = any(token in user_agent.lower() for token in [
        'chrome', 'firefox', 'safari', 'edg', 'opera', 'msie', 'trident'
    ])

    if has_browser_token: 
        logger.warning("Torrent requested from browser. Ignoring request.")
        return Response("Torrent requested from browser. Ignoring request.", 503)

    def calculate():
        if type == "movie":
            logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
            return torrentio_module.get_movie(id, thread_pool_torrent, True)
        else:
            logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
            return torrentio_module.get_series(id, thread_pool_torrent, True)

    time.sleep(3)
    while (processing_cache.get_status(id, 'torrent') or (processing_cache.get_status(id, 'web'))) and start_time+120>time.time(): time.sleep(1)
        
    cache = torrent_cache.get(key=id, upto_mins=USE_CACHE_UPTO)
    if cache:
        logger.info("Returning cached torrent result...")
        return respond_with(cache)
        # return respond_otherwise(cache)
    else:
        processing_cache.start(id, 'torrent')
        result = calculate()
        processing_cache.finish(id, 'torrent', bool(result))
        if result:
            formatted_result = {'streams': result}
            torrent_cache.set(id, formatted_result)
            return respond_with(formatted_result)
            # return respond_otherwise(formatted_result)

    logger.info(f"Total time taken to fetch torrent stream: {time.time() - start_time:.2f} seconds")
    logger.warning(f"No torrent stream found for {type} with ID {id}")
    return respond_with({'streams': []})

        
@app.route('/redirect')
def redirect() -> Response:
    return Proxy.redirect()

@app.route('/redirect.m3u8')
def redirect_m3u8() -> Response:
    return Proxy.redirect()

@app.route('/redirect.mp4')
def redirect_mp4() -> Response:
    return Proxy.redirect()

@app.route("/stream.m3u8")
def proxy_m3u8():
    """Proxy endpoint for M3U8 playlists - ends with .m3u8 for Android compatibility"""
    return Proxy.proxy("application/vnd.apple.mpegurl")

@app.route("/stream.ts")
def proxy_stream_ts():
    """Proxy endpoint for TS segments - ends with .ts for Android compatibility"""
    return Proxy.proxy("video/mp2t")

@app.route("/stream.mp4")
def proxy_stream_mp4():
    return Proxy.proxy("video/mp4")

@app.route("/stream.m4s")
def proxy_stream_m4s():
    return Proxy.proxy("video/mp4")

@app.route("/proxy.vtt")
def proxy_vvt():
    return Proxy.proxy("text/vtt")

@app.route("/proxy.srt")
def proxy_srt():
    return Proxy.proxy("text/plain")

@app.route("/proxy")
def proxy() -> Response | tuple[dict[str, str], int]:
    return Proxy.proxy()


if __name__ == "__main__":
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        logger.info("Starting server...")
    
    app.run(host="0.0.0.0", port=8000, debug=True)
