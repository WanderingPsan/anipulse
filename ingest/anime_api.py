"""A small client for a Jikan v4-compatible anime API (an unofficial MyAnimeList API).

The default server is Tenrai. Any server that speaks the Jikan v4 format works, so the base
URL comes from the ANIME_API_BASE_URL environment variable. Free APIs like this are strict
and sometimes flaky, so every request is throttled, and only errors that might go away on
their own are retried.
"""

import logging
import os
import time
from typing import Any, NamedTuple

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.tenrai.org/v1"


def base_url_from_env() -> str:
    """Read the API's base URL from the environment, falling back to Tenrai.

    A trailing slash is removed so "…/v1/" and "…/v1" build the same request URLs.
    """
    return os.getenv("ANIME_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


# Load .env first so a value saved there counts, not only one set in the shell.
load_dotenv()
BASE_URL = base_url_from_env()

# The Jikan v4 limits are 3 requests per second AND 60 per minute. 0.5 s respects the first
# limit but a long run would hit the second (120 per minute). 1.0 s keeps us under both.
# Tenrai does not publish its own limits, so we keep these conservative ones.
THROTTLE_SECONDS = 1.0
MAX_RETRIES = 3
TIMEOUT_SECONDS = 20
# A server could ask us to wait for an hour. Cap it so one bad header cannot stall a run.
MAX_RETRY_AFTER_SECONDS = 60

# The four tag families MyAnimeList shares one ID space for. Key: the API's filter value.
# Value: the singular "kind" we store in the genres table.
GENRE_FILTERS = {
    "genres": "genre",
    "explicit_genres": "explicit_genre",
    "themes": "theme",
    "demographics": "demographic",
}


class PageResult(NamedTuple):
    """What a paginated fetch returns: the rows it got, and which pages it had to skip."""

    items: list[dict[str, Any]]
    failed_pages: list[int]


def _backoff_seconds(attempt: int) -> int:
    """Exponential backoff: wait 1 s after the first failure, then 2 s."""
    return 2 ** (attempt - 1)


def _is_retryable_status(status_code: int) -> bool:
    """429 (slow down) and 5xx (server trouble) can succeed later. Other 4xx never will."""
    return status_code == 429 or status_code >= 500


def _retry_after_seconds(response: requests.Response, attempt: int) -> float:
    """Honor the server's Retry-After header on a 429. Otherwise use normal backoff."""
    header = response.headers.get("Retry-After")
    if response.status_code == 429 and header is not None:
        try:
            return min(float(header), MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            # Retry-After can also be an HTTP date. That is rare, so fall back to backoff.
            pass
    return _backoff_seconds(attempt)


def get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send one GET request to the anime API and return the parsed JSON.

    Retries connection errors, timeouts, 429, and 5xx up to MAX_RETRIES attempts.
    Raises right away on other errors (like 404), and after the last failed attempt.
    """
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        except (requests.ConnectionError, requests.Timeout) as err:
            if attempt == MAX_RETRIES:
                raise
            wait = _backoff_seconds(attempt)
            logger.warning(
                "Attempt %d for %s failed (%s). Retrying in %ss.", attempt, url, err, wait
            )
            time.sleep(wait)
            continue

        if response.ok:
            time.sleep(THROTTLE_SECONDS)
            return response.json()

        if not _is_retryable_status(response.status_code) or attempt == MAX_RETRIES:
            response.raise_for_status()

        wait = _retry_after_seconds(response, attempt)
        logger.warning(
            "Attempt %d for %s got HTTP %d. Retrying in %ss.",
            attempt,
            url,
            response.status_code,
            wait,
        )
        time.sleep(wait)

    # Unreachable: the loop either returns or raises. This line keeps type checkers happy.
    raise RuntimeError("retry loop exited without a result")


def _get_pages(endpoint: str, pages: int) -> PageResult:
    """Fetch pages 1..pages of a paginated endpoint, skipping pages that keep failing.

    One bad page should not throw away the pages that worked, so a failed page is logged
    and recorded instead of raised.
    """
    items: list[dict[str, Any]] = []
    failed_pages: list[int] = []
    for page in range(1, pages + 1):
        try:
            data = get(endpoint, params={"page": page})
        except requests.RequestException as err:
            logger.error("Skipping page %d of %s: %s", page, endpoint, err)
            failed_pages.append(page)
            continue
        items.extend(data["data"])
        if not data.get("pagination", {}).get("has_next_page", True):
            break  # no more pages exist, so do not ask for them
    return PageResult(items, failed_pages)


def get_top_anime(pages: int = 1) -> PageResult:
    """Fetch the top-rated anime, 25 per page."""
    return _get_pages("top/anime", pages)


def get_season_now(pages: int = 1) -> PageResult:
    """Fetch the anime airing this season, 25 per page."""
    return _get_pages("seasons/now", pages)


def get_genre_reference() -> list[dict[str, Any]]:
    """Fetch every genre-like tag with its MyAnimeList ID and kind.

    Makes 4 calls, one per tag family. Unlike the paginated helpers this raises on failure,
    because a reference file with a missing family would be silently wrong.
    """
    records: list[dict[str, Any]] = []
    for api_filter, kind in GENRE_FILTERS.items():
        data = get("genres/anime", params={"filter": api_filter})
        for tag in data["data"]:
            records.append({"genre_id": tag["mal_id"], "name": tag["name"], "kind": kind})
    return records
