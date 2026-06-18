import subprocess
from pathlib import Path
import time
import requests
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = Path(".cache") / "subtitles"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def build_absolute_url(base, parent_path, new_path):
    if new_path.startswith("http"):
        return new_path
    if new_path.startswith("/"):
        return base + new_path
    parent_dir = parent_path.rsplit("/", 1)[0]
    return base + parent_dir + "/" + new_path

def get_base_and_path_url(url):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query
    return base, path

def parse_m3u8_playlist(m3u8_url):
    """Recursively resolves the media playlist and returns segment URLs with durations."""
    print("[HLS] Resolving playlist...")
    r = requests.get(m3u8_url, timeout=20)
    r.raise_for_status()
    
    lines = r.text.splitlines()
    base, path = get_base_and_path_url(m3u8_url)

    # Resolve master playlist if present
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            next_url = lines[i + 1].strip()
            stream_url = build_absolute_url(base, path, next_url)
            return parse_m3u8_playlist(stream_url)

    # Parse media segments
    segments = []
    for i, line in enumerate(lines):
        if line.startswith("#EXTINF"):
            duration = float(line.split(":")[1].replace(",", ""))
            seg_path = lines[i + 1].strip()
            seg_url = build_absolute_url(base, path, seg_path)
            segments.append({"url": seg_url, "duration": duration})
            
    return segments

def download_segment(args):
    """Worker function to download a single segment."""
    url, output_path, headers = args
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Failed downloading segment {url}: {e}")
    return False

def extract_parallel_audio(m3u8_url, output_wav, headers, skip_seconds=60, duration_seconds=60):
    """Downloads HLS segments in parallel, stitches them, and converts to WAV."""
    print("[HLS] Parsing HLS stream structure...")
    all_segments = parse_m3u8_playlist(m3u8_url)
    
    # Windowing: isolate subset of segments based on -ss and -t parameters
    accumulated_time = 0.0
    target_segments = []
    
    for seg in all_segments:
        if accumulated_time + seg["duration"] > skip_seconds and accumulated_time < (skip_seconds + duration_seconds):
            target_segments.append(seg)
        accumulated_time += seg["duration"]
        if accumulated_time >= (skip_seconds + duration_seconds):
            break
            
    if not target_segments:
        raise ValueError("No segments found in the requested time window.")

    print(f"[HLS] Concurrently downloading {len(target_segments)} segments (~{duration_seconds}s)...")
    temp_dir = CACHE_DIR / "temp_segments"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare download arguments for thread pool
    download_tasks = []
    for idx, seg in enumerate(target_segments):
        seg_path = temp_dir / f"seg_{idx:05d}.ts"
        download_tasks.append((seg["url"], seg_path, headers))

    # Parallel downloading using thread pool
    success_count = 0
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(download_segment, task): task[1] for task in download_tasks}
        for future in as_completed(futures):
            if future.result():
                success_count += 1
                
    print(f"[HLS] Successfully downloaded {success_count}/{len(target_segments)} segments.")

    # Create FFmpeg concat list file INSIDE the temp_dir so paths are relative and simple
    concat_list = temp_dir / "concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for idx in range(len(target_segments)):
            filename = f"seg_{idx:05d}.ts"
            f.write(f"file '{filename}'\n")

    # Stitch and convert to target WAV in one FFmpeg call
    print("[FFMPEG] Stitching and converting segments to WAV...")
    
    # Resolve absolute path of the output file BEFORE changing directories
    abs_output_wav = str(Path(output_wav).resolve())
    
    import os
    original_cwd = os.getcwd()
    os.chdir(temp_dir) # Temporarily move to temp dir so relative paths in concat.txt resolve perfectly

    try:
        result = subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", "concat.txt",
            "-vn", "-ac", "1", "-ar", "16000",
            abs_output_wav # Use the correct resolved absolute path
        ], capture_output=True, text=True)
    finally:
        os.chdir(original_cwd) # Always change back to the original directory

    # Use shutil.rmtree to safely delete the temp_segments folder and all its contents at once
    import shutil
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    if result.returncode != 0:
        raise Exception(f"ffmpeg failed: {result.stderr}")

def sync_hls_subtitle(m3u8_url, subtitle_url, headers=None, imdb_id="test"):
    start_time = time.time()

    audio_file = CACHE_DIR / f"{imdb_id}.wav"
    sub_file = CACHE_DIR / f"{imdb_id}_input.srt"
    out_file = CACHE_DIR / f"{imdb_id}_synced.srt"

    if out_file.exists():
        out_file.unlink()

    # Extract audio via parallel segment downloader
    extract_parallel_audio(
        m3u8_url, 
        audio_file, 
        headers, 
        skip_seconds=0, 
        duration_seconds=300
    )

    print("Audio size:", audio_file.stat().st_size)

    print("Downloading subtitle...")
    r = requests.get(subtitle_url, timeout=20)
    if r.status_code != 200:
        raise Exception("subtitle download failed")

    subtitle = r.text
    # Normalize line endings
    subtitle = subtitle.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\r\n", "\n")

    sub_file.write_text(subtitle, encoding="utf-8")
    print("Subtitle size:", sub_file.stat().st_size)

    print("Running ffsubsync...")
    result = subprocess.run([
        "ffsubsync", str(audio_file),
        "-i", str(sub_file),
        "-o", str(out_file)
    ], capture_output=True, text=True)

    print(result.stdout)
    print(result.stderr)

    if result.returncode != 0:
        raise Exception("ffsubsync failed")

    print("Output size:", out_file.stat().st_size)
    if out_file.stat().st_size == 0:
        raise Exception("ffsubsync created empty subtitle")

    print("Saved:", out_file)
    print("Time:", time.time() - start_time, "seconds")

    return out_file.read_text(encoding="utf-8")

if __name__ == "__main__":
    hsl_url = """http://localhost:8000/stream.m3u8?url=https%3A%2F%2Fjoe.goldweather.net%2FusTtvED1GyxFe8kuPKyu8g4VMEmAvFeK0qYU6cbwvHwHo73cCYY_piLWOWbtMkwkznqfz_2QEuk_RZCmLb9YyPykBqQg2eXE9IHfW3tY0gi8oxDDggTi4LNelvtYEqmZDQtm3OyHWVjFOSzUhMbjqLmxZcjXGbrgxemWXqOON46ayqRbQF-D-Eh62oNeAM1Gyolklsj6Mom5I43iQFlY8rjrp0Ih4r4zSPFoPjl9i9XtKkn91AvvtOIITox6LJ_UVU4AK9xdaJssFAxfQ-Dh_USe0aUQvjTzOoodar4TIkNMvWbJP7d733o8KT9lYGdBK-Y9foijYqYmb6A7p75m9YInVrV-rOt3NHfnInW4CywpS9Rh1HPvsbXhVx6O1BzS4Rtiv5Bm5L-RQbs8KI_iD3Cktg8iXof1lvxXThQttuNqCFScCVn9mFCvpNVAdP7NHJ5Le1hdlpMUhGydZ3HGYiagAsuCBnAiukcTWbJhjrc36LbqnSt0Pc_5l2uFsL7Q6jyzJun_ZzwRfSOCnqTMntrJVTvFriyYJpuCSOFsk4y_zxiFH7hMXTuZeuTAoausNpQOOukHrRmTa61eSe3P425lsGfzlO243j0jZqG1_tJxgDCo6T68lsIgfZQVctEL9dWVuHCQ-imDXM2meu68WeYxtYpcgUJ_tDDpauipug-zUl3HtKqx4FZsS5TEjqPz8%2Findex.m3u8&headers=%7B%22ffuser-agent%22%3A%20%22Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%3B%20rv%3A137.0%29%20Gecko%2F20100101%20Firefox%2F137.0%22%2C%20%22accept%22%3A%20%22%2A%2F%2A%22%2C%20%22accept-language%22%3A%20%22en-US%2Cen%3Bq%3D0.5%22%2C%20%22sec-fetch-dest%22%3A%20%22empty%22%2C%20%22sec-fetch-mode%22%3A%20%22cors%22%2C%20%22sec-fetch-site%22%3A%20%22cross-site%22%2C%20%22origin%22%3A%20%22https%3A%2F%2Fvidking.net%22%2C%20%22referer%22%3A%20%22https%3A%2F%2Fvidking.net%2F%22%7D"""
    sub_url = "https://subs5.strem.io/en/download/subencoding-stremio-utf8/src-api/file/1958134220"
    
    custom_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Origin": "https://vidking.net",
        "Referer": "https://vidking.net/"
    }

    synced = sync_hls_subtitle(
        hsl_url,
        sub_url,
        headers=custom_headers
    )