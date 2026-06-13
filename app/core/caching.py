import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from pathlib import Path
from datetime import datetime, timezone
from app.config import CACHE_DIR
from app.core.logger import Logger
from typing import Any

logger = Logger('caching')

class Caching:
    def __init__(self):
        self.cache_dir = Path(CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # self.cache: dict[str, Any]
        self.cache_path: Path

    def _load_from_disk(self) -> dict[str, Any]:
        """Load cache from JSON file if it exists."""
        if not hasattr(self, 'cache_path'): raise AttributeError('Subclass must define `cache_path` attribute')
        try:
            if self.cache_path.exists():
                with open(self.cache_path, 'r', encoding='utf-8') as f: 
                    return json.load(f)
        except Exception as e: logger.error(f"Error loading cache from disk: {e}")
        return {}

    def _save_to_disk(self, path: Path, data: dict[str, Any]):
        """Save cache to JSON file."""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving cache to disk: {e}")

    def set(self, key: str, value: Any) -> None:
        # if not hasattr(self, 'cache'): raise AttributeError('Subclass must define `cache` attribute')
        # if not hasattr(self, 'cache_path'): raise AttributeError('Subclass must define `cache_path` attribute')

        timestamp = datetime.now(timezone.utc).isoformat()
        cache = self._load_from_disk()
        cache[key] = {"value": value, "ts": timestamp}
        self._save_to_disk(self.cache_path, cache)

    def get(self, key: str, upto_mins: int = 0) -> Any | None:
        # if not hasattr(self, 'cache'): raise AttributeError('Subclass must define `cache` attribute')
        cache = self._load_from_disk()
        entry = cache.get(key)
        if entry is None: return None

        now = datetime.now(timezone.utc)
        try:
            ts_dt = datetime.fromisoformat(entry['ts'])
            if ts_dt.tzinfo is None: ts_dt = ts_dt.replace(tzinfo=timezone.utc)
            if upto_mins > 0 and (now - ts_dt).total_seconds() / 60.0 > upto_mins: return None
            return entry['value']
        except Exception as e:
            logger.error(f"Error getting cache for key '{key}', error: \n{e}")
            return None

class TmdbCache(Caching):
    def __init__(self):
        super().__init__()
        self.cache_path = self.cache_dir / "tmdb.json"
        # self.cache: dict[str, Any] = self._load_from_disk()

class WebCache(Caching):
    def __init__(self):
        super().__init__()
        self.cache_path = self.cache_dir / "web_results.json"
        # self.cache: dict[str, Any] = self._load_from_disk()

class TorrentCache(Caching):
    def __init__(self):
        super().__init__()
        self.cache_path = self.cache_dir / "torrent_results.json"
        # self.cache: dict[str, Any] = self._load_from_disk()

if __name__ == "__main__":
    web_cache = WebCache()
    tmdb_cache = TmdbCache()
    web_cache.set('1234', {'1234': '1234'})
    tmdb_cache.set('4567', {'4567': '4567'})
    print(web_cache.get('1234'))
    print(tmdb_cache.get('4567'))