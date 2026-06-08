from app.config import TUNNEL_URL
from flask import Response, request, jsonify
from requests.exceptions import ReadTimeout, RequestException
from urllib.parse import quote, urljoin
import requests
from app.core.logger import Logger

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
    def get_proxy_url(stream_url: str, origin: str | None = None) -> str:
        """Construct the full proxy URL for a given stream URL.

        If an origin is provided, add it as a query parameter so the proxy
        can use it for Referer/Origin headers on the upstream request.
        """
        proxied_url = urljoin(TUNNEL_URL, f"/proxy?url={quote(stream_url, safe='%')}")
        if origin:
            proxied_url += f"&origin={quote(origin, safe='%')}"
        return proxied_url

    @staticmethod
    def proxy_m3u8():
        """Proxy endpoint for M3U8 playlists - ends with .m3u8 for Android compatibility"""
        return Proxy.proxy()

    @staticmethod
    def proxy_stream_ts():
        """Proxy endpoint for TS segments - ends with .ts for Android compatibility"""
        return Proxy.proxy()

    @staticmethod
    def proxy() -> Response | tuple[dict[str, str], int]:

        try:
            url = request.args.get("url")
            origin = request.args.get("origin", "https://www.vidking.net")

            if not url:
                return {"error": "Missing url"}, 400
            if not url.startswith(("http://", "https://")):
                return {"error": "Invalid URL"}, 400

            range_header = request.headers.get("Range")

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": origin,
                "Origin": origin,
            }

            if range_header:
                headers["Range"] = range_header

            try:
                r = requests.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=3,
                    allow_redirects=True,
                )
            except ReadTimeout as exc:
                logger.warning(f"Upstream read timed out for URL {url}")
                return {"error": "Upstream read timed out", "details": str(exc)}, 504
            except RequestException as exc:
                logger.warning(f"Upstream request failed for URL {url}")
                return {"error": "Upstream request failed", "details": str(exc)}, 502

            if r.status_code not in (200, 206):
                return {"error": f"Upstream server returned status {r.status_code}"}, r.status_code

            content_type = r.headers.get("Content-Type", "application/octet-stream")

            # HLS playlist handling
            if ".m3u8" in url.lower() or "mpegurl" in content_type.lower():

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

            # Video / TS streaming
            def generate():
                try:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            yield chunk
                finally:
                    r.close()

            response_headers = {"Access-Control-Allow-Origin": "*", "Accept-Ranges": "bytes"}

            content_length = r.headers.get("Content-Length")
            if content_length:
                response_headers["Content-Length"] = content_length

            return Response(generate(), status=r.status_code, content_type=content_type, headers=response_headers)

        except Exception as e:
            import traceback

            traceback.print_exc()
            return {"error": str(e)}, 500