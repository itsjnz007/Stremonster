# import sys
# from pathlib import Path
# sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# from app.core.proxy import Proxy
# from app.core.scraper import Scraper
# from app.models.responses import WebResponse
# from typing import Optional

# class VidkingScraper(Scraper):
#     def __init__(self):
#         super().__init__(headless=True, source="vidking")
#         # self.base_url = "https://vidking.net"
#         self.base_url = "https://www.vidsrc.wtf"

#     def get_movie(self, tmdb_id: str) -> Optional[WebResponse]:
#         # url = f"{self.base_url}/embed/movie/{tmdb_id}"
#         url = f"{self.base_url}/1/movie/{tmdb_id}"
#         result = self.get_stream(url)
#         if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
#         return result
    
#     def get_series(self, tmdb_id: str, season: str, episode: str) -> Optional[WebResponse]:
#         # url = f"{self.base_url}/embed/tv/{tmdb_id}/{season}/{episode}"
#         url = f"{self.base_url}/1/tv/{tmdb_id}/{season}/{episode}"
#         result = self.get_stream(url)
#         if result: result['url'] = Proxy.get_proxy_url(result['url'], origin=self.base_url)
#         return result