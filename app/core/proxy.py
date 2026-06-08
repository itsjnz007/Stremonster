from app.config import TUNNEL_URL
from flask import Response, request, jsonify
from urllib.parse import quote, urljoin
import requests
import re
from app.core.logger import Logger

logger = Logger("proxy")

def respond_with(data: dict[str, object]) -> Response:
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    return resp


class Proxy:
    """Collection of proxy-related helpers exposed as static methods.

    Optimized for Android ExoPlayer compatibility by preserving clean explicit 
    extensions and handling precise mime-types.
    """

    @staticmethod
    def get_proxy_url(stream_url: str, origin: str | None = None) -> str:
        """Constructs the initial proxy URL wrapper for Stremio to consume.
        
        Uses /stream.m3u8 directly to force Android ExoPlayer into HLS mode.
        """
        # CRITICAL CHANGE: Route explicitly through /stream.m3u8 so Android detects the format
        proxied_url = urljoin(TUNNEL_URL, f"/stream.m3u8?url={quote(stream_url, safe='%')}")
        if origin: 
            proxied_url += f"&origin={quote(origin, safe='%')}"

        logger.debug(f"Generated Proxied Endpoint: {proxied_url}")
        return proxied_url

    @staticmethod
    def proxy_m3u8() -> Response | tuple[dict[str, str], int]:
        """Proxy endpoint for M3U8 playlists"""
        return Proxy.proxy()

    @staticmethod
    def proxy_stream_ts() -> Response | tuple[dict[str, str], int]:
        """Proxy endpoint for TS segments"""
        return Proxy.proxy()
    
    @staticmethod
    def handle_m3u8(r: requests.Response, url: str, origin: str) -> Response:
        """Parses and rewrites HLS stream configurations safely for Android frameworks."""
        playlist = r.text
        rewritten_lines: list[str] = []
        
        is_master = "#EXT-X-STREAM-INF" in playlist

        if is_master:
            logger.info("Optimizing Master HLS Playlist tracks while protecting audio layers...")
            lines = playlist.splitlines()
            
            # Scan for the maximum available video bandwidth
            max_bandwidth = 0
            for line in lines:
                line = line.strip()
                if line.startswith("#EXT-X-STREAM-INF:"):
                    bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                    if bw_match:
                        bw = int(bw_match.group(1))
                        if bw > max_bandwidth:
                            max_bandwidth = bw

            skip_next_url_line = False
            
            for raw_line in lines:
                line = raw_line.rstrip()
                if not line:
                    continue

                if skip_next_url_line:
                    skip_next_url_line = False
                    continue

                if line.startswith("#"):
                    # Intercept separate audio/subtitle track streams
                    if 'URI=' in line:
                        parts = line.split('URI="')
                        if len(parts) > 1:
                            sub_uri = parts[1].split('"')[0]
                            absolute_audio_url = urljoin(url, sub_uri)
                            encoded_audio_url = quote(absolute_audio_url, safe="%")
                            # CRITICAL: Re-route sub-playlists through /stream.m3u8 explicitly
                            proxied_audio = f"{TUNNEL_URL}/stream.m3u8?url={encoded_audio_url}&origin={origin}"
                            line = line.replace(f'URI="{sub_uri}"', f'URI="{proxied_audio}"')
                    
                    if line.startswith("#EXT-X-STREAM-INF:"):
                        bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                        if bw_match and int(bw_match.group(1)) < max_bandwidth:
                            skip_next_url_line = True
                            continue
                    
                    rewritten_lines.append(line)
                    continue

                # Video Variant line rewrite
                absolute_url = urljoin(url, line)
                encoded_url = quote(absolute_url, safe="%")
                proxied_url = f"{TUNNEL_URL}/stream.m3u8?url={encoded_url}&origin={origin}"
                rewritten_lines.append(proxied_url)
                
        else:
            # Direct Media Playlists (Pure segment chunks mapping)
            for raw_line in playlist.splitlines():
                line = raw_line.rstrip()
                if not line:
                    rewritten_lines.append("")
                    continue

                if line.startswith("#"):
                    rewritten_lines.append(line)
                    continue

                absolute_url = urljoin(url, line)
                encoded_url = quote(absolute_url, safe="%")
                # CRITICAL: Route video segments to /stream.ts to force Android's TsExtractor
                proxied_url = f"{TUNNEL_URL}/stream.ts?url={encoded_url}&origin={origin}"
                rewritten_lines.append(proxied_url)

        playlist_output = "\n".join(rewritten_lines)

        # Android demands strict HLS mime-types
        return Response(
            playlist_output,
            status=200,
            content_type="application/vnd.apple.mpegurl",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
                "Content-Length": str(len(playlist_output.encode("utf-8"))),
            },
        )

    @staticmethod
    def proxy() -> Response | tuple[dict[str, str], int]:
        """Core gateway pipe routing data packages downstream to Stremio."""
        try:
            url = request.args.get("url")
            origin = request.args.get("origin", "https://www.vidking.net")

            if not url:
                return {"error": "Missing url"}, 400

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": origin + '/',
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

            # Resolve Content-Type based on the request path
            # (Enforces compatibility when upstream servers send unhelpful generic content types)
            path_lower = request.path.lower()
            if "stream.m3u8" in path_lower or ".m3u8" in url.lower():
                return Proxy.handle_m3u8(r, url, origin)
            elif "stream.ts" in path_lower:
                content_type = "video/mp2t"  # Force explicit MPEG-TS mimetype for ExoPlayer
            else:
                content_type = r.headers.get("Content-Type", "application/octet-stream")

            def generate():
                try:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk: yield chunk
                finally: 
                    r.close()

            response_headers = {
                "Access-Control-Allow-Origin": "*", 
                "Accept-Ranges": "bytes"
            }
            content_length = r.headers.get("Content-Length")
            if content_length: 
                response_headers["Content-Length"] = content_length

            return Response(
                generate(), 
                status=r.status_code, 
                content_type=content_type, 
                headers=response_headers
            )

        except Exception as e:
            logger.error(str(e))
            return {"error": str(e)}, 500