from app.config import TUNNEL_URL
from flask import Response, request, jsonify
from urllib.parse import quote, urljoin, urlparse
import requests
import re
from app.core.logger import Logger
from typing import Any

logger = Logger("proxy")

def respond_with(data: dict[str, Any]) -> Response:
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    return resp


class Proxy:
    """Collection of proxy-related helpers optimized for streaming compatibility."""

    @staticmethod
    def get_proxy_url(stream_url: str, origin: str | None = None, type: str = "stream.m3u8") -> str:
        proxied_url = urljoin(TUNNEL_URL, f"/{type}?url={quote(stream_url, safe='%')}")
        if origin: 
            proxied_url += f"&origin={quote(origin, safe='%')}"
        logger.debug(f"Generated Proxied Endpoint: {proxied_url}")
        return proxied_url

    @staticmethod
    def proxy_m3u8() -> Response | tuple[dict[str, str], int]:
        return Proxy.proxy()

    @staticmethod
    def proxy_stream_ts() -> Response | tuple[dict[str, str], int]:
        return Proxy.proxy()
    
    @staticmethod
    def handle_m3u8(r: requests.Response, url: str, origin: str) -> Response:
        playlist = r.text
        rewritten_lines: list[str] = []
        is_master = "#EXT-X-STREAM-INF" in playlist

        if is_master:
            lines = playlist.splitlines()
            max_bandwidth = 0
            for line in lines:
                if "#EXT-X-STREAM-INF:" in line:
                    bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                    if bw_match: max_bandwidth = max(max_bandwidth, int(bw_match.group(1)))

            skip_next = False
            for raw_line in lines:
                line = raw_line.rstrip()
                if not line: continue
                if skip_next:
                    skip_next = False
                    continue
                if line.startswith("#"):
                    if 'URI=' in line:
                        sub_uri = re.search(r'URI="([^"]+)"', line)
                        if sub_uri:
                            abs_url = urljoin(url, sub_uri.group(1))
                            proxied_audio = f"{TUNNEL_URL}/stream.m3u8?url={quote(abs_url, safe='%')}&origin={origin}"
                            line = line.replace(sub_uri.group(1), proxied_audio)
                    if "#EXT-X-STREAM-INF:" in line:
                        bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                        if bw_match and int(bw_match.group(1)) < max_bandwidth:
                            skip_next = True
                            continue
                    rewritten_lines.append(line)
                    continue
                proxied_url = f"{TUNNEL_URL}/stream.m3u8?url={quote(urljoin(url, line), safe='%')}&origin={origin}"
                rewritten_lines.append(proxied_url)
        else:
            for raw_line in playlist.splitlines():
                line = raw_line.rstrip()
                if not line: rewritten_lines.append(""); continue
                if line.startswith("#"): rewritten_lines.append(line); continue
                proxied_url = f"{TUNNEL_URL}/stream.ts?url={quote(urljoin(url, line), safe='%')}&origin={origin}"
                rewritten_lines.append(proxied_url)

        return Response(
            "\n".join(rewritten_lines),
            status=200,
            content_type="application/vnd.apple.mpegurl",
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"}
        )

    @staticmethod
    def proxy() -> Response | tuple[dict[str, str], int]:
        try:
            url = request.args.get("url")
            if not url: return {"error": "Missing url"}, 400

            # DYNAMIC SPOOFING: Use the target domain for Origin/Referer to bypass 403s
            parsed = urlparse(url)
            target_origin = f"{parsed.scheme}://{parsed.netloc}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": f"{target_origin}/",
                "Origin": target_origin,
            }

            r = requests.get(url, headers=headers, stream=True, timeout=(10, 60), allow_redirects=True)
            logger.info(f"Upstream: {r.status_code} | Type: {r.headers.get('Content-Type')} | URL: {url}")

            if r.status_code not in (200, 206):
                return {"error": f"Upstream status {r.status_code}"}, r.status_code

            # FORCE MIME TYPES: Ignore upstream claims and force video types for our routes
            if "stream.ts" in request.path:
                content_type = "video/mp2t"
            elif "stream.m3u8" in request.path or ".m3u8" in url.lower():
                return Proxy.handle_m3u8(r, url, request.args.get("origin", target_origin))
            else:
                content_type = r.headers.get("Content-Type", "application/octet-stream")

            # CLEAN HEADERS: Strip security headers that block proxying
            excluded = ['content-encoding', 'content-length', 'x-content-type-options', 'access-control-allow-origin']
            resp_headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Accept-Ranges": "bytes",
                "Content-Type": content_type
            }
            for k, v in r.headers.items():
                if k.lower() not in excluded: resp_headers[k] = v

            def generate():
                try:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk: yield chunk
                finally: r.close()

            return Response(generate(), status=r.status_code, headers=resp_headers)

        except Exception as e:
            logger.error(f"Proxy Error: {str(e)}")
            return {"error": str(e)}, 500