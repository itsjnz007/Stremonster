import sys
import os
import json
import threading, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


from datetime import datetime, timezone
from typing import Any, ClassVar
from app.models.responses import WebResponse
from app.config import CACHE_DIR
from app.core.logger import Logger
# from urllib.parse import parse_qs, urlparse
import logging


logger = Logger('caching', logging.INFO)

class Caching:
    _write_lock: ClassVar[threading.Lock] = threading.Lock()
    cache: ClassVar[dict[str, Any]]
    cache_path: ClassVar[Path]

    def __init__(self):
        self.cache_dir = Path(CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_cache()

    def _initialize_cache(self) -> None:
        if not hasattr(self.__class__, 'cache'):
            raise AttributeError('Subclass must define `cache` attribute')

        cache = getattr(self.__class__, 'cache', None)
        if cache is None:
            self.__class__.cache = {}
            return

        if not cache:
            self.__class__.cache = self._load_from_disk()

    def _get_cache(self) -> dict[str, Any]:
        if not hasattr(self.__class__, 'cache'):
            raise AttributeError('Subclass must define `cache` attribute')
        return self.__class__.cache

    def _get_cache_path(self) -> Path:
        if not hasattr(self.__class__, 'cache_path'):
            raise AttributeError('Subclass must define `cache_path` attribute')
        return self.__class__.cache_path

    def _load_from_disk(self) -> dict[str, Any]:
        """Load cache from JSON file if it exists."""
        path = self._get_cache_path()
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
        except Exception as e:
            logger.error(f"Error loading cache from disk: {e}")
        return {}

    def _save_to_disk(self, path: Path, data: dict[str, Any]):
        """Save cache to JSON file."""
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, path)
        except Exception as e:
            print(f"Error saving cache to disk: {e}")

    def set(self, key: str, value: Any) -> None:
        cache = self._get_cache()
        timestamp = datetime.now(timezone.utc).isoformat()
        cache[key] = {"value": copy.deepcopy(value), "ts": timestamp}
        self._save_to_disk(self._get_cache_path(), cache)

    def get(self, key: str, upto_mins: int = 0) -> Any | None:
        entry = self._get_cache().get(key)
        if entry is None:
            return None

        now = datetime.now(timezone.utc)
        try:
            ts_dt = datetime.fromisoformat(entry['ts'])
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
            if upto_mins > 0 and (now - ts_dt).total_seconds() / 60.0 > upto_mins:
                return None
            return entry['value']
        except Exception as e:
            logger.error(f"Error getting cache for key '{key}', error: \n{e}")
            return None

    def remove(self, key: str) -> None:
        """Removes an item from the cache and updates the disk file."""
        cache = self._get_cache()
        if key in cache:
            del cache[key]
            self._save_to_disk(self._get_cache_path(), cache)
            logger.info(f"Key '{key}' removed from cache.")
        else:
            logger.warning(f"Attempted to remove non-existent key: '{key}'")

class TmdbCache(Caching):
    cache_path: ClassVar[Path] = Path(CACHE_DIR) / "tmdb.json"
    cache: ClassVar[dict[str, Any]] = {}

class WebCache(Caching):
    cache_path: ClassVar[Path] = Path(CACHE_DIR) / "web_results.json"
    cache: ClassVar[dict[str, Any]] = {}

    def set(self, key: str, value: list[WebResponse]) -> None:
        """Set a WebResponse for a given key."""
        with self._write_lock:
            cache = self._get_cache()
            timestamp = datetime.now(timezone.utc).isoformat()
            cache[key] = {"value": {"current_index": 0, "requires_reload": False, "streams": copy.deepcopy([value])}, "ts": timestamp}
            self._save_to_disk(self._get_cache_path(), cache)

    def extend(self, key: str, web_responses: list[WebResponse]) -> None:
        """Append a WebResponse to the list of streams for a given key."""
        with self._write_lock:
            cache = self._get_cache()
            timestamp = datetime.now(timezone.utc).isoformat()
            if key not in cache:
                cache[key] = {"value": {"current_index": 0, "requires_reload": False, "streams": []}, "ts": timestamp}

            cache[key]["value"]["streams"].extend(copy.deepcopy([web_responses]))
            cache[key]["ts"] = timestamp  # Update timestamp on append
            self._save_to_disk(self._get_cache_path(), cache)
    
    def switch_source(self, key: str) -> None:
        """Switch to the next source in the list for a given key."""
        with self._write_lock:
            cache = self._get_cache()
            if key not in cache or not cache[key]["value"]["streams"]:
                logger.warning(f"No streams available to switch for key: '{key}'")
                return

            current_index = cache[key]["value"]["current_index"]
            total_streams = len(cache[key]["value"]["streams"])
            new_index = (current_index + 1) % total_streams
            cache[key]["value"]["current_index"] = new_index
            # cache[key]["value"]["requires_reload"] = True
            cache[key]["ts"] = datetime.now(timezone.utc).isoformat()  # Update timestamp on switch
            self._save_to_disk(self._get_cache_path(), cache)
            logger.info(f"Switching source for key: '{key}' to index: '{new_index}'")
    
    # def reloaded(self, key: str, index: str) -> None:
    #     with self._write_lock:
    #         cache = self._get_cache()
    #         if key not in cache or not cache[key]["value"]["streams"]:
    #             logger.warning(f"No streams available to switch for key: '{key}'")
    #             return
            
    #         current_index = cache[key]["value"]["current_index"]
    #         source_index, file_index = index.split(':')
    #         logger.debug(f'current_index: {current_index} | source_index: {source_index} | file_index: {file_index}')
    #         url: str = cache[key]['value']['streams'][current_index][int(file_index)]['url']
    #         parsed_url = urlparse(url)
    #         query_params = parse_qs(parsed_url.query)
    #         if query_params.get('index', [None])[0] == index:
    #             logger.warning(f"Skipping 'requires_reload' flag, url same as current index. Current index {current_index}.")
    #             return
            
    #         cache[key]["value"]["requires_reload"] = False
    #         cache[key]["ts"] = datetime.now(timezone.utc).isoformat()  # Update timestamp on switch
    #         self._save_to_disk(self._get_cache_path(), cache)


class TorrentCache(Caching):
    cache_path: ClassVar[Path] = Path(CACHE_DIR) / "torrent_results.json"
    cache: ClassVar[dict[str, Any]] = {}

class TvdbCache(Caching):
    cache_path: ClassVar[Path] = Path(CACHE_DIR) / "tvdb.json"
    cache: ClassVar[dict[str, Any]] = {}

class CatalogCache(Caching):
    cache_path: ClassVar[Path] = Path(CACHE_DIR) / "catalog.json"
    cache: ClassVar[dict[str, Any]] = {}

class IgnoreSourceCache(Caching):
    cache_path: ClassVar[Path] = Path(CACHE_DIR) / "ignore_source.json"
    cache: ClassVar[dict[str, Any]] = {}


class ProcessingCache(Caching):
    """Track processing status for web/torrent requests per ID.

    Stored format per key:
    {
        "web": {"processing": bool, "completed": bool, "has_results": bool},
        "torrent": {"processing": bool, "completed": bool, "has_results": bool},
        "ts": "..."
    }
    """
    cache_path: ClassVar[Path] = Path(CACHE_DIR) / "processing.json"
    cache: ClassVar[dict[str, Any]] = {}

    def start(self, key: str, kind: str) -> None:
        kind = kind.lower()
        if kind not in ("web", "torrent"):
            raise ValueError("kind must be 'web' or 'torrent'")
        with self._write_lock:
            cache = self._get_cache()
            timestamp = datetime.now(timezone.utc).isoformat()
            entry = cache.get(key, {})
            entry.setdefault("web", {"processing": False, "completed": False, "has_results": False})
            entry.setdefault("torrent", {"processing": False, "completed": False, "has_results": False})
            entry[kind]["processing"] = True
            entry[kind]["completed"] = False
            entry[kind]["has_results"] = False
            entry["ts"] = timestamp
            cache[key] = entry
            # self._save_to_disk(self._get_cache_path(), cache)

    def finish(self, key: str, kind: str, has_results: bool) -> None:
        kind = kind.lower()
        if kind not in ("web", "torrent"):
            raise ValueError("kind must be 'web' or 'torrent'")
        with self._write_lock:
            cache = self._get_cache()
            timestamp = datetime.now(timezone.utc).isoformat()
            entry = cache.get(key, {})
            entry.setdefault("web", {"processing": False, "completed": False, "has_results": False})
            entry.setdefault("torrent", {"processing": False, "completed": False, "has_results": False})
            entry[kind]["processing"] = False
            entry[kind]["completed"] = True
            entry[kind]["has_results"] = bool(has_results)
            entry["ts"] = timestamp
            cache[key] = entry
            # self._save_to_disk(self._get_cache_path(), cache)

    def get_status(self, key: str) -> dict[str, dict[str, bool]] | None:
        entry = self._get_cache().get(key)
        if not entry:
            return None
        return copy.deepcopy(entry)

if __name__ == "__main__":
    web_cache = WebCache()
    tmdb_cache = TmdbCache()
    # web_cache.set('1234', {'1234': '1234'})
    tmdb_cache.set('4567', {'4567': '4567'})
    print(web_cache.get('1234'))
    print(tmdb_cache.get('4567'))