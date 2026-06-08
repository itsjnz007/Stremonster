import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
import platform
import time
import shutil
import threading
import libtorrent as lt  # type: ignore
from typing import List, Tuple, Dict, Any
from collections import deque
from app.core.logger import Logger
from app.models.responses import TorrentResponse
from app.core.multithreading import MultiThreading

logger = Logger('torrent')

class Torrent:
    def __init__(self, connection_speed: int = 200):
        self.connection_speed = connection_speed
        self._session = None
        self._session_lock = threading.Lock()
        
        if platform.system() == "Linux" and os.path.exists("/dev/shm"):
            self.temp_dir = "/dev/shm/torrent_speed_cache"
        elif platform.system() == "Darwin" and os.path.exists("/Volumes"):
            self.temp_dir = "/tmp/torrent_speed_cache"
        else:
            self.temp_dir = "./.temp_ram_fallback"

        self._completed_qualities = set()
        self._qualities_lock = threading.Lock()
        
        # Pre-initialize the single instance session to eliminate initialization delays
        self._get_session()

    def _get_session(self) -> lt.session: # type: ignore
        """Thread-safely initializes a single shared libtorrent session context."""
        with self._session_lock:
            if self._session is None: # type: ignore
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                os.makedirs(self.temp_dir, exist_ok=True)

                params = lt.session_params() # type: ignore
                params.listen_interfaces = "0.0.0.0:6881,[::]:6891"
                self._session = lt.session(params) # type: ignore
                
                settings = self._session.get_settings() # type: ignore
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
        if speed_kb_s < 10.0:  return ("very slow", 1)
        if speed_kb_s < 100.0: return ("slow", 2)
        if speed_kb_s < 500.0: return ("medium", 3)
        if speed_kb_s < 1500.0:return ("fast", 4)
        if speed_kb_s < 5000.0:return ("ultra fast", 5)
        return ("extreme", 6)

    def test_torrent(self, info_hash: str, quality: str, timeout: int = 5) -> float:
        """Synchronously connects to an infohash and returns its maximum download speed in KB/s."""
        with self._qualities_lock:
            if quality in self._completed_qualities:
                return 0.0

        ses = self._get_session() # type: ignore
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
        
        torrent_params = lt.parse_magnet_uri(magnet_link) # type: ignore
        torrent_params.save_path = os.path.join(self.temp_dir, info_hash)
        torrent_params.storage_mode = lt.storage_mode_t(2) # type: ignore
        torrent_params.flags |= lt.torrent_flags.sequential_download # type: ignore
        
        handle = ses.add_torrent(torrent_params) # type: ignore
        max_speed = 0.0

        try:
            logger.info(f"Swarm Link: Pulling metadata for {info_hash[:8]} ({quality})...")
            
            meta_timeout = time.time() + 15
            while not handle.status().has_metadata: # type: ignore
                if time.time() > meta_timeout:
                    logger.info(f"❌ Fast-skip: Dead metadata path for {info_hash[:8]}.")
                    return 0.0
                
                with self._qualities_lock:
                    if quality in self._completed_qualities:
                        return 0.0
                time.sleep(0.1)

            logger.info(f"✓ Link Alive for {info_hash[:8]}. Sampling speeds...")
            speeds = []
            start_time = time.time()
            while time.time() - start_time < timeout:
                with self._qualities_lock:
                    if quality in self._completed_qualities:
                        break

                speed_kb_s = handle.status().download_rate / 1024.0 # type: ignore
                speeds.append(speed_kb_s) # type: ignore
                time.sleep(0.4)

            if speeds:
                max_speed = max(speeds) # type: ignore
                category, rank = self.get_speed_category(max_speed) # type: ignore
                logger.info(f"🏁 Peak: {info_hash[:8]} -> {max_speed:.2f} KB/s ({category.upper()})")
                
                if rank >= 4:  # Fast or higher benchmarks
                    with self._qualities_lock:
                        self._completed_qualities.add(quality)
                    logger.info(f"⭐ [{quality.upper()}] Satisfied. Canceling remaining pending searches.")

        except Exception as e:
            logger.error(f"Error testing hash {info_hash}: {e}")
        finally:
            try:
                ses.remove_torrent(handle) # type: ignore
                shutil.rmtree(torrent_params.save_path, ignore_errors=True)
            except Exception:
                pass

        return max_speed # type: ignore

    def get_best_torrents(self, streams: List[TorrentResponse], timeout: int = 5) -> List[TorrentResponse]:
        """Runs single resolution tiers side-by-side using aggressive low-latency timeout configurations."""
        valid_streams = [s for s in streams if s.get("infoHash")]
        if not valid_streams: 
            return streams

        with self._qualities_lock: 
            self._completed_qualities.clear()

        # Build Round-Robin Buckets
        quality_buckets: Dict[str, deque] = {}
        for s in valid_streams:
            q = s.get("name", "Unknown")
            if q not in quality_buckets:
                quality_buckets[q] = deque()
            quality_buckets[q].append(s)

        execution_waves: List[List[Dict[str, Any]]] = []
        while any(len(bucket) > 0 for bucket in quality_buckets.values()):
            current_wave = []
            for bucket in quality_buckets.values():
                if bucket:
                    current_wave.append(bucket.popleft())
            execution_waves.append(current_wave)

        mt = MultiThreading(logger=logger, max_workers=len(quality_buckets))
        results: List[Tuple[TorrentResponse, float]] = []

        for wave_idx, wave_streams in enumerate(execution_waves, start=1):
            # Dynamic wave-skipping check before initiating thread worker pool mappings
            filtered_wave_streams = []
            for s in wave_streams:
                with self._qualities_lock:
                    if s.get("name", "Unknown") not in self._completed_qualities:
                        filtered_wave_streams.append(s)
            
            if not filtered_wave_streams:
                continue

            logger.info(f"🚀 Processing Interleaved Wave {wave_idx}/{len(execution_waves)}")
            
            tasks = [
                lambda s=stream: (s, self.test_torrent(s["infoHash"], s.get("name", "Unknown"), timeout))
                for stream in filtered_wave_streams
            ]
            
            wave_results = mt.get_all(tasks)
            results.extend(wave_results)

        # Build final optimized outputs mapping dicts
        quality_map = {}
        for stream, speed in results:
            quality = stream.get("name", "Unknown")
            if quality not in quality_map or speed > quality_map[quality][1]:
                quality_map[quality] = (stream, speed)

        final_streams = []
        for quality, (stream, speed) in quality_map.items():
            category, _ = self.get_speed_category(speed)
            stream["title"] = f"Torrent ({category.title()})"
            final_streams.append(stream)

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        return final_streams

if __name__ == "__main__":
    # Test dataset containing duplicates inside the 1080p and 720p buckets
    TEST_DATA: list[TorrentResponse] = [
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "4k", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "4k", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "1080p", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "1080p", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "720p", "title": "Torrent"},
        {"infoHash": "4615a780aa66f3a09218c5d458505c2d17770920", "name": "720p", "title": "Torrent"},
    ]

    torrent_tester = Torrent(connection_speed=200)
    result = torrent_tester.get_best_torrents(TEST_DATA, timeout=5)
    logger.info(f"Final Returned Results Map: {result}")