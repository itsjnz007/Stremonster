from app.config import TUNNEL_URL
from flask import Response, request, jsonify
from urllib.parse import quote, urljoin
import requests, re
from app.core.logger import Logger
from typing import Any, Dict, List, Optional

logger = Logger("proxy")

def respond_with(data: dict[str, object]) -> Response:
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    return resp


class Proxy:
    @staticmethod
    def get_best_stream(stream_url: str, origin: Optional[str] = None) -> str:
        """
        Parses an HLS Master Playlist and returns the absolute target URL 
        for the highest quality variant stream.
        """
        if ".m3u8" not in stream_url.lower():
            return stream_url

        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        if origin:
            headers['Origin'] = origin
            headers['Referer'] = origin + '/'

        try:
            # We fetch the RAW source master playlist directly, bypassing our local proxy loop
            response = requests.get(stream_url, headers=headers, timeout=10)
            if response.status_code != 200:
                return stream_url
            
            content = response.text
            if "#EXT-X-STREAM-INF" not in content:
                return stream_url

            logger.info("--- Extracting Highest HLS Track Quality ---")
            lines = content.splitlines()
            streams: List[Dict[str, Any]] = []
            
            current_meta = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith("#EXT-X-STREAM-INF:"):
                    current_meta = line
                elif current_meta and not line.startswith("#"):
                    bandwidth = 0
                    resolution = "Unknown"
                    
                    bw_match = re.search(r'BANDWIDTH=(\d+)', current_meta)
                    if bw_match:
                        bandwidth = int(bw_match.group(1))
                        
                    res_match = re.search(r'RESOLUTION=(\d+x\d+)', current_meta)
                    if res_match:
                        resolution = res_match.group(1)
                    
                    streams.append({
                        'bandwidth': bandwidth,
                        'resolution': resolution,
                        'url': urljoin(stream_url, line)
                    })
                    current_meta = None

            if not streams:
                return stream_url

            # Sort to select the absolute best payload config
            streams.sort(key=lambda x: (x['bandwidth'], x['resolution']), reverse=True)
            best_stream = streams[0]
            
            logger.info(f"[Selection] -> Chosen: {best_stream['resolution']} ({best_stream['bandwidth'] / 1_000_000:.2f} Mbps)")
            return best_stream['url']

        except Exception as e:
            logger.error(f"Error parsing best stream quality: {e}")
            return stream_url

    @staticmethod
    def get_proxy_url(stream_url: str, origin: str | None = None) -> str:
        """Construct the initial proxy URL wrapper for Stremio to consume."""
        # 1. First, find out what the *actual* best quality endpoint URL is from the provider
        best_target_url = Proxy.get_best_stream(stream_url, origin)
        
        # 2. Package that optimized URL down into your proxy route assignment 
        proxied_url = urljoin(TUNNEL_URL, f"/proxy?url={quote(best_target_url, safe='%')}")
        if origin: 
            proxied_url += f"&origin={quote(origin, safe='%')}"

        logger.info(f"Generated Proxied Endpoint: {proxied_url}")
        return proxied_url

    @staticmethod
    def proxy_m3u8():
        return Proxy.proxy()

    @staticmethod
    def proxy_stream_ts():
        return Proxy.proxy()
    
    @staticmethod
    def handle_m3u8(r: requests.Response, url: str, origin: str):
        playlist = r.text
        rewritten_lines: list[str] = []

        for raw_line in playlist.splitlines():
            line = raw_line.rstrip()

            if not line:
                rewritten_lines.append("")
                continue

            # CRITICAL FIX: If the line contains an embedded audio track group, rewrite its URI property too
            if line.startswith("#"):
                if 'URI=' in line:
                    parts = line.split('URI="')
                    if len(parts) > 1:
                        sub_uri = parts[1].split('"')[0]
                        absolute_audio_url = urljoin(url, sub_uri)
                        encoded_audio_url = quote(absolute_audio_url, safe="%")
                        
                        proxied_audio = f"{TUNNEL_URL}/proxy?url={encoded_audio_url}&origin={origin}"
                        line = line.replace(f'URI="{sub_uri}"', f'URI="{proxied_audio}"')
                
                rewritten_lines.append(line)
                continue

            if "proxy?url=" in line:
                rewritten_lines.append(line)
                continue

            # Standard transport segment chunks mapping
            absolute_url = urljoin(url, line)
            encoded_url = quote(absolute_url, safe="%")
            proxied_url = f"{TUNNEL_URL}/stream.ts?url={encoded_url}&origin={origin}"
            rewritten_lines.append(proxied_url)

        playlist_output = "\n".join(rewritten_lines)

        return Response(
            playlist_output,
            status=200,
            content_type="application/vnd.apple.mpegurl",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache",
                "Content-Length": str(len(playlist_output.encode("utf-8"))),
            },
        )

    @staticmethod
    def proxy() -> Response | tuple[dict[str, str], int]:
        try:
            url = request.args.get("url")
            origin = request.args.get("origin", "https://www.vidking.net")

            if not url:
                return {"error": "Missing url"}, 400

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": origin,
                "Origin": origin,
            }

            r = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=30,
                allow_redirects=True,
            )

            if r.status_code not in (200, 206):
                return {"error": f"Upstream status {r.status_code}"}, r.status_code

            content_type = r.headers.get("Content-Type", "application/octet-stream")

            if ".m3u8" in url.lower() or "mpegurl" in content_type.lower(): 
                return Proxy.handle_m3u8(r, url, origin)

            def generate():
                try:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk: yield chunk
                finally: 
                    r.close()

            response_headers = {"Access-Control-Allow-Origin": "*", "Accept-Ranges": "bytes"}
            content_length = r.headers.get("Content-Length")
            if content_length: 
                response_headers["Content-Length"] = content_length

            return Response(generate(), status=r.status_code, content_type=content_type, headers=response_headers)

        except Exception as e:
            logger.error(str(e))
            return {"error": str(e)}, 500