from app.config import TUNNEL_URL
from flask import Response, request, jsonify, stream_with_context
from urllib.parse import quote, urlparse
from app.core.logger import Logger
import json, re, urllib3, logging, time, requests
from typing import Optional, Any
from app.core.caching import WebCache
from app.models.responses import WebResponse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = Logger("proxy", logging.INFO)
session = requests.Session()
web_cache = WebCache()


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
    def get_content_type(res: requests.Response) -> Optional[str]:

        # 1. Handle standard error codes
        if res.status_code not in (200, 203, 206): 
            logger.error(f"Unable to fetch content-type. Error code {res.status_code}")
            return None
            
        # 2. DETECT DEAD/EMPTY SOURCES (The fix for your issue)
        # If the server returns a 200 but explicitly says Content-Length is 0 (a ghost/dead token)
        content_length = res.headers.get('content-length')
        if content_length and int(content_length) == 0:
            logger.warning(f"Source returned 200 OK but Content-Length is 0. URL is likely dead/invalid.")
            return None

        # 3. Extract and validate Content-Type
        content_type = res.headers.get('content-type', "").lower()
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
        if res.request.url:
            if ".mp4" in res.request.url.lower():
                return "video/mp4"
            if ".m3u8" in res.request.url.lower():
                return "application/vnd.apple.mpegurl"
            if ".mpd" in res.request.url.lower():
                return "application/dash+xml"
        
        return None

    @staticmethod
    def get_proxy_url(stream: WebResponse) -> Optional[WebResponse]:
        stream['headers']["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0"
        stream['headers']["accept"] = "*/*"
        stream['headers']["accept-language"] = "en-US,en;q=0.5"
        stream['headers']["sec-fetch-dest"] = "empty"
        stream['headers']["sec-fetch-mode"] = "cors"
        stream['headers']["sec-fetch-site"] = "cross-site"

        try:
            r = session.head(stream['url'], timeout=10, headers=stream['headers'], allow_redirects=True)
        except Exception as e:
            logger.error(f"Network error while probing stream URL: {e}")
            return None

        if r.status_code not in (200, 203, 206): 
            logger.error(f"Unable to fetch content-type. Error code {r.status_code}")
            return None
        
        if not stream.get('contentType'): 
            stream['contentType'] = Proxy.get_content_type(r)
            if not stream.get('contentType'): 
                logger.error("Unable to determine content-type for proxying. Rejecting source.")
                return None
            logger.info(f"Detected content-type: {stream['contentType']}")
        stream_type = "stream.mp4" if stream['contentType'] == "video/mp4" else "stream.m3u8"

        headers_str = json.dumps(stream['headers'])
        stream['url'] = Proxy.add_proxy(stream['url'], headers_str, stream_type=stream_type)
        return stream
    
    
    @staticmethod
    def add_proxy(url: str, headers: str, id: Optional[str] = None, index: Optional[str] = None, stream_type: str = "stream.ts") -> str:

        if not TUNNEL_URL: raise Exception("TUNNEL_URL not set")

        if isinstance(headers, dict): headers_str = json.dumps(headers, separators=(",", ":"))
        else: headers_str = str(headers)

        url_str = str(url)
        proxy_url = (
            f"{TUNNEL_URL}/{stream_type}"
            + "?url=" + quote(url_str, safe="")
            + "&headers=" + quote(headers_str, safe="")
        )
        if id: proxy_url += f"&id={quote(id, safe='')}"
        if index: proxy_url +=  f"&index={quote(index, safe='')}"
        return proxy_url


    @staticmethod
    def parse_segment(content: bytes, headers: str, master_url: str, id: Optional[str], index: Optional[str]) -> str:
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
                        proxied_url = Proxy.add_proxy(full_url, headers, stream_type=stream_type, id=id, index=index)
                        return f'{match.group(1)}{proxied_url}{match.group(3)}'
                    
                    rewritten.append(uri_pattern.sub(replace_uri, line))
                else:
                    # Standard tag, no URI to proxy
                    rewritten.append(line)
            
            # Handle segment URLs (lines not starting with #)
            else:
                rewritten.append(Proxy.add_proxy(resolve_url(line), headers, stream_type=stream_type, id=id, index=index))

        return "\n".join(rewritten)
    
    @staticmethod
    def apply_headers(response: Response):
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        for header in excluded_headers:
            response.headers.pop(header, None)

        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Connection"] = "close"
        response.headers["Accept-Ranges"] = "bytes"
        return response
    
    @staticmethod
    def redirect() -> Response:
        id = request.args.get("id")
        if not id: return Response("Missing 'id' parameter", status=400)

        cache = web_cache.get(id)
        if not cache: return Response("Stream not found", status=404)

        current_index = cache.get("current_index", 0)
        streams = cache.get("streams", [])
        if not streams: return Response("No streams found", status=404)
        if len(streams[int(current_index)]) != 1:
            logger.error(f"Stream length {len(streams[int(current_index)])} is not 1. Unable to process request.")
            return Response(f"Stream length {len(streams[int(current_index)])} is not 1. Unable to process request.", status=404)
        
        current_stream = streams[int(current_index)][0]
        stream: str = current_stream.get("url") + f"&id={id}&index={current_index}:0"
        if not stream: return Response("Stream URL not found", status=404)

        logger.info(f"Redirecting to proxied stream URL: {stream}")
        return Response(status=302, headers={"Location": stream})

    @staticmethod
    def proxy(content_type: Optional[str] = None) -> Response:
        # try:
        start_time = time.time()

        # Proxy arguments
        media_url = request.args.get("url")
        if not media_url: raise Exception("No media_url found")
        id = request.args.get("id")
        index = request.args.get("index")
        media_headers = request.args.get("headers", "{}")
        if not media_headers: raise Exception("No media_headers found")
        logger.debug(f"id {id} | index {index}\n{'-'*10}\nmedia_url {media_url}\n{'-'*10}\nmedia_headers {media_headers}")

        # Request arguments
        request_headers = dict(request.headers)
        logger.debug(f"request_headers: {request_headers}")

        try: arg_headers = json.loads(media_headers)
        except Exception as e: return Response(f"Unable to parse headers_str. Error: {e}", status=503)
        logger.debug(f"arg_headers: {arg_headers}")

        if "Range" in request_headers: arg_headers['Range'] = request_headers['Range']

        try:
            if request.method == "POST":
                upstream_response = session.post(
                    media_url,
                    timeout=(5, 30),
                    headers=arg_headers,
                    stream=True,
                    verify=False,
                    allow_redirects=True,
                )
            else:
                upstream_response = session.get(
                    media_url,
                    timeout=(5, 30),
                    headers=arg_headers,
                    stream=True,
                    verify=False,
                    allow_redirects=True,
                )
        except Exception as e: 
            logger.error(f"Proxy upstream error, {e}")
            if id: 
                web_cache.switch_source(id)
            else: logger.warning("'request_id' not available, skipping source switch")
            return Response(f"Upstream error {e}", status=503) 
        
        if upstream_response.status_code not in (200, 203, 206):
            logger.error(f"Upstream error [{upstream_response.status_code}] {upstream_response.text}")
            if id:
                web_cache.switch_source(id)
            else: logger.warning("'request_id' not available, skipping source switch")
            return Response(f"Upstream error {upstream_response.text}", status=503)

        if not content_type: content_type = upstream_response.headers.get("content-type", "").lower()

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
                media_url,
                id=id,
                index=index
            )
            resp = Response(
                updated_content,
                status=upstream_response.status_code,
                mimetype=content_type,
                headers=upstream_response.headers,
            )
            logger.info(f"{upstream_response.status_code} | {time.time() - start_time}ms | Parsing m3u8 {request.url}")
            return Proxy.apply_headers(resp)
        
        if id and index:
            web_res = web_cache.get(id)
            if web_res:
                current_index = int(web_res.get('current_index'))
                source_index = int(index.split(':')[0])
                logger.debug(f"current_index: {current_index} | source_index: {source_index}")
                if current_index != source_index:
                    logger.error("Returning failure to reload webpage.")
                    return Response("Returning failure to reload webpage.", status=503)
        
        def generate_media():
            try:
                start = time.monotonic()
                bytes_read = 0

                for chunk in upstream_response.iter_content(64 * 1024):
                    if not chunk:
                        continue

                    bytes_read += len(chunk)
                    elapsed = time.monotonic() - start

                    if elapsed > 10 and bytes_read / elapsed < 100 * 1024:  # <100 KB/s
                        if id:
                            web_cache.switch_source(id)
                        else: logger.warning("'request_id' not available, skipping source switch")
                        break

                    yield chunk
            finally: upstream_response.close()

        resp = Response(
            stream_with_context(generate_media()), 
            status=upstream_response.status_code,
            content_type=content_type,
            headers=upstream_response.headers,
        )

        logger.info(f"{upstream_response.status_code} | {time.time() - start_time}ms | Proxying url {request.url}")
        return Proxy.apply_headers(resp)
        # except Exception as e: 
        #     logger.error(f"Proxy error, {e}")
        #     return Response(f"Proxy error: {e}")
        # finally:
        #     pass
