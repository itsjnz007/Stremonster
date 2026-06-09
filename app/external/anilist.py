import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from typing import Dict
from app.core.logger import Logger

logger = Logger('anilist')

# Official v3 Direct Production Release Distribution URL
RAW_MAPPINGS_URL = "https://github.com/anibridge/anibridge-mappings/releases/download/v3/mappings.json"

class AniBridgeV3Resolver:
    """
    In-memory resolver designed to ingest and parse AniBridge v3 specifications
    defined by the 'provider:id[:scope]' descriptor layout.
    """
    def __init__(self):
        self.mappings_db: Dict[str, Dict[str, Dict[str, str]]] = self._get_database()

    def _get_database(self):
            print(f"[AniBridge v3] Sourcing distribution payload from Release channel...")
            try:
                # Mirroring target distribution binaries
                response = requests.get(RAW_MAPPINGS_URL, timeout=15)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                raise IOError(f"Failed to bootstrap database asset file from GitHub Releases: {e}")
            
    def convert_episode(self, source_rule: str, target_rule: str, current_episode: int) -> int:
        source_start, source_end = map(int, source_rule.split("-"))
        target_start, _ = map(int, target_rule.split("-"))
        
        if not (source_start <= current_episode <= source_end):
            raise ValueError(f"Episode {current_episode} falls outside source range {source_rule}")
            
        offset = current_episode - source_start
        final_episode = target_start + offset
        
        return final_episode
    
    def extract_anilist_mapping(self, data: Dict[str, Dict[str, str]]):
        # Look through the dictionary keys
        for key in data.keys():
            if key.startswith("anilist:"):
                # Split the string on the colon and convert the second half to an integer
                anilist_id = key.split(":")[1]
                source_dict = data.get(key)
                if not source_dict: return None, None, None
                source_range = list(source_dict.keys())[0]
                target_range = source_dict.get(source_range)
                if not target_range: return None, None, None
                return anilist_id, source_range, target_range
        return None, None, None
    
    def get_anilist_info(self, tmdb_id: str, season: str, episode: str):
        mapping = self.mappings_db.get(f'tmdb_show:{tmdb_id}:s{season}')
        if not mapping:
            logger.error(f"Could not find mapping for tmdb_id {tmdb_id}")
            return None, None
        anilist_id, source_range, target_range = self.extract_anilist_mapping(mapping)
        if not anilist_id or not source_range or not target_range:
            logger.error(f'Could not extract anilist mapping for tmdb_id {tmdb_id}. anilist_id: {anilist_id}, source_range: {source_range}, target_range: {target_range}')
            return None, None
        eps_number = self.convert_episode(source_range, target_range, int(episode))
        return anilist_id, eps_number
        


    
# --- IMPLEMENTATION VERIFICATION TESTING HARNESS ---
if __name__ == "__main__":
    resolver = AniBridgeV3Resolver()
    a, b = resolver.get_anilist_info(tmdb_id="88046", season="1", episode="14") # Fire Force
    print(a, b)