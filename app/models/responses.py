from typing import Optional, TypedDict, Any, Dict
from dataclasses import dataclass, field
from collections import deque
import time


def _new_speed_window_chunks() -> deque[tuple[float, int, float]]:
    return deque()


class BehaviorHints(TypedDict):
    bingeGroup: Optional[str]
    # notWebReady: Optional[bool]

class Subtitle(TypedDict):
    id: str
    lang: str
    url: str
    label: Optional[str]
    
class WebResponse(TypedDict):
    """Information about the scraped stream."""
    title: str # Will be depriciated. Moved to stream.description??? Refer docs.
    name: str
    url: str
    headers: Dict[str, Any]
    subtitles: list[Subtitle]
    contentType: Optional[str]
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


@dataclass
class SpeedWindow:
    chunks: deque[tuple[float, int, float]] = field(default_factory=_new_speed_window_chunks)
    started_at: float = field(default_factory=time.monotonic)