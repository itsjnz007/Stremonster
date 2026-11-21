from typing import List, Optional, TypedDict


class Episode(TypedDict):
  name: str
  season: int
  number: int
  firstAired: str
  tvdb_id: int
  rating: str
  thumbnail: str
  id: str
  released: str
  episode: int


class Popularities(TypedDict):
  PXS_TEST: int
  EXMD: int
  ALLIANCE: int
  EJD: int
  moviedb: float
  trakt: int
  stremio: float
  stremio_lib: int


class MetaData(TypedDict):
  awards: str
  cast: List[str]
  country: str
  description: str
  director: Optional[str]
  dvdRelease: str
  genre: List[str]
  imdbRating: str
  imdb_id: str
  name: str
  popularity: float
  poster: str
  released: str
  runtime: str
  status: str
  tvdb_id: str
  type: str
  writer: List[str]
  year: str
  popularities: Popularities
  logo: str
  moviedb_id: int
  background: str
  slug: str
  id: str
  genres: List[str]
  releaseInfo: str
  videos: List[Episode]


class CinemetaResponse(TypedDict):
  meta: MetaData