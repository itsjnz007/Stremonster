import unittest

import requests

from app.core.proxy import Proxy


class ContentTypeTests(unittest.TestCase):
    def make_response(self, content_type: str = "", url: str = "", content: bytes = b"") -> requests.Response:
        response = requests.Response()
        response.status_code = 200
        response.headers["content-type"] = content_type
        response._content = content
        if url:
            response.request = requests.Request("GET", url).prepare()
        return response

    def test_webm_content_type_is_preserved(self) -> None:
        response = self.make_response("video/webm; codecs=vp9")

        self.assertEqual(Proxy.get_content_type(response), "video/webm")

    def test_webm_url_is_detected_when_content_type_is_generic(self) -> None:
        response = self.make_response("application/octet-stream", "https://example.com/video.webm?token=abc")

        self.assertEqual(Proxy.get_content_type(response), "video/webm")

    def test_webm_container_signature_is_detected(self) -> None:
        response = self.make_response(content=b"\x1a\x45\xdf\xa3")

        self.assertEqual(Proxy.get_content_type(response), "video/webm")


if __name__ == "__main__":
    unittest.main()
