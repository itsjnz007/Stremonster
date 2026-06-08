from typing import TypedDict


class StreamResponse(TypedDict):
    """Information about the scraped stream."""
    title: str
    url: str
    subtitles: list[str]
