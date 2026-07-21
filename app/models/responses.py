from typing import Optional, TypedDict, Any, Dict
from dataclasses import dataclass

class BehaviorHints(TypedDict):
    bingeGroup: Optional[str]
    # notWebReady: Optional[bool]

class WebResponse(TypedDict):
    """Information about the scraped stream."""
    title: str # Will be depriciated. Moved to stream.description??? Refer docs.
    name: str
    url: str
    headers: Dict[str, Any]
    subtitles: list[str]
    origin: Optional[str]
    behaviorHints: Optional[BehaviorHints]
    cacheMaxAge: Optional[int]
    staleRevalidate: Optional[int]
    staleError: Optional[int]

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