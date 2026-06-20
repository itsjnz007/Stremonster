from app.config import TUNNEL_URL
from flask import Response, request, jsonify, stream_with_context
from urllib.parse import quote, urlparse
import requests
from app.core.logger import Logger
from typing import Any
import json, re, urllib3
from typing import Optional
from requests.cookies import RequestsCookieJar

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# from requests.adapters import HTTPAdapter
# from urllib3.util.retry import Retry

# --- Add this setup block ---
logger = Logger("proxy")
session = requests.Session()

# # Configure retry strategy
# retry_strategy = Retry(
#     total=3,  # Total number of retries
#     backoff_factor=0.5,  # Wait 0.5s, 1s, 2s between retries
#     status_forcelist=[500, 502, 503, 504, 403],  # Retry on these status codes
#     allowed_methods=["GET", "POST"]
# )

# adapter = HTTPAdapter(max_retries=retry_strategy)
# session.mount("http://", adapter)
# session.mount("https://", adapter)
# ----------------------------

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
    # @staticmethod
    # def is_valid(stream_url: str) -> bool:
    #     try:
    #         response = requests.head(stream_url, timeout=10, allow_redirects=True)
    #         if response.status_code in [200, 203, 206]: return True 
    #     except Exception as e:
    #         logger.error(f"Error checking URL validity. Error: {e}")

    #     return False

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
    def get_stream_type(stream_url: str, origin: str):
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.5",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "origin": origin,
            "referer": f"{origin}/"
        }

        r = session.head(stream_url, headers=headers, timeout=10, stream=True)

        if r.status_code in (200, 203, 206): 
            content_type = r.headers.get('Content-Type')
            if content_type: 
                if content_type in ("mpegurl", "application/vnd.apple.mpegurl", "video/mp2t", "video/mp4"): return content_type
        else: logger.error(f"Unable to fetch content-type. Error code {r.status_code}. ")
        
        if ".mp4" in stream_url: return "video/mp4"
        if ".m3u8" in stream_url: return "mpegurl"
        
        logger.error("Content-type unavailable in the obtained header. Returning default type.")
        return "mpegurl"

    @staticmethod
    def get_proxy_url(stream_url: str, origin: str, content_type: Optional[str] = None, cookies: Optional[dict[str, str] | RequestsCookieJar] = None) -> str:

        if not content_type: content_type = Proxy.get_stream_type(stream_url=stream_url, origin=origin)
        stream_type = "stream.mp4" if content_type == "video/mp4" else "stream.m3u8"

        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.5",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "origin": origin,
            "referer": f"{origin}/",
            "content-type": content_type
        }

        if cookies:
            if isinstance(cookies, RequestsCookieJar):
                cookie_header = "; ".join(
                    f"{c.name}={c.value}" for c in cookies
                )
            else:
                cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())

            headers["cookie"] = cookie_header

        headers_str = json.dumps(headers)

        proxied_url = Proxy.add_proxy(stream_url, headers_str, stream_type)
        return proxied_url

    # @staticmethod
    # def proxy_m3u8() -> Response | tuple[dict[str, str], int]:
    #     """Proxy endpoint for M3U8 playlists"""
    #     return Proxy.proxy()

    # @staticmethod
    # def proxy_stream_ts() -> Response | tuple[dict[str, str], int]:
    #     """Proxy endpoint for TS segments"""
    #     return Proxy.proxy()
    
    # @staticmethod
    # def proxy_stream_mp4() -> Response | tuple[dict[str, str], int]:
    #     """Proxy endpoint for mp4 url"""
    #     return Proxy.proxy()
    
    @staticmethod
    def add_proxy(url: str, headers: str, stream_type: str = "stream.ts") -> str:

        if not TUNNEL_URL: raise Exception("TUNNEL_URL not set")

        if isinstance(headers, dict): headers_str = json.dumps(headers, separators=(",", ":"))
        else: headers_str = str(headers)

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
        response.headers["Accept-Ranges"] = "bytes"
        return response
    
    @staticmethod
    def proxy() -> Response:
        try:
            logger.debug(f"Proxying: {request.url}")
            media_url = request.args.get("url")
            if not media_url: raise Exception("No media_url found")

            headers_str = request.args.get("headers", "{}")
            try: headers = json.loads(headers_str)
            except Exception as e: return Response(f"Unable to parse headers_str. Error: {e}", status=503)

            try:
                if request.method == "POST":
                    upstream_response = session.post(
                        media_url,
                        timeout=30,
                        headers=headers,
                        stream=True,
                        cookies=request.cookies,
                        verify=False
                    )
                else:
                    upstream_response = session.get(
                        media_url,
                        timeout=30,
                        headers=headers,
                        stream=True,
                        cookies=request.cookies,
                        verify=False
                    )
            except Exception as e: 
                logger.error(f"Proxy upstream error, {e}")
                return Response(f"Upstream error {e}", status=503)

            content_type = upstream_response.headers.get("content-type", "").lower()

            is_m3u8 = (
                ".m3u8" in media_url
                or "mpegurl" in content_type
            )

            if is_m3u8 and upstream_response.status_code in (200, 203, 206):

                content = upstream_response.content

                updated_content = Proxy.parse_segment(
                    content,
                    headers,
                    media_url
                )

                resp = Response(
                    updated_content,
                    status=upstream_response.status_code,
                    mimetype="mpegurl"
                )
                return Proxy.apply_header(resp)
            
            def generate_media():
                for chunk in upstream_response.iter_content(chunk_size=1024*64):
                    if chunk: yield chunk

            resp = Response(
                stream_with_context(generate_media()), 
                status=upstream_response.status_code,
                mimetype=headers.get("content-type", "video/mp2t")
            )
            return Proxy.apply_header(resp)
        except Exception as e: 
            logger.error(f"Proxy error, {e}")
            return Response(f"Proxy error: {e}")
        finally:
            pass