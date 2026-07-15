from typing import Optional, TypedDict
from dataclasses import dataclass

class BehaviorHints(TypedDict):
    bingeGroup: Optional[str]

class WebResponse(TypedDict):
    """Information about the scraped stream."""
    title: str
    name: str
    url: str
    subtitles: list[str]
    origin: Optional[str]
    behaviorHints: Optional[BehaviorHints]

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
    bandwidth: Optional[float]


@dataclass
class Segment:
    url: str
    duration: float