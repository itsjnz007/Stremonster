import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, jsonify
from flask.wrappers import Response
import os
from app.core.logger import Logger
from app.config import MANIFEST_TMDB, MANIFEST_TORRENTS, MANIFEST_WEB

logger = Logger("server")

app = Flask(__name__)

def respond_with(data: dict[str, object]) -> Response:
    resp: Response = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    return resp

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

if __name__ == "__main__":
    # Check if we're in the Flask reloader child process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        logger.info("Starting server...")
    
    app.run(host="0.0.0.0", port=8000, debug=True)