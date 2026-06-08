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
    """Collection of proxy-related helpers exposed as static methods.

    Use `Proxy.get_proxy_url(...)` to generate proxied links and
    `Proxy.proxy`, `Proxy.proxy_m3u8`, `Proxy.proxy_stream_ts` as
    Flask route handlers.
    """

    @staticmethod
    def get_best_stream(stream_url: str, origin: Optional[str] = None):
        """
        Checks if a URL is an HLS Master Playlist. If it is, parses the available 
        qualities, selects the one with the highest bandwidth/resolution, 
        and returns its absolute URL. Otherwise, returns the original URL.
        """
        if ".m3u8" not in stream_url.lower():
            logger.warning(f"[Stream Resolver] Not an M3U8 link. Returning original URL.")
            return stream_url

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        if origin:
            headers['Origin'] = origin
            headers['Referer'] = origin + '/'

        try:
            response = requests.get(stream_url, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to fetch playlist (Status: {response.status_code}). Using original.")
                return stream_url
            
            content = response.text

            # A Master Playlist MUST contain variant streams, typically tagged with #EXT-X-STREAM-INF
            if "#EXT-X-STREAM-INF" not in content:
                logger.info(f"Detected a direct Media Playlist (no sub-qualities). Using original URL.")
                return stream_url

            logger.info(f"\n\n--- Parsing HLS Master Playlist Qualities ---")
            
            lines = content.splitlines()
            streams: List[Dict[str, Any]]= []
            
            current_meta = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Capture the metadata line containing BANDWIDTH and RESOLUTION
                if line.startswith("#EXT-X-STREAM-INF:"):
                    current_meta = line
                elif current_meta and not line.startswith("#"):
                    # This line is the URL/relative path corresponding to the metadata above
                    bandwidth = 0
                    resolution = "Unknown"
                    
                    # Extract BANDWIDTH using regex
                    bw_match = re.search(r'BANDWIDTH=(\d+)', current_meta)
                    if bw_match:
                        bandwidth = int(bw_match.group(1))
                        
                    # Extract RESOLUTION using regex if available
                    res_match = re.search(r'RESOLUTION=(\d+x\d+)', current_meta)
                    if res_match:
                        resolution = res_match.group(1)
                    
                    # Convert relative variant URLs to full absolute URLs
                    absolute_variant_url = urljoin(stream_url, line)
                    
                    streams.append({
                        'bandwidth': bandwidth,
                        'resolution': resolution,
                        'url': absolute_variant_url
                    })
                    current_meta = None # Reset for next stream

            if not streams:
                logger.error("Failed to parse any valid streams. Using original URL.")
                return stream_url

            # Sort streams: Highest bandwidth and highest resolution first
            streams.sort(key=lambda x: (x['bandwidth'], x['resolution']), reverse=True) # type: ignore

            # Log all discovered qualities
            print(f"{'INDEX':<6} | {'RESOLUTION':<12} | {'BANDWIDTH (Mbps)':<18}")
            print("-" * 45)
            for idx, stream in enumerate(streams):
                mbps = stream['bandwidth'] / 1_000_000
                print(f"{idx:<6} | {stream['resolution']:<12} | {mbps:<18.2f}")

            # Pick the best one
            best_stream = streams[0]
            print(f"\n[Selection] -> Chosen Quality: {best_stream['resolution']} ({best_stream['bandwidth'] / 1_000_000:.2f} Mbps)")
            print(f"[Selection] -> Target URL: {best_stream['url']}\n")
            
            return best_stream['url']

        except Exception as e:
            print(f"[Stream Resolver] Error analyzing playlist: {e}. Falling back to original URL.")
            return stream_url

    @staticmethod
    def get_proxy_url(stream_url: str, origin: str | None = None) -> str:
        """Construct the full proxy URL for a given stream URL.

        If an origin is provided, add it as a query parameter so the proxy
        can use it for Referer/Origin headers on the upstream request.
        """
        proxied_url = urljoin(TUNNEL_URL, f"/proxy?url={quote(stream_url, safe='%')}")
        if origin: proxied_url += f"&origin={quote(origin, safe='%')}"

        best_url = Proxy.get_best_stream(proxied_url, origin)
        logger.info(f"Best stream {best_url}")

        return best_url

    @staticmethod
    def proxy_m3u8():
        """Proxy endpoint for M3U8 playlists - ends with .m3u8 for Android compatibility"""
        return Proxy.proxy()

    @staticmethod
    def proxy_stream_ts():
        """Proxy endpoint for TS segments - ends with .ts for Android compatibility"""
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

            if line.startswith("#"):
                rewritten_lines.append(line)
                continue

            if "proxy?url=" in line:
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

        try:
            url = request.args.get("url")
            origin = request.args.get("origin", "https://www.vidking.net")

            if not url:
                logger.error("Missing URL")
                return {"error": "Missing url"}, 400
            if not url.startswith(("http://", "https://")):
                logger.error("Invalid URL")
                return {"error": "Invalid URL"}, 400

            headers = {
                "User-Agent": "Mozilla/5.0",
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
                upstream_body = r.text
                upstream_json = None

                try: upstream_json = r.json()
                except ValueError: pass

                logger.error(
                    "Upstream error for URL!"
                    f"\nstatus={r.status_code}"
                    f"\nbody={upstream_body}"
                    f"\njson={upstream_json}"
                )
                return {"error": f"Upstream server returned status {r.status_code}"}, r.status_code

            content_type = r.headers.get("Content-Type", "application/octet-stream")

            # HLS playlist handling
            if ".m3u8" in url.lower() or "mpegurl" in content_type.lower(): return Proxy.handle_m3u8(r, url, origin)

            # Video / TS streaming
            def generate():
                try:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk: yield chunk
                finally: r.close()

            response_headers = {"Access-Control-Allow-Origin": "*", "Accept-Ranges": "bytes"}
            content_length = r.headers.get("Content-Length")
            if content_length: response_headers["Content-Length"] = content_length

            return Response(generate(), status=r.status_code, content_type=content_type, headers=response_headers)

        except Exception as e:
            logger.error(str(e))
            return {"error": str(e)}, 500