import json
from pathlib import Path
from app.config import CACHE_DIR

class Caching:
    def __init__(self):
        self.cache: dict[str | int, dict[str, dict[str, object]]] = {'tmdb': {}}
        self.cache_dir = Path(CACHE_DIR)
        self.cache_file = self.cache_dir / "cache.json"
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load persisted cache from disk if it exists
        self._load_from_disk()

    def _load_from_disk(self):
        """Load cache from JSON file if it exists."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
        except Exception as e:
            print(f"Error loading cache from disk: {e}")

    def _save_to_disk(self):
        """Save cache to JSON file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving cache to disk: {e}")

    def set_tmdb(self, imdb_id: str, result: dict[str, object]):
        if 'tmdb' not in self.cache:
            self.cache['tmdb'] = {}
        self.cache['tmdb'][imdb_id] = result
        self._save_to_disk()

    def get_tmdb(self, imdb_id: str):
        return self.cache.get('tmdb', {}).get(imdb_id)
    
    def clear(self):
        self.cache.clear()
        self.cache['tmdb'] = {}
        self._save_to_disk()