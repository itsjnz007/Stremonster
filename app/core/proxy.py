from app.config import TUNNEL_URL
from flask import Response, request, jsonify, stream_with_context
from urllib.parse import quote, urlparse
from app.core.logger import Logger
import json, re, urllib3, logging, time, requests, queue, pycurl, threading
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
        # 2. PycURL Connection Setup with Fast Retry Loop
        # ------------------------------------------------------------------
        MAX_RETRIES = 3
        FIRST_BYTE_TIMEOUT = 5.0  # Increased to prevent premature timeouts on worker cold-starts

        active_curl_handle: Optional[pycurl.Curl] = None
        active_curl_thread: Optional[threading.Thread] = None
        
        response_headers: dict[str, str] = {}
        chunk_queue: queue.Queue[Optional[bytes]] = queue.Queue(maxsize=10)
        curl_state: dict[str, Any] = {"status_code": None, "curl_error": []}
        is_paused = False

        for attempt in range(1, MAX_RETRIES + 1):
            response_headers.clear()
            curl_state = {"status_code": None, "curl_error": []}
            chunk_queue = queue.Queue(maxsize=10)
            is_paused = False

            # Create fresh PycURL handle for this attempt
            c = pycurl.Curl()
            c.setopt(pycurl.URL, str(media_url))
            c.setopt(pycurl.FOLLOWLOCATION, True)
            c.setopt(pycurl.SSL_VERIFYPEER, 0)
            c.setopt(pycurl.SSL_VERIFYHOST, 0)
            
            c.setopt(pycurl.CONNECTTIMEOUT, 5)
            c.setopt(pycurl.LOW_SPEED_LIMIT, 1024 * 128 )  # 1 KB/s threshold
            c.setopt(pycurl.LOW_SPEED_TIME, 15)     # 15s low speed abort

            formatted_headers = [f"{k}: {v}" for k, v in arg_headers.items()]
            c.setopt(pycurl.HTTPHEADER, formatted_headers)

            if request.method == "POST":
                c.setopt(pycurl.POST, 1)

            def header_function(header_line: bytes) -> int:
                header_line_str = header_line.decode('iso-8859-1')
                if header_line_str.startswith('HTTP/'):
                    parts = header_line_str.split(' ')
                    if len(parts) >= 2 and parts[1].isdigit():
                        curl_state["status_code"] = int(parts[1])
                elif ':' in header_line_str:
                    name, value = header_line_str.split(':', 1)
                    response_headers[name.strip().lower()] = value.strip()
                return len(header_line)

            c.setopt(pycurl.HEADERFUNCTION, header_function)

            def write_callback(data: bytes) -> int:
                nonlocal is_paused
                try:
                    chunk_queue.put(data, block=True, timeout=0.2)
                    return len(data)
                except queue.Full:
                    is_paused = True
                    return pycurl.WRITEFUNC_PAUSE  # type: ignore

            c.setopt(pycurl.WRITEFUNCTION, write_callback)

            def run_curl(handle: pycurl.Curl, state_dict: dict[str, Any]) -> None:
                try:
                    handle.perform()
                    # Capture info safely inside thread where perform() ran
                    state_dict["status_code"] = handle.getinfo(pycurl.RESPONSE_CODE)
                    dl_speed_bytes = handle.getinfo(pycurl.SPEED_DOWNLOAD_T)
                    logger.info(f"PycURL download speed: {dl_speed_bytes / 1024:.2f} KB/s")
                except pycurl.error as e:
                    logger.error(f"PycURL upstream error on attempt {attempt}: {e}")
                    state_dict["curl_error"].append(e)
                finally:
                    chunk_queue.put(None)
                    try:
                        handle.close()
                    except Exception:
                        pass

            curl_thread = threading.Thread(target=run_curl, args=(c, curl_state), daemon=True)
            curl_thread.start()

            # Wait for TTFB / initial headers
            first_byte_start = time.time()
            timed_out = False
            while not response_headers and curl_thread.is_alive() and not curl_state["curl_error"]:
                if (time.time() - first_byte_start) > FIRST_BYTE_TIMEOUT:
                    logger.warning(
                        f"Attempt {attempt}/{MAX_RETRIES} timed out waiting for first byte after {FIRST_BYTE_TIMEOUT}s. Retrying..."
                    )
                    timed_out = True
                    break
                time.sleep(0.01)

            # Success check
            if response_headers and not curl_state["curl_error"] and not timed_out:
                active_curl_handle = c
                active_curl_thread = curl_thread
                break  # Exit retry loop on success

            # Clean up timed-out attempt safely
            if timed_out:
                try:
                    c.pause(pycurl.PAUSE_ALL)  # Tell libcurl to pause processing safely
                except Exception:
                    pass

        # Check for absolute failure after max retries
        status_code = curl_state.get("status_code")
        if not response_headers or curl_state["curl_error"] or not status_code:
            if id: 
                web_cache.switch_source(id)
            else:
                logger.warning("'request_id' not available, skipping source switch")
            err_msg = curl_state["curl_error"][0] if curl_state["curl_error"] else "First-byte response timeout"
            return Response(f"Upstream low speed / error after retries: {err_msg}", status=503)

        if status_code not in (200, 203, 206):
            logger.error(f"Upstream error [{status_code}]")
            if id: 
                web_cache.switch_source(id)
            else:
                logger.warning("'request_id' not available, skipping source switch")
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
        if is_m3u8 and status_code in (200, 203, 206):
            content_chunks: list[bytes] = []
            while True:
                chunk = chunk_queue.get()
                if chunk is None:
                    break
                content_chunks.append(chunk)

            content = b"".join(content_chunks)

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

        # ------------------------------------------------------------------
        # 4. Handle Binary Video / MP4 / TS Streaming Generator
        # ------------------------------------------------------------------
        def generate_media():
            nonlocal is_paused
            try:
                while True:
                    if is_paused and chunk_queue.qsize() < 5:
                        try:
                            if active_curl_handle:
                                active_curl_handle.pause(pycurl.PAUSE_CONT)
                            is_paused = False
                        except pycurl.error:
                            pass

                    try:
                        chunk = chunk_queue.get(timeout=0.5)
                    except queue.Empty:
                        if active_curl_thread and not active_curl_thread.is_alive():
                            break
                        continue

                    if chunk is None:  # EOF
                        break

                    yield chunk

            except Exception as e:
                logger.error(f"Error while yielding chunk. Error: {e}")
                if id and index:
                    web_res = web_cache.get(id)
                    if web_res:
                        current_index = int(web_res.get('current_index'))
                        source_index = int(index.split(':')[0])
                        if current_index == source_index:
                            web_cache.switch_source(id)
                else:
                    logger.warning("'id' or 'index' not available, skipping source switch")
            finally:
                if curl_state["curl_error"] and id:
                    logger.warning(f"PycURL aborted stream due to slow speed. Switching source for {id}")
                    web_cache.switch_source(id)

        resp = Response(
            stream_with_context(generate_media()),
            status=status_code,
            content_type=content_type,
            headers=out_headers,
        )

        logger.info(f"{status_code} | {time.time() - start_time:.2f}ms | Proxying url {request.url}")
        return Proxy.apply_headers(resp)