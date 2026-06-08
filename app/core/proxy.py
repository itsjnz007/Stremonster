from app.config import TUNNEL_URL
from flask import Response, jsonify
from urllib.parse import quote, urljoin
import requests, re
from app.core.logger import Logger

logger = Logger("proxy")

def respond_with(data: dict[str, object]) -> Response:
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    return resp


class Proxy:
    @staticmethod
    def get_proxy_url(stream_url: str, origin: str | None = None) -> str:
        """Construct the initial proxy URL wrapper for Stremio to consume."""
        proxied_url = urljoin(TUNNEL_URL, f"/proxy?url={quote(stream_url, safe='%')}")
        if origin: 
            proxied_url += f"&origin={quote(origin, safe='%')}"

        logger.info(f"Generated Proxied Endpoint: {proxied_url}")
        return proxied_url

    @staticmethod
    def handle_m3u8(r: requests.Response, url: str, origin: str):
        playlist = r.text
        rewritten_lines: list[str] = []
        
        # Check if this is a master playlist containing variant tracks
        is_master = "#EXT-X-STREAM-INF" in playlist

        if is_master:
            logger.info("Optimizing Master HLS Playlist tracks...")
            lines = playlist.splitlines()
            
            # Step 1: Parse and find the single best video track bandwidth
            max_bandwidth = 0
            
            for line in lines:
                line = line.strip()
                if line.startswith("#EXT-X-STREAM-INF:"):
                    bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                    if bw_match:
                        bw = int(bw_match.group(1))
                        if bw > max_bandwidth:
                            max_bandwidth = bw

            # Step 2: Rewrite playlist keeping audio tracks and ONLY the highest video track
            skip_next_url_line = False
            
            for raw_line in lines:
                line = raw_line.rstrip()
                if not line:
                    continue

                if skip_next_url_line:
                    skip_next_url_line = False
                    continue

                # Process media attributes (Like Audio groups)
                if line.startswith("#"):
                    if 'URI=' in line:
                        parts = line.split('URI="')
                        if len(parts) > 1:
                            sub_uri = parts[1].split('"')[0]
                            absolute_audio_url = urljoin(url, sub_uri)
                            encoded_audio_url = quote(absolute_audio_url, safe="%")
                            proxied_audio = f"{TUNNEL_URL}/proxy?url={encoded_audio_url}&origin={origin}"
                            line = line.replace(f'URI="{sub_uri}"', f'URI="{proxied_audio}"')
                    
                    # If it's a stream variant, see if it matches our best quality
                    if line.startswith("#EXT-X-STREAM-INF:"):
                        bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                        if bw_match and int(bw_match.group(1)) < max_bandwidth:
                            # Drop lower qualities by skipping this metadata block entirely
                            skip_next_url_line = True
                            continue
                    
                    rewritten_lines.append(line)
                    continue

                # Standard variant URL conversion
                absolute_url = urljoin(url, line)
                encoded_url = quote(absolute_url, safe="%")
                proxied_url = f"{TUNNEL_URL}/proxy?url={encoded_url}&origin={origin}"
                rewritten_lines.append(proxied_url)
                
        else:
            # Direct Media Playlist (Video chunks or Audio chunks file)
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