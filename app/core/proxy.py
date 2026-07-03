from app.config import TUNNEL_URL
from flask import Response, request, jsonify, stream_with_context
from urllib.parse import quote, urlparse
from app.core.logger import Logger
import json, re, urllib3, logging, time, requests
from typing import Optional, Any
from requests.cookies import RequestsCookieJar

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = Logger("proxy", logging.INFO)
session = requests.Session()


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

    # @staticmethod
    # def get_external_proxy_url(stream_url: str, origin: str) -> str:
    #     if 'proxy' in stream_url: return stream_url
    #     headers = {
    #         "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    #         "accept": "*/*",
    #         "accept-language": "en-US,en;q=0.5",
    #         "sec-fetch-dest": "empty",
    #         "sec-fetch-mode": "cors",
    #         "sec-fetch-site": "cross-site",
    #         "origin": origin,
    #         "referer": origin.rstrip("/") + "/"
    #     }

    #     encoded_url = quote(stream_url, safe="")
    #     encoded_headers = quote(
    #         json.dumps(headers, separators=(",", ":")),
    #         safe=""
    #     )

    #     return (
    #         "https://megacloud.animanga.fun/proxy"
    #         f"?url={encoded_url}&headers={encoded_headers}"
    #     )
    


    @staticmethod
    def get_stream_type(stream_url: str, origin: str = "https://web.stremio.com") -> Optional[str]:
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

        try:
            r = session.head(stream_url, headers=headers, timeout=10, allow_redirects=True)
        except Exception as e:
            logger.error(f"Network error while probing stream URL: {e}")
            return None

        # 1. Handle standard error codes
        if r.status_code not in (200, 203, 206): 
            logger.error(f"Unable to fetch content-type. Error code {r.status_code} {r.text}")
            return None
            
        # 2. DETECT DEAD/EMPTY SOURCES (The fix for your issue)
        # If the server returns a 200 but explicitly says Content-Length is 0 (a ghost/dead token)
        content_length = r.headers.get('content-length')
        if content_length and int(content_length) == 0:
            logger.warning(f"Source returned 200 OK but Content-Length is 0. URL is likely dead/invalid: {stream_url}")
            return None

        # 3. Extract and validate Content-Type
        content_type = r.headers.get('content-type', "").lower()
        if content_type:
            if "mpegurl" in content_type or "apple.mpegurl" in content_type:
                return "application/vnd.apple.mpegurl"
            elif "dash+xml" in content_type:
                return "application/dash+xml"
            elif "mp4" in content_type:
                return "video/mp4"
            elif "mp2t" in content_type:
                return "video/mp2t"

        # 4. Fallback to URL extension parsing if Content-Type is vague
        if ".mp4" in stream_url.lower(): 
            return "video/mp4"
        if ".m3u8" in stream_url.lower(): 
            return "application/vnd.apple.mpegurl"
        if ".mpd" in stream_url.lower(): 
            return "application/dash+xml"
        
        logger.error("Content-type unavailable or unrecognized. Rejecting source.")
        return None

    @staticmethod
    def get_proxy_url(stream_url: str, origin: str, content_type: Optional[str] = None, cookies: Optional[dict[str, str] | RequestsCookieJar] = None) -> Optional[str]:

        if not content_type: 
            content_type = Proxy.get_stream_type(stream_url=stream_url, origin=origin)
            if not content_type: 
                logger.error("Unable to determine content-type for proxying. Rejecting source.")
                return
            logger.info(f"Detected content-type: {content_type}")
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
            # "content-type": content_type
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
    def apply_headers(response: Response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Connection"] = "close"
        response.headers["Accept-Ranges"] = "bytes"
        return response
    
    @staticmethod
    def proxy() -> Response:
        try:
            start_time = time.time()

            media_url = request.args.get("url")
            if not media_url: raise Exception("No media_url found")
            logger.debug(f"media_url: {media_url}")

            request_headers = dict(request.headers)
            logger.debug(f"request_headers: {request_headers}")

            arg_headers_str = request.args.get("headers", "{}")
            
            try: arg_headers = json.loads(arg_headers_str)
            except Exception as e: return Response(f"Unable to parse headers_str. Error: {e}", status=503)
            logger.debug(f"arg_headers: {arg_headers}")

            if "Range" in request_headers: arg_headers['Range'] = request_headers['Range']

            try:
                if request.method == "POST":
                    upstream_response = session.post(
                        media_url,
                        timeout=30,
                        headers=arg_headers,
                        stream=True,
                        # cookies=request.cookies,
                        verify=False
                    )
                else:
                    upstream_response = session.get(
                        media_url,
                        timeout=30,
                        headers=arg_headers,
                        stream=True,
                        # cookies=request.cookies,
                        verify=False
                    )
            except Exception as e: 
                logger.error(f"Proxy upstream error, {e}")
                return Response(f"Upstream error {e}", status=503)
            
            if upstream_response.status_code not in (200, 203, 206):
                logger.error(f"Upstream error {upstream_response.status_code} {upstream_response.text}")

            content_type = upstream_response.headers.get("content-type", "").lower()

            is_m3u8 = (
                ".m3u8" in media_url
                or "mpegurl" in content_type
                or "application/vnd.apple.mpegurl" in content_type
            )

            if is_m3u8 and upstream_response.status_code in (200, 203, 206):

                content = upstream_response.content

                updated_content = Proxy.parse_segment(
                    content,
                    arg_headers,
                    media_url
                )

                resp = Response(
                    updated_content,
                    status=upstream_response.status_code,
                    mimetype=content_type
                )
                # upstream_response.close()
                logger.info(f"{upstream_response.status_code} | {time.time() - start_time}ms | Parsing m3u8 {request.url}")
                return Proxy.apply_headers(resp)
            
            def generate_media():
                for chunk in upstream_response.iter_content(chunk_size=1024*64):
                    if chunk: yield chunk

            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = {k: v for k, v in upstream_response.headers.items() if k.lower() not in excluded_headers}

            resp = Response(
                stream_with_context(generate_media()), 
                status=upstream_response.status_code,
                content_type=content_type,
                headers=headers
            )

            # upstream_response.close()
            logger.info(f"{upstream_response.status_code} | {time.time() - start_time}ms | Proxying url {request.url}")
            return Proxy.apply_headers(resp)
        except Exception as e: 
            logger.error(f"Proxy error, {e}")
            return Response(f"Proxy error: {e}")
        finally:
            pass