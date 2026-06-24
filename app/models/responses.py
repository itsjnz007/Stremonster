from typing import TypedDict
from dataclasses import dataclass

class WebResponse(TypedDict):
    """Information about the scraped stream."""
    title: str
    name: str
    url: str
    subtitles: list[str]

class ExternalWebResponse(TypedDict):
    """Information about the scraped stream."""
    title: str
    name: str
    externalUrl: str
    subtitles: list[str]

class TorrentResponse(TypedDict):
    title: str
    name: str
    infoHash: str

@dataclass
class Segment:
    url: str
    duration: float
