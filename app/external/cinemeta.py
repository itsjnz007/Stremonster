import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional
from app.core.logger import Logger
import requests, logging
from app.models.cinemeta import CinemetaResponse

logger = Logger('cinemeta', level=logging.INFO)

class Cinemeta:
    def __init__(self):
        self.base_url = "https://v3-cinemeta.strem.io"

    def get_metadata(self, imdb_id: str, type: str) -> Optional[CinemetaResponse]:
        if not type in ["movie", "series"]:
            logger.error("Type must be either 'movie' or 'series'")
            return

        if len(imdb_id.split(":"))>1:
            logger.error("IMDb ID should not contain season or episode information")
            return
        
        url = f"{self.base_url}/meta/{type}/{imdb_id}.json"
        print(f"Fetching metadata from {url}")
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to fetch metadata for IMDb ID {imdb_id}: {response.status_code}")
            return

    def get_next_episode(self, id: str) -> Optional[str]:
        """Given an ID in the format 'imdb_id:season:episode', fetch the next episode's id.

        If a season ends, use the first episode of the next season. If no more
        seasons/episodes exist, return None.
        """
        parts = id.split(":")
        if len(parts) != 3:
            logger.error("ID must be in the format 'imdb_id:season:episode'")
            return None

        imdb_id, current_season_str, current_episode_str = parts
        try:
            current_season = int(current_season_str)
            current_episode = int(current_episode_str)
        except ValueError:
            logger.error("Season and episode numbers must be integers")
            return None

        # Fetch metadata using your existing method (which returns a CinemetaResponse)
        response: Optional[CinemetaResponse] = self.get_metadata(imdb_id, "series")
        if not response or "meta" not in response:
            return None

        videos = response["meta"].get("videos", [])
        if not videos:
            return None

        # 1. Try to find the exact next episode in the same season (e.g., S1E1 -> S1E2)
        for video in videos:
            if (
                video.get("season") == current_season
                and video.get("episode") == current_episode + 1
            ):
                return video.get("id")

        # 2. If not found, it means current_episode was the last of that season.
        # Look for episode 1 of the next chronological season (e.g., S1 End -> S2E1)
        next_season = current_season + 1
        for video in videos:
            if video.get("season") == next_season and video.get("episode") == 1:
                return video.get("id")

        # 3. If neither exists, we've reached the end of the series
        return None


if __name__ == "__main__":
    cinemeta = Cinemeta()
    metadata = cinemeta.get_metadata("tt0310460", "series")
    print(f"Metadata -> {metadata}")
    next_episode_id = cinemeta.get_next_episode("tt0310460:1:4")
    print(f"Next Episode ID -> {next_episode_id}")
    next_episode_id = cinemeta.get_next_episode("tt0310460:7:4")
    print(f"Next Episode ID -> {next_episode_id}")