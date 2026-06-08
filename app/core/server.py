import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional
from app.external.tmdb import Tmdb
from app.models.responses import StreamResponse
from app.sources import flicky as flicky_module, vidking as vidking_module
from flask import Flask
from flask.wrappers import Response
import os, time
from app.core.logger import Logger
from app.config import MANIFEST_TMDB, MANIFEST_TORRENTS, MANIFEST_WEB
from app.core.caching import Caching
from app.core.multithreading import MultiThreading
from app.core.proxy import respond_with, Proxy

logger = Logger("server")
cache = Caching()
app = Flask(__name__)
thread_pool = MultiThreading(logger, max_workers=4)

flicky_scraper = flicky_module.FlickyScraper()
vidking_scraper = vidking_module.VidkingScraper()
tmdb_client = Tmdb(cache)

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

    # tmp = StreamResponse(
    #     title="Under manitenance!",
    #     url="https://www.google/com",
    #     subtitles=[]
    # )
    # return respond_with({"streams": [tmp]})

    if type == 'movie':
        tmdb_id = tmdb_client.imdb_to_tmdb(id)
        if not tmdb_id: 
            logger.warning(f"No TMDB ID found for IMDB ID {id}")
            return respond_with({'streams': []})
        
        result: Optional[StreamResponse] = thread_pool.get_first([
            lambda: vidking_scraper.get_movie(tmdb_id),
            lambda: flicky_scraper.get_movie(tmdb_id)
        ])

        logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
        # if result: return respond_with({'streams': [result]})
        
    else:
        imdb_id, season, episode = id.split(':')
        tmdb_id = tmdb_client.imdb_to_tmdb(imdb_id)
        if not tmdb_id:
            logger.warning(f"No TMDB ID found for IMDB ID {imdb_id}")
            return respond_with({'streams': []})

        result: Optional[StreamResponse] = thread_pool.get_first([
            lambda: vidking_scraper.get_series(tmdb_id, season, episode),
            lambda: flicky_scraper.get_series(tmdb_id, season, episode)
        ])

        logger.info(f"Total time taken to fetch web stream: {time.time() - start_time:.2f} seconds")
        # if result: return respond_with({'streams': [result]})

    if result: return respond_with({'streams': [result]})
    
    logger.warning(f"No stream found for {type} with ID {id}")
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