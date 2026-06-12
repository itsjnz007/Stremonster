import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from typing import Dict
from app.core.logger import Logger
from typing import Optional
import logging

logger = Logger('anilist', level=logging.DEBUG)

# Official v3 Direct Production Release Distribution URL
RAW_MAPPINGS_URL = "https://github.com/anibridge/anibridge-mappings/releases/download/v3/mappings.json"
ANI_ZIP_URL = "https://api.ani.zip/mappings?imdb_id=%s"

class AniBridgeV3Resolver:
    """
    In-memory resolver designed to ingest and parse AniBridge v3 specifications
    defined by the 'provider:id[:scope]' descriptor layout.
    """
    def __init__(self):
        self.mappings_db: Dict[str, Dict[str, Dict[str, str]]] = self._get_database()

    def _get_database(self):
            logger.info(f"Sourcing distribution payload from Release channel...")
            try:
                # Mirroring target distribution binaries
                response = requests.get(RAW_MAPPINGS_URL, timeout=15)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                raise IOError(f"Failed to bootstrap database asset file from GitHub Releases: {e}")
            
    def convert_episode(self, source_rule: str, target_rule: str, current_episode: int) -> int:
        def parse_range(rule: str):
            start, end = rule.split("-")
            return int(start), int(end) if end else None

        source_start, source_end = parse_range(source_rule)
        target_start, target_end = parse_range(target_rule)

        # Same range mapping
        if source_rule == target_rule: return current_episode

        # Validate source range if an end is specified
        if source_end is not None and not (source_start <= current_episode <= source_end):
            raise ValueError(
                f"Episode {current_episode} is outside source range {source_start}-{source_end}"
            )

        # Calculate mapped episode
        mapped_ep = target_start + (current_episode - source_start)

        # Validate target range if an end is specified
        if target_end is not None and mapped_ep > target_end:
            raise ValueError(
                f"Mapped episode {mapped_ep} is outside target range "
                f"{target_start}-{target_end}"
            )

        return mapped_ep

        # if 
        # if target_start == source_start: return current_episode

        # if source_start == : return current_episode
        # else: return source_start + current_episode
        
        # if not (source_start <= current_episode <= source_end):
        #     raise ValueError(f"Episode {current_episode} falls outside source range {source_rule}")
            
        # offset = current_episode - source_start
        # final_episode = target_start + offset
        
        return final_episode
    
    def extract_mapping(self, data: Dict[str, Dict[str, str]], extraction_key: str = 'mal'):
        # Look through the dictionary keys
        for key in data.keys():
            if key.startswith(f"{extraction_key}:"):
                # Split the string on the colon and convert the second half to an integer
                mal_id = key.split(":")[1]
                source_dict = data.get(key)
                if not source_dict: return None, None, None
                source_range = list(source_dict.keys())[0]
                target_range = source_dict.get(source_range)
                if not target_range: return None, None, None
                return mal_id, source_range, target_range
        return None, None, None
    
    def get_mal_info(self, imdb_id: str, season: str, episode: str):
        ani_zip_response = requests.get(ANI_ZIP_URL % imdb_id)
        ani_zip_response.raise_for_status()
        tvdb_id: Optional[str] = ani_zip_response.json().get("mappings", {}).get("thetvdb_id")
        if not tvdb_id: raise Exception(f"No tvdb mapping found for imdb id: {imdb_id}")
        logger.debug(f"Found tvdb id '{tvdb_id}' mapping for imdb id: {imdb_id}")
        mapping = self.mappings_db.get(f'tvdb_show:{tvdb_id}:s{season}')
        if not mapping: raise Exception(f"Could not find mapping for tvdb_id {tvdb_id}")
        mal_id, source_range, target_range = self.extract_mapping(mapping, 'mal')
        if not mal_id or not source_range or not target_range:
            raise Exception(f'Could not extract anilist mapping for tvdb_id {tvdb_id}. mal_id: {mal_id}, source_range: {source_range}, target_range: {target_range}')
        eps_number = self.convert_episode(source_range, target_range, int(episode))
        return mal_id, eps_number
    
    def get_anilist_info(self, imdb_id: str, season: str, episode: str):
        ani_zip_response = requests.get(ANI_ZIP_URL % imdb_id)
        ani_zip_response.raise_for_status()
        tvdb_id: Optional[str] = ani_zip_response.json().get("mappings", {}).get("thetvdb_id")
        if not tvdb_id: raise Exception(f"No tvdb mapping found for imdb id: {imdb_id}")
        logger.debug(f"Found tvdb id '{tvdb_id}' mapping for imdb id: {imdb_id}")
        mapping = self.mappings_db.get(f'tvdb_show:{tvdb_id}:s{season}')
        if not mapping: raise Exception(f"Could not find mapping for tvdb_id {tvdb_id}")
        mal_id, source_range, target_range = self.extract_mapping(mapping, 'anilist')
        if not mal_id or not source_range or not target_range:
            raise Exception(f'Could not extract anilist mapping for tvdb_id {tvdb_id}. mal_id: {mal_id}, source_range: {source_range}, target_range: {target_range}')
        eps_number = self.convert_episode(source_range, target_range, int(episode))
        return mal_id, eps_number
        


    
# --- IMPLEMENTATION VERIFICATION TESTING HARNESS ---
if __name__ == "__main__":
    resolver = AniBridgeV3Resolver()
    # print(resolver.get_anilist_info(imdb_id="tt9307686", season="3", episode="1"))
    print(resolver.get_mal_info(imdb_id="tt9307686", season="2", episode="10"))