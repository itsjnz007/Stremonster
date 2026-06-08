from typing import TypedDict


class StreamResponse(TypedDict):
    """Information about the scraped stream."""
    title: str
    name: str
    url: str
    subtitles: list[str]

class TorrentResponse(TypedDict):
    title: str
    name: str
    infoHash: str
