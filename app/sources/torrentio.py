import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
import time
from typing import List

from app.core.torrent import Torrent
from app.models.responses import TorrentResponse
from app.core.multithreading import MultiThreading
from app.core.logger import Logger

logger = Logger("torrentio")

BASE_URL = "https://torrentio.strem.fun/qualityfilter=scr,cam,brremux,hdrall,dolbyvision,dolbyvisionwithhdr,threed,480p,other,unknown%7Climit=2"


def bucket_streams(torrentio_json: TorrentResponse) -> List[TorrentResponse]:
    """Filters and categorizes incoming API streams into clean 4K, 1080p, and 720p buckets."""
    buckets: dict[str, list[TorrentResponse]] = {"4k": [], "1080p": [], "720p": []}

    for stream in torrentio_json.get("streams", []):
        name = stream.get("name", "")
        title = stream.get("title", "")
        filename = stream.get("behaviorHints", {}).get("filename", "")
        
        combined = f"{name} {title} {filename}".lower()

        if "2160p" in combined or "4k" in combined:
            bucket = "4k"
        elif "1080p" in combined:
            bucket = "1080p"
        elif "720p" in combined:
            bucket = "720p"
        else:
            continue  # Drop unrecognized formats or low qualities

        stream['title'] = "Torrent"
        stream['name'] = bucket
        buckets[bucket].append(stream)

    return buckets["4k"] + buckets["1080p"] + buckets["720p"]


def get_streams(media_type: str, imdb_id: str, threadpool: MultiThreading, test_speeds: bool = False) -> List[TorrentResponse]:
    """Core retrieval script pulling raw Torrentio indexes and calling our validation engine."""
    url = f"{BASE_URL}/stream/{media_type}/{imdb_id}.json"
    logger.info(f"GET Torrent for URL {url}")
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=12)
        if response.status_code != 200:
            return []

        streams = bucket_streams(response.json())
        
        if test_speeds and streams:
            print(f"\n=== Testing {len(streams)} Streams using Interleaved Round-Robin Waves ===")
            torrent_tester = Torrent(threadpool)
            # This calls your parallel wave engine!
            streams = torrent_tester.get_best_torrents(streams)
            
        return streams
    except Exception as e:
        print(f"Exception encountered within Torrentio module: {e}")
        return []


def get_movie(imdb_id: str, threadpool: MultiThreading, test_speeds: bool = False) -> List[TorrentResponse]:
    """Fetch movie metadata streams."""
    return get_streams("movie", imdb_id, threadpool, test_speeds)


def get_series(imdb_id: str, threadpool: MultiThreading, test_speeds: bool = False) -> List[TorrentResponse]:
    """Fetch series metadata streams."""
    return get_streams("series", imdb_id, threadpool, test_speeds)


if __name__ == "__main__":
    print("Testing Live Torrentio Speed Verification System...")
    start_time = time.time()
    from app.core.logger import Logger
    logger = Logger('torrentio')
    threadpool = MultiThreading(2)
    # Interstellar IMDB id used for profiling speed categorization workflows
    results = get_movie("tt1130884", threadpool, test_speeds=True)
    
    response_time = time.time() - start_time
    print(f"\n🏁 Finished evaluation loops in: {response_time:.2f} seconds")
    print(f"Selected {len(results)} optimal streams:")
    
    for stream in results:
        print(f"  - [{stream.get('name').upper()}]: {stream.get('title')} (Hash: {stream.get('infoHash')[:10]}...)")