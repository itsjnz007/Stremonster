import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
import time
import shutil
import threading
import libtorrent as lt  # type: ignore[import-untyped]
from typing import List, Tuple, Dict, Any, Deque, Callable, cast
from collections import deque
from app.core.logger import Logger
from app.models.responses import TorrentResponse, WebResponse
from app.core.multithreading import MultiThreading
from app.config import CACHE_DIR, TUNNEL_URL
import logging

logger = Logger('torrent', level=logging.DEBUG)

class Torrent:
    def __init__(self, threadpool: MultiThreading, connection_speed: int = 200) -> None:
        self.connection_speed: int = connection_speed
        self._session: Any = None
        self._session_lock: threading.Lock = threading.Lock()
        self.threadpool: MultiThreading = threadpool
        self.temp_dir: str = CACHE_DIR + '/torrent_cache'
        
        self._completed_qualities: set[str] = set()
        self._qualities_lock: threading.Lock = threading.Lock()
        
        # Pre-initialize the single instance session
        self._get_session()

    def _get_session(self) -> Any:
        """Thread-safely initializes a single shared libtorrent session context."""
        with self._session_lock:
            if self._session is None:
                # Only clean the directory once on the very first boot of the app
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                os.makedirs(self.temp_dir, exist_ok=True)

                params: Any = lt.session_params() # type: ignore
                params.listen_interfaces = "0.0.0.0:6881,[::]:6891"
                self._session = lt.session(params) # type: ignore
                
                settings: Dict[str, Any] = self._session.get_settings() # type: ignore
                settings["connection_speed"] = self.connection_speed
                settings["dht_upload_rate_limit"] = 8000
                settings["max_queued_disk_bytes"] = 32 * 1024 * 1024  
                settings["cache_size"] = 2048                         
                
                self._session.apply_settings(settings) # type: ignore
                logger.info(f"✓ Shared Volatile RAM session optimized at: {self.temp_dir}")
            return self._session # type: ignore

    @staticmethod
    def get_speed_category(speed_kb_s: float) -> tuple[str, int]:
        if speed_kb_s < 1.0:   return ("dead", 0)
        if speed_kb_s < 100.0: return ("very slow", 1)
        if speed_kb_s < 300.0: return ("slow", 2)
        if speed_kb_s < 700.0: return ("medium", 3)
        if speed_kb_s < 1200.0:return ("fast", 4)
        if speed_kb_s < 2000.0:return ("ultra fast", 5)
        return ("extreme", 6)

    def test_torrent(self, info_hash: str, quality: str, fileIdx: int = -1, timeout: int = 7) -> float:
        """Synchronously connects to an infohash and returns its maximum download speed in KB/s."""
        with self._qualities_lock:
            if quality in self._completed_qualities:
                return 0.0

        ses: Any = self._get_session()
        magnet_link: str = f"magnet:?xt=urn:btih:{info_hash}"
        
        torrent_params: Any = lt.parse_magnet_uri(magnet_link) # type: ignore
        torrent_params.save_path = os.path.join(self.temp_dir, info_hash)
        torrent_params.storage_mode = lt.storage_mode_t(2) # type: ignore
        torrent_params.flags |= lt.torrent_flags.sequential_download # type: ignore
        
        handle: Any = ses.add_torrent(torrent_params)
        max_speed: float = 0.0

        try:
            logger.info(f"Swarm Link: Pulling metadata for {info_hash[:8]} ({quality})...")
            
            meta_timeout: float = time.time() + 15
            while not handle.status().has_metadata:
                if time.time() > meta_timeout:
                    logger.info(f"❌ Fast-skip: Dead metadata path for {info_hash[:8]}.")
                    return 0.0
                
                with self._qualities_lock:
                    if quality in self._completed_qualities:
                        return 0.0
                time.sleep(0.1)

            # --- ADDED: File prioritization ---
            if fileIdx >= 0:
                torrent_info = handle.get_torrent_info()
                num_files = torrent_info.num_files()
                
                if fileIdx < num_files:
                    # Prioritize the selected file index and set others to 0 (do not download)
                    for i in range(num_files):
                        if i == fileIdx:
                            handle.file_priority(i, 7)  # Highest priority
                        else:
                            handle.file_priority(i, 0)  # Skip downloading
                else:
                    logger.warning(f"File index {fileIdx} out of range for torrent {info_hash[:8]} (has {num_files} files).")
            # -----------------------------------

            logger.info(f"✓ Link Alive for {info_hash[:8]}. Sampling speeds...")
            speeds: List[float] = []
            start_time: float = time.time()
            while time.time() - start_time < timeout:
                with self._qualities_lock:
                    if quality in self._completed_qualities:
                        break

                speed_kb_s: float = handle.status().download_rate / 1024.0
                speeds.append(speed_kb_s)
                time.sleep(0.4)

            if speeds:
                max_speed = max(speeds)
                category, rank = self.get_speed_category(max_speed)
                logger.info(f"🏁 Peak: {info_hash[:8]} -> {max_speed:.2f} KB/s ({category.upper()})")
                
                if rank >= 4:  
                    with self._qualities_lock:
                        self._completed_qualities.add(quality)
                    logger.info(f"⭐ [{quality.upper()}] Satisfied. Canceling remaining pending searches.")

        except Exception as e:
            logger.error(f"Error testing hash {info_hash}: {e}")
        finally:
            try:
                start = time.perf_counter()

                if handle and handle.is_valid():
                    t = time.perf_counter()
                    logger.debug(f"Removing Torrent")
                    ses.remove_torrent(handle)
                    logger.debug(f"remove_torrent={time.perf_counter()-t:.3f}s")

                if os.path.exists(torrent_params.save_path):
                    t = time.perf_counter()
                    shutil.rmtree(torrent_params.save_path, ignore_errors=True)
                    logger.debug(f"rmtree={time.perf_counter()-t:.3f}s")

                logger.debug(f"finally total={time.perf_counter()-start:.3f}s")

            except Exception as e:
                logger.error(f"Error removing cache: {e}")

        return max_speed

    def get_best_torrents(self, streams: List[TorrentResponse]) -> List[TorrentResponse]:
        """Runs single resolution tiers side-by-side using aggressive low-latency timeout configurations."""
        valid_streams: List[TorrentResponse] = [s for s in streams if s.get("infoHash")]
        if not valid_streams: 
            return streams

        with self._qualities_lock: 
            self._completed_qualities.clear()

        quality_buckets: Dict[str, Deque[TorrentResponse]] = {}
        for s in valid_streams:
            q: str = str(s.get("name", "Unknown"))
            if q not in quality_buckets:
                quality_buckets[q] = deque()
            quality_buckets[q].append(s)

        execution_waves: List[List[TorrentResponse]] = []
        while any(len(bucket) > 0 for bucket in quality_buckets.values()):
            current_wave: List[TorrentResponse] = []
            for bucket in quality_buckets.values():
                if bucket:
                    current_wave.append(bucket.popleft())
            execution_waves.append(current_wave)

        results: List[Tuple[TorrentResponse, float]] = []

        for wave_idx, wave_streams in enumerate(execution_waves, start=1):
            filtered_wave_streams: List[TorrentResponse] = []
            for s in wave_streams:
                with self._qualities_lock:
                    if str(s.get("name", "Unknown")) not in self._completed_qualities:
                        filtered_wave_streams.append(s)
            
            if not filtered_wave_streams:
                continue

            logger.info(f"🚀 Processing Interleaved Wave {wave_idx}/{len(execution_waves)}")
            
            tasks: List[Callable[..., Any]] = [
                lambda _, s=stream: ( # type: ignore
                    s, 
                    self.test_torrent(
                        str(s.get("infoHash", "")), 
                        str(s.get("name", "Unknown")), 
                        fileIdx=int(s.get("fileIdx", -1)) # <-- EXTRACTED AND PASSED FILEIDX

                    )
                ) or 0.0  # type: ignore
                for stream in filtered_wave_streams
            ]
            
            wave_results: List[Any] = [r for r in self.threadpool.get_all(tasks)]
            for r in wave_results:
                if isinstance(r, tuple) and len(r) == 2: # type: ignore
                    results.append(cast(Tuple[TorrentResponse, float], r))

        quality_map: Dict[str, Tuple[TorrentResponse, float]] = {}
        for stream, speed in results:
            quality: str = str(stream.get("name", "Unknown"))
            if quality not in quality_map or speed > quality_map[quality][1]:
                quality_map[quality] = (stream, speed)

        final_streams: List[TorrentResponse] = []
        for quality, (stream, speed) in quality_map.items():
            category, _ = self.get_speed_category(speed)
            stream["title"] = f"Torrent ({category.title()})"
            final_streams.append(stream)

        # REMOVED: shutil.rmtree(self.temp_dir)
        # Leaving the base directory intact allows subsequent requests to reuse the active session.
        return final_streams

    def shutdown(self) -> None:
        """Call this when your main application is fully shutting down."""
        if self._session:
            logger.info("Pausing libtorrent session for fast teardown...")
            self._session.pause()

    @staticmethod
    def to_web_response(response: TorrentResponse) -> WebResponse:
        """Placeholder conversion to a web response."""
        return WebResponse(
            title=response.get("title", "Unknown"),
            name=response.get("name", "Unknown"),
            url=f"{TUNNEL_URL}/stream-torrent/{response.get('infoHash', '')}/{response.get('fileIdx', '0')}.mkv",
            subtitles=[],
            origin=None,
            behaviorHints=None
        )


if __name__ == "__main__":
    TEST_DATA: list[TorrentResponse] = [
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "4k", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "4k", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "1080p", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "1080p", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "720p", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "720p", "title": "Torrent"},
    ]
    threadpool = MultiThreading(3)
    
    # 1. Initialize once
    torrent_tester = Torrent(threadpool, connection_speed=10)
    
    # 2. You can now safely call this multiple times without it breaking!
    result = torrent_tester.get_best_torrents(TEST_DATA)
    logger.info(f"Final Returned Results Map 1: {result}")
    
    # result_2 = torrent_tester.get_best_torrents(TEST_DATA)
    # logger.info(f"Final Returned Results Map 2: {result_2}")

    # 3. Kills the test process instantly so it doesn't hang in terminal.
    os._exit(0)