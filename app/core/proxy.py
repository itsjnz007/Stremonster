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

    Handles HLS (.m3u8) master playlist manipulation to strip lower qualities
    while linking multi-audio demuxed tracks and streaming binary .ts segments.
    """

    @staticmethod
    def get_proxy_url(stream_url: str, origin: str | None = None) -> str:
        """Constructs the initial proxy URL wrapper for Stremio to consume.
        
        Passes the original Master URL cleanly to let the proxy filter it 
        on demand without losing audio track groupings.
        """
        proxied_url = urljoin(TUNNEL_URL, f"/proxy?url={quote(stream_url, safe='%')}")
        if origin: 
            proxied_url += f"&origin={quote(origin, safe='%')}"

        logger.info(f"Generated Proxied Endpoint: {proxied_url}")
        return proxied_url

    @staticmethod
    def proxy_m3u8() -> Response | tuple[dict[str, str], int]:
        """Proxy endpoint for M3U8 playlists - routing alias for compatibility"""
        return Proxy.proxy()

    @staticmethod
    def proxy_stream_ts() -> Response | tuple[dict[str, str], int]:
        """Proxy endpoint for TS segments - routing alias for compatibility"""
        return Proxy.proxy()
    
    @staticmethod
    def handle_m3u8(r: requests.Response, url: str, origin: str) -> Response:
        """Parses and rewrites HLS stream configurations.
        
        If it's a Master Playlist, it preserves critical audio groupings while 
        filtering out lower video quality options to speed up playback buffers.
        """
        playlist = r.text
        rewritten_lines: list[str] = []
        
        # Determine if this playlist contains multiple stream configurations
        is_master = "#EXT-X-STREAM-INF" in playlist

        if is_master:
            logger.info("Optimizing Master HLS Playlist tracks while protecting audio layers...")
            lines = playlist.splitlines()
            
            # Step 1: Scan for the maximum available video bandwidth
            max_bandwidth = 0
            for line in lines:
                line = line.strip()
                if line.startswith("#EXT-X-STREAM-INF:"):
                    bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                    if bw_match:
                        bw = int(bw_match.group(1))
                        if bw > max_bandwidth:
                            max_bandwidth = bw

            # Step 2: Reconstruct playlist keeping audio attributes and top-tier video 
            skip_next_url_line = False
            
            for raw_line in lines:
                line = raw_line.rstrip()
                if not line:
                    continue

                if skip_next_url_line:
                    skip_next_url_line = False
                    continue

                if line.startswith("#"):
                    # CRITICAL: Intercept separate audio/subtitle track streams
                    if 'URI=' in line:
                        parts = line.split('URI="')
                        if len(parts) > 1:
                            sub_uri = parts[1].split('"')[0]
                            absolute_audio_url = urljoin(url, sub_uri)
                            encoded_audio_url = quote(absolute_audio_url, safe="%")
                            proxied_audio = f"{TUNNEL_URL}/proxy?url={encoded_audio_url}&origin={origin}"
                            line = line.replace(f'URI="{sub_uri}"', f'URI="{proxied_audio}"')
                    
                    # Intercept video variants and discard entries scoring below peak bandwidth
                    if line.startswith("#EXT-X-STREAM-INF:"):
                        bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                        if bw_match and int(bw_match.group(1)) < max_bandwidth:
                            skip_next_url_line = True
                            continue
                    
                    rewritten_lines.append(line)
                    continue

                # Fallback handler for raw stream configurations
                absolute_url = urljoin(url, line)
                encoded_url = quote(absolute_url, safe="%")
                proxied_url = f"{TUNNEL_URL}/stream.ts?url={encoded_url}&origin={origin}"
                rewritten_lines.append(proxied_url)
                
        else:
            # Direct Media Playlists (Pure segment mappings for independent Audio/Video files)
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
        """Core gateway pipe routing data packages downstream to Stremio."""
        try:
            url = request.args.get("url")
            origin = request.args.get("origin", "https://www.vidking.net")

            if not url:
                logger.error("Missing URL parameter")
                return {"error": "Missing url"}, 400
                
            if not url.startswith(("http://", "https://")):
                logger.error(f"Invalid URL structure blocked: {url}")
                return {"error": "Invalid URL"}, 400

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
                upstream_body = r.text[:200]  # Grab a small sample snippet
                logger.error(f"Upstream server flatlined: status={r.status_code}, snippet={upstream_body}")
                return {"error": f"Upstream server returned status {r.status_code}"}, r.status_code

            content_type = r.headers.get("Content-Type", "application/octet-stream")

            # Route HLS file layouts through the text intercept parsing structures
            if ".m3u8" in url.lower() or "mpegurl" in content_type.lower(): 
                return Proxy.handle_m3u8(r, url, origin)

            # Route Binary Video Segment Chunks (.ts / .mp4) as a real-time system stream pipe
            def generate():
                try:
                    for chunk in r.iter_content(chunk_size=1024 * 256): # 256KB block tracking
                        if chunk: 
                            yield chunk
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
            logger.error(f"Exception triggered in Proxy Core: {str(e)}")
            return {"error": str(e)}, 500