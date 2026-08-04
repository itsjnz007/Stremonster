from app.config import TUNNEL_URL
from flask import Response, request, jsonify, stream_with_context
from urllib.parse import quote, urlparse
from app.core.logger import Logger
import json, re, urllib3, logging, time, requests, pycurl
from typing import Optional, Any
from app.core.caching import WebCache
from app.models.responses import WebResponse
from typing import Optional
from flask import request, Response, stream_with_context

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
    _stream_speeds: dict[str, dict[str, float]] = {}
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
            logger.warning(f"Source returned {res.status_code} OK but Content-Length is 0. URL is likely dead/invalid.")
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

        # 4. Fallback 1: URL extension parsing if Content-Type is vague
        if res.request and res.request.url:
            url_lower = res.request.url.lower()
            if ".mp4" in url_lower:
                return "video/mp4"
            if ".m3u8" in url_lower:
                return "application/vnd.apple.mpegurl"
            if ".mpd" in url_lower:
                return "application/dash+xml"

        # 5. Fallback 2: Magic byte signature detection on binary payload
        head_bytes = res.content[:512]
        if head_bytes:
            # Check for HLS Playlist (#EXTM3U)
            if head_bytes.startswith(b'#EXTM3U'):
                return "application/vnd.apple.mpegurl"
            
            # Check for MP4 container ('ftyp', 'moov', or 'mdat' at offset 4)
            if len(head_bytes) >= 8 and head_bytes[4:8] in (b'ftyp', b'moov', b'mdat'):
                return "video/mp4"
                
            # Check for WebM / MKV container
            if head_bytes.startswith(b'\x1a\x45\xdf\xa3'):
                return "video/webm"
                
            # Check for MPEG Transport Stream (.ts) sync byte
            if head_bytes.startswith(b'G') and len(head_bytes) >= 189 and head_bytes[188] == 0x47:
                return "video/mp2t"

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
            r = session.get(stream['url'], 
                            timeout=10, 
                            headers={
                                **(stream.get('headers') or {}),
                                'Range': 'bytes=0-1023',
                                'Accept-Encoding': 'identity'
                            }, 
                            allow_redirects=True, 
                            stream=True
                        )
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
        stream['subtitles'] = [Proxy.add_proxy(url, headers=headers_str, stream_type="proxy.vtt") for url in stream['subtitles']]
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
    def _capture_curl_status(curl_obj: Any, state: dict[str, Any]) -> int:
        if state.get("status_code") is not None:
            return int(state["status_code"])

        try:
            status_code = curl_obj.getinfo(curl_obj.RESPONSE_CODE)
        except pycurl.error as exc:
            logger.warning(f"Unable to read curl status after handle closed: {exc}")
            status_code = None

        if status_code is None:
            status_code = 200

        state["status_code"] = int(status_code)
        return int(status_code)
    
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
        start_time = time.time()

        # ------------------------------------------------------------------
        # 1. Parse and Validate Proxy Arguments
        # ------------------------------------------------------------------
        media_url = request.args.get("url")
        if not media_url: 
            raise Exception("No media_url found")
            
        id = request.args.get("id")
        index = request.args.get("index")
        media_headers = request.args.get("headers", "{}")
        if not media_headers: 
            raise Exception("No media_headers found")

        logger.debug(
            f"id {id} | index {index}\n{'-'*10}\nmedia_url {media_url}\n{'-'*10}\nmedia_headers {media_headers}"
        )

        request_headers = dict(request.headers)
        try: 
            arg_headers = json.loads(media_headers)
        except Exception as e: 
            return Response(f"Unable to parse headers_str. Error: {e}", status=503)

        if "Range" in request_headers: 
            arg_headers['Range'] = request_headers['Range']

        if id and index:
            web_res = web_cache.get(id)
            if web_res:
                current_index = int(web_res.get('current_index'))
                source_index = int(index.split(':')[0])
                if current_index != source_index:
                    logger.error("Returning failure to reload webpage.")
                    return Response("Returning failure to reload webpage.", status=503)

        # ------------------------------------------------------------------
        # 2. PycURL Connection Setup (Synchronous / Threadless Retry Loop)
        # ------------------------------------------------------------------
        MAX_RETRIES = 3
        FIRST_BYTE_TIMEOUT = 5.0

        response_headers: dict[str, str] = {}
        header_status_code: list[Optional[int]] = [None]
        buffer: list[bytes] = []
        success = False
        curl_error_msg: Optional[str] = None
        c = pycurl.Curl()
        cm = pycurl.CurlMulti()
        num_handles = 0

        for attempt in range(1, MAX_RETRIES + 1):
            response_headers = {}
            header_status_code = [None]
            buffer = []
            success = False
            curl_error_msg = None
            c = pycurl.Curl()
            cm = pycurl.CurlMulti()

            c.setopt(pycurl.URL, str(media_url))
            c.setopt(pycurl.FOLLOWLOCATION, True)
            c.setopt(pycurl.SSL_VERIFYPEER, 0)
            c.setopt(pycurl.SSL_VERIFYHOST, 0)

            c.setopt(pycurl.CONNECTTIMEOUT, 5)
            c.setopt(pycurl.LOW_SPEED_LIMIT, 1024 * 256)  # 512 KB/s threshold
            c.setopt(pycurl.LOW_SPEED_TIME, 5)          # 5s low speed abort

            formatted_headers = [f"{k}: {v}" for k, v in arg_headers.items()]
            c.setopt(pycurl.HTTPHEADER, formatted_headers)

            if request.method == "POST":
                c.setopt(pycurl.POST, 1)

            def header_function(header_line: bytes) -> int:
                header_line_str = header_line.decode('iso-8859-1')
                if header_line_str.startswith('HTTP/'):
                    parts = header_line_str.split(' ')
                    if len(parts) >= 2 and parts[1].isdigit():
                        header_status_code[0] = int(parts[1])
                elif ':' in header_line_str:
                    name, value = header_line_str.split(':', 1)
                    response_headers[name.strip().lower()] = value.strip()
                return len(header_line)

            def write_function(data: bytes) -> int:
                buffer.append(data)
                return len(data)

            c.setopt(pycurl.HEADERFUNCTION, header_function)
            c.setopt(pycurl.WRITEFUNCTION, write_function)

            # Create Multi Handle to drive socket select without extra threads
            cm.add_handle(c)

            ttfb_start = time.time()

            while True:
                ret, num_handles = cm.perform()  # type: ignore

                # First byte / headers received check
                if response_headers:
                    success = True
                    break

                # Timeout check for TTFB
                if (time.time() - ttfb_start) > FIRST_BYTE_TIMEOUT:
                    curl_error_msg = f"First-byte timeout after {FIRST_BYTE_TIMEOUT}s"
                    break

                # Transfer complete or failed check before headers arrived
                if num_handles == 0:
                    # Retrieve curl error message if available
                    num_q, ok_list, err_list = cm.info_read()  # type: ignore
                    for handle, err_code, err_msg in err_list:  # type: ignore
                        logger.error(f"PycURL error during initial transfer: [{err_code}] {err_msg}")
                        curl_error_msg = err_msg
                    break

                # Wait for socket activity with 20ms precision
                cm.select(0.02)

            if success:
                break

            # Cleanup failed attempt handle
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES} failed: {curl_error_msg}. Retrying...")
            cm.remove_handle(c)
            c.close()
            cm.close()

        # Handle absolute failure after max retries
        status_code = header_status_code[0] if header_status_code else None
        if not success or not response_headers or status_code is None:
            logger.error(f"Failed to obtain headers from upstream: {curl_error_msg or 'unknown error'}")
            if id:
                web_cache.switch_source(id)
            return Response(f"Upstream low speed / error after retries: {curl_error_msg or 'unknown error'}", status=503)

        if status_code not in (200, 203, 206):
            logger.error(f"Upstream returned HTTP error status [{status_code}]")
            cm.remove_handle(c)
            c.close()
            cm.close()
            if id:
                web_cache.switch_source(id)
            return Response(f"Upstream error [{status_code}]", status=503)

        if not content_type:
            content_type = response_headers.get("content-type", "").lower()

        is_m3u8 = (
            ".m3u8" in media_url
            or "mpegurl" in content_type
            or "application/vnd.apple.mpegurl" in content_type
        )

        excluded = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
        out_headers = [(k, v) for k, v in response_headers.items() if k.lower() not in excluded]

        # ------------------------------------------------------------------
        # 3. Handle M3U8 Playlist Proxying
        # ------------------------------------------------------------------
        if is_m3u8:
            try:
                # Synchronously read remaining payload for M3U8 file
                while num_handles > 0:
                    cm.select(0.05)
                    ret, num_handles = cm.perform() # type: ignore

                content = b"".join(buffer)
                updated_content = Proxy.parse_segment(
                    content,
                    arg_headers,
                    media_url,
                    id=id,
                    index=index
                )

                resp = Response(
                    updated_content,
                    status=status_code,
                    mimetype=content_type,
                    headers=out_headers,
                )
                logger.info(f"{status_code} | {time.time() - start_time:.2f}ms | Parsing m3u8 {request.url}")
                return Proxy.apply_headers(resp)

            finally:
                # Log transfer download speed before closing handle
                # try:
                speed_bytes_sec = c.getinfo(pycurl.SPEED_DOWNLOAD_T)
                speed_kbps = speed_bytes_sec / 1024
                speed_mbps = speed_kbps / 1024
                logger.info(f"Stream finished/closed. Average speed: {speed_kbps:.2f} KB/s ({speed_mbps:.2f} MB/s)")

                cm.remove_handle(c)
                c.close()
                cm.close()

        # ------------------------------------------------------------------
        # 4. Handle Binary Video / Media Generator (Thread-Safe Single-Thread)
        # ------------------------------------------------------------------
        def generate_media():
            stream_failed = False
            try:
                while buffer:
                    yield buffer.pop(0)

                handles_remaining = 1
                while handles_remaining > 0:
                    cm.select(0.05)
                    ret, handles_remaining = cm.perform() # type: ignore

                    while buffer:
                        yield buffer.pop(0)

                    num_q, ok_list, err_list = cm.info_read() # type: ignore
                    if err_list:
                        for handle, err_code, err_msg in err_list: # type: ignore
                            logger.error(f"PycURL error mid-stream: [{err_code}] {err_msg}")
                            stream_failed = True
                        break

            except GeneratorExit:
                logger.warning(f"Client disconnected early while streaming: {media_url}")
                stream_failed = True
                raise

            except Exception as e:
                logger.error(f"Unhandled exception during media generator yield: {e}")
                stream_failed = True
                raise

            finally:
                # Log transfer download speed before closing handle
                try:
                    speed_bytes_sec = c.getinfo(pycurl.SPEED_DOWNLOAD_T)
                    speed_kbps = speed_bytes_sec / 1024
                    speed_mbps = speed_kbps / 1024
                    logger.info(f"Stream finished/closed. Average speed: {speed_kbps:.2f} KB/s ({speed_mbps:.2f} MB/s)")
                except Exception:
                    pass

                # Clean up PycURL objects safely
                try:
                    cm.remove_handle(c)
                    c.close()
                    cm.close()
                except Exception:
                    pass

                if stream_failed and id:
                    logger.warning(f"Switching source for ID: {id} after failed/aborted stream.")
                    web_cache.switch_source(id)

        resp = Response(
            stream_with_context(generate_media()),
            status=status_code,
            content_type=content_type,
            headers=out_headers,
        )

        logger.info(f"{status_code} | {time.time() - start_time:.2f}ms | Proxying url {request.url}")
        return Proxy.apply_headers(resp)