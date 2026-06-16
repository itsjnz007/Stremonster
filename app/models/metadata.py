from typing import Optional, List
from dataclasses import dataclass

@dataclass
class Metadata:
    title: str
    url: str
    year: Optional[str] = None
    languages: List[str] = None # type: ignore

    def __post_init__(self):
        if self.languages is None: # type: ignore
            self.languages = []