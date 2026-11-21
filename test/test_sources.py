"""Live smoke tests for every source under ``app.sources``.

Run from the repository root with::

    python test/test_sources.py

The source list is discovered at runtime, so adding or removing a source module
or source class changes the report automatically.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from types import ModuleType
from typing import Any, Callable, Iterable, cast


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.multithreading import MultiThreading
from app.core.scraper import Scraper


@dataclass
class Probe:
    movie_id: str = "550"
    series_id: str = "1399"
    imdb_id: str = "tt0137523"
    anime_id: str = "21"
    title: str = "Fight Club"
    year: str = "1999"
    season: str = "1"
    episode: str = "1"
    timeout: float = 45.0


@dataclass
class Result:
    name: str
    status: str
    elapsed: float
    detail: str = ""


def source_modules() -> Iterable[ModuleType]:
    """Import every module below app.sources, including nested packages."""
    package = importlib.import_module("app.sources")
    yield package
    prefix = package.__name__ + "."
    for module_info in pkgutil.walk_packages(package.__path__, prefix):
        yield importlib.import_module(module_info.name)


def source_classes(module: ModuleType) -> Iterable[type[Scraper]]:
    for _, candidate in inspect.getmembers(module, inspect.isclass):
        if (
            candidate is not Scraper
            and issubclass(candidate, Scraper)
            and candidate.__module__ == module.__name__
        ):
            yield candidate


def source_operations(module: ModuleType) -> Iterable[tuple[str, Callable[..., Any], Any]]:
    """Yield (display name, callable, owner) for discovered source operations."""
    for source_class in source_classes(module):
        instance = cast(Any, source_class)()
        for operation in ("get_movie", "get_series"):
            method = getattr(instance, operation, None)
            if callable(method):
                yield f"{module.__name__}.{source_class.__name__}.{operation}", method, instance

    for operation in ("get_movie", "get_series"):
        function = getattr(module, operation, None)
        if inspect.isfunction(function) and function.__module__ == module.__name__:
            yield f"{module.__name__}.{operation}", function, None


def argument_for(name: str, probe: Probe, operation_name: str) -> Any:
    media_id = probe.series_id if operation_name == "get_series" else probe.movie_id
    values: dict[str, Any] = {
        "tmdb_id": media_id,
        "imdb_id": probe.imdb_id,
        "mal_id": probe.anime_id,
        "anilist_id": probe.anime_id,
        "animal_id": probe.anime_id,
        "id": probe.movie_id,
        "title": probe.title,
        "year": probe.year,
        "season": probe.season,
        "episode": probe.episode,
        "threadpool": MultiThreading(max_workers=2),
        "stop_event": Event(),
        "test_speeds": False,
    }
    if name not in values:
        raise ValueError(f"no probe value configured for parameter '{name}'")
    return values[name]


def call_operation(operation: Callable[..., Any], probe: Probe) -> Any:
    signature = inspect.signature(operation)
    kwargs: dict[str, Any] = {}
    for parameter in signature.parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        if parameter.default is not parameter.empty and parameter.name not in {
            "threadpool",
        }:
            continue
        kwargs[parameter.name] = argument_for(parameter.name, probe, operation.__name__)
    return operation(**kwargs)


def has_response(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return bool(cast(Any, value))
    return True


def run_operation(name: str, operation: Callable[..., Any], owner: Any, probe: Probe) -> Result:
    if owner is not None and hasattr(owner, "timeout"):
        owner.timeout = int(probe.timeout * 1000)

    started = time.monotonic()
    try:
        response = call_operation(operation, probe)
        elapsed = time.monotonic() - started
        if has_response(response):
            return Result(name, "WORKING", elapsed, response_summary(response))
        return Result(name, "NOT WORKING", elapsed, "empty response")
    except ValueError as error:
        return Result(name, "SKIPPED", time.monotonic() - started, str(error))
    except Exception as error:
        detail = f"{type(error).__name__}: {error}"
        return Result(name, "NOT WORKING", time.monotonic() - started, detail)


def response_summary(response: Any) -> str:
    if isinstance(response, (list, tuple, set, dict)):
        return f"{len(cast(Any, response))} result(s)"
    return type(response).__name__


def print_report(results: list[Result]) -> None:
    print("\nSource smoke-test report")
    print("=" * 80)
    for result in results:
        detail = f" - {result.detail}" if result.detail else ""
        print(f"{result.status:12} {result.elapsed:7.2f}s  {result.name}{detail}")

    counts = {status: sum(result.status == status for result in results) for status in (
        "WORKING", "NOT WORKING", "SKIPPED"
    )}
    print("-" * 80)
    print(
        f"Total: {len(results)} | Working: {counts['WORKING']} | "
        f"Not working: {counts['NOT WORKING']} | Skipped: {counts['SKIPPED']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--movie-id", default="550", help="TMDB/IMDb movie probe ID")
    parser.add_argument("--series-id", default="1399", help="TMDB/IMDb series probe ID")
    parser.add_argument("--imdb-id", default="tt0137523", help="IMDb ID for Torrentio probes")
    parser.add_argument("--anime-id", default="21", help="MAL/Anilist anime probe ID")
    parser.add_argument("--title", default="Fight Club", help="regional source title probe")
    parser.add_argument("--year", default="1999", help="regional source year probe")
    parser.add_argument("--season", default="1")
    parser.add_argument("--episode", default="1")
    parser.add_argument("--timeout", type=float, default=45.0, help="timeout per browser source in seconds")
    parser.add_argument("--match", help="only run discovered names containing this text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    probe = Probe(
        movie_id=args.movie_id,
        series_id=args.series_id,
        imdb_id=args.imdb_id,
        anime_id=args.anime_id,
        title=args.title,
        year=args.year,
        season=args.season,
        episode=args.episode,
        timeout=args.timeout,
    )
    results: list[Result] = []

    try:
        for module in source_modules():
            for name, operation, owner in source_operations(module):
                if args.match and args.match.lower() not in name.lower():
                    continue
                results.append(run_operation(name, operation, owner, probe))
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        Scraper.shutdown()

    print_report(results)
    return 0 if results and not any(result.status == "NOT WORKING" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())