from app.config import TUNNEL_URL
from flask import Response, request, jsonify
from urllib.parse import quote, urlparse
import requests
from app.core.logger import Logger
from typing import Any
import json, re
from typing import Optional, Iterable

logger = Logger("proxy")
# session = requests.Session()
# session.headers.update({"Connection": "close"})

def respond_with(data: dict[str, Any]) -> Response:
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
    def get_external_proxy_url(stream_url: str, origin: str) -> str:
        if 'proxy' in stream_url: return stream_url
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.5",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "origin": origin,
            "referer": origin.rstrip("/") + "/"
        }

        encoded_url = quote(stream_url, safe="")
        encoded_headers = quote(
            json.dumps(headers, separators=(",", ":")),
            safe=""
        )

        return (
            "https://megacloud.animanga.fun/proxy"
            f"?url={encoded_url}&headers={encoded_headers}"
        )

    @staticmethod
    def get_proxy_url(stream_url: str, origin: str, type: str = "stream.m3u8") -> str:
        # if 'proxy' in stream_url: return stream_url
        # proxied_url = urljoin(TUNNEL_URL, f"/{type}?url={quote(stream_url, safe='%')}") # type: ignore
        # proxied_url += f"&origin={quote(origin, safe='%')}"
        headers_str = """{"ffuser-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.5",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "origin": "%s",
            "referer": "%s/"
        }"""

        # logger.debug(f"Generated Proxied Endpoint: {proxied_url}")
        proxied_url = Proxy.add_proxy(stream_url, headers_str % (origin, origin), type)
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
    def add_proxy(url: str, headers: str, stream_type: str = "stream.ts") -> str:

        if not TUNNEL_URL:
            raise Exception("TUNNEL_URL not set")

        # --- normalize headers ---
        if isinstance(headers, dict):
            headers_str = json.dumps(headers, separators=(",", ":"))
        else:
            headers_str = str(headers)

        # --- normalize url ---
        url_str = str(url)

        return (
            f"{TUNNEL_URL}/{stream_type}"
            + "?url=" + quote(url_str, safe="")
            + "&headers=" + quote(headers_str, safe="")
        )


    @staticmethod
    def parse_segment(content: bytes, headers: str, master_url: str) -> str:
        text = content.decode("utf-8", errors="ignore")
        rewritten: list[str] = []

        parsed = urlparse(master_url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        base_path = "/".join(parsed.path.split("/")[:-1])

        is_master = "#EXT-X-STREAM-INF" in text
        stream_type = "stream.m3u8" if is_master else "stream.ts"

        def resolve_url(url: str) -> str:
            """Converts relative URLs to absolute."""
            if url.startswith("http"):
                return url
            elif url.startswith("/"):
                return host + url
            else:
                return f"{host}{base_path}/{url}"

        # Regex to find URI="..." inside tags
        uri_pattern = re.compile(r'(URI=["\'])(.*?)(["\'])')

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                rewritten.append("")
                continue

            # Handle tags that might contain URIs
            if line.startswith("#"):
                if 'URI=' in line:
                    # Replace the URI inside the tag with the proxied version
                    def replace_uri(match: re.Match[str]):
                        full_url = resolve_url(match.group(2))
                        proxied_url = Proxy.add_proxy(full_url, headers, stream_type)
                        return f'{match.group(1)}{proxied_url}{match.group(3)}'
                    
                    rewritten.append(uri_pattern.sub(replace_uri, line))
                else:
                    # Standard tag, no URI to proxy
                    rewritten.append(line)
            
            # Handle segment URLs (lines not starting with #)
            else:
                rewritten.append(Proxy.add_proxy(resolve_url(line), headers, stream_type))

        return "\n".join(rewritten)
    
    @staticmethod
    def apply_header(response: Response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "close"
        return response
    
    @staticmethod
    def proxy():
        response: Optional[requests.Response] = None

        try:
            media_url = request.args.get("url")
            if not media_url: raise Exception("No media_url found")

            headers_str = request.args.get("headers", "{}")
            try: headers = json.loads(headers_str)
            except Exception as e: return Response(f"Unable to parse headers_str. Error: {e}", status=503)

            try:
                if request.method == "POST":
                    response = requests.post(
                        media_url,
                        timeout=10,
                        headers=headers,
                        stream=True,
                        cookies=request.cookies
                    )
                else:
                    response = requests.get(
                        media_url,
                        timeout=10,
                        headers=headers,
                        stream=True,
                        cookies=request.cookies
                    )
            except Exception as e: return Response(f"Upstream error {e}", status=503)

            content_type = response.headers.get("content-type", "").lower()

            is_m3u8 = (
                ".m3u8" in media_url
                or "mpegurl" in content_type
            )

            if is_m3u8 and response.status_code in (200, 206):

                content = response.content

                updated_content = Proxy.parse_segment(
                    content,
                    headers,
                    media_url
                )

                resp = Response(
                    updated_content,
                    status=response.status_code,
                    mimetype="application/vnd.apple.mpegurl"
                )

                return Proxy.apply_header(resp)

            def generate() -> Iterable[bytes]:
                if response:
                    try: yield from response.iter_content(chunk_size=8192)
                    finally: response.close()
                else: return Response("Missing response", status=503)

            resp = Response(generate(), status=response.status_code)
            return Proxy.apply_header(resp)
        
        finally:
            try:
                if response: response.close()
                response = None
            except: pass