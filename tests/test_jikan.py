"""Tests for the Jikan client. They use recorded data and never call the real API."""

import json
from pathlib import Path

import pytest
import requests
import responses

from ingest import jikan

FIXTURE = Path(__file__).parent / "fixtures" / "jikan_top_anime_page1.json"
TOP_URL = f"{jikan.BASE_URL}/top/anime"
GENRES_URL = f"{jikan.BASE_URL}/genres/anime"


@pytest.fixture
def top_page() -> dict:
    """Page 1 of /top/anime as Jikan sends it: the 25 recorded anime plus pagination."""
    anime = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {"data": anime, "pagination": {"has_next_page": True}}


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace time.sleep so tests run instantly, and record every wait asked for."""
    waits: list[float] = []
    monkeypatch.setattr(jikan.time, "sleep", waits.append)
    return waits


@responses.activate
def test_success_returns_json_and_throttles(top_page: dict, sleeps: list[float]) -> None:
    responses.get(TOP_URL, json=top_page)

    data = jikan.get("top/anime", params={"page": 1})

    assert data["data"][0]["mal_id"] == 52991  # Frieren is first
    assert sleeps == [jikan.THROTTLE_SECONDS]


@responses.activate
def test_504_then_success_is_retried(top_page: dict, sleeps: list[float]) -> None:
    responses.get(TOP_URL, status=504)
    responses.get(TOP_URL, json=top_page)

    data = jikan.get("top/anime")

    assert len(data["data"]) == 25
    assert len(responses.calls) == 2
    assert sleeps == [1, jikan.THROTTLE_SECONDS]  # one backoff wait, then the throttle


@responses.activate
def test_404_is_not_retried(sleeps: list[float]) -> None:
    responses.get(f"{jikan.BASE_URL}/anime/999999999", status=404)

    with pytest.raises(requests.HTTPError):
        jikan.get("anime/999999999")

    assert len(responses.calls) == 1
    assert sleeps == []


@responses.activate
def test_429_waits_for_retry_after(top_page: dict, sleeps: list[float]) -> None:
    responses.get(TOP_URL, status=429, headers={"Retry-After": "7"})
    responses.get(TOP_URL, json=top_page)

    jikan.get("top/anime")

    assert sleeps[0] == 7


@responses.activate
def test_retry_after_is_capped(top_page: dict, sleeps: list[float]) -> None:
    responses.get(TOP_URL, status=429, headers={"Retry-After": "3600"})
    responses.get(TOP_URL, json=top_page)

    jikan.get("top/anime")

    assert sleeps[0] == jikan.MAX_RETRY_AFTER_SECONDS


@responses.activate
def test_gives_up_after_max_retries(sleeps: list[float]) -> None:
    for _ in range(jikan.MAX_RETRIES):
        responses.get(TOP_URL, status=503)

    with pytest.raises(requests.HTTPError):
        jikan.get("top/anime")

    assert len(responses.calls) == jikan.MAX_RETRIES
    assert sleeps == [1, 2]


@responses.activate
def test_connection_error_is_retried(top_page: dict, sleeps: list[float]) -> None:
    responses.get(TOP_URL, body=requests.ConnectionError("connection reset"))
    responses.get(TOP_URL, json=top_page)

    data = jikan.get("top/anime")

    assert len(data["data"]) == 25
    assert sleeps == [1, jikan.THROTTLE_SECONDS]


@responses.activate
def test_failing_page_is_skipped(top_page: dict, sleeps: list[float]) -> None:
    # Page 1 works. Page 2 fails every attempt. Page 3 works.
    responses.get(
        TOP_URL, json=top_page, match=[responses.matchers.query_param_matcher({"page": 1})]
    )
    responses.get(TOP_URL, status=504, match=[responses.matchers.query_param_matcher({"page": 2})])
    responses.get(
        TOP_URL, json=top_page, match=[responses.matchers.query_param_matcher({"page": 3})]
    )

    result = jikan.get_top_anime(pages=3)

    assert len(result.items) == 50
    assert result.failed_pages == [2]


@responses.activate
def test_paging_stops_when_there_is_no_next_page(top_page: dict, sleeps: list[float]) -> None:
    top_page["pagination"]["has_next_page"] = False
    responses.get(f"{jikan.BASE_URL}/seasons/now", json=top_page)

    result = jikan.get_season_now(pages=4)

    assert len(responses.calls) == 1
    assert result.failed_pages == []


@responses.activate
def test_genre_reference_tags_each_family_with_its_kind(sleeps: list[float]) -> None:
    samples = {
        "genres": {"mal_id": 2, "name": "Adventure"},
        "explicit_genres": {"mal_id": 12, "name": "Hentai"},
        "themes": {"mal_id": 50, "name": "Adult Cast"},
        "demographics": {"mal_id": 27, "name": "Shounen"},
    }
    for jikan_filter, tag in samples.items():
        responses.get(
            GENRES_URL,
            json={"data": [tag]},
            match=[responses.matchers.query_param_matcher({"filter": jikan_filter})],
        )

    records = jikan.get_genre_reference()

    assert {"genre_id": 27, "name": "Shounen", "kind": "demographic"} in records
    assert sorted(r["kind"] for r in records) == [
        "demographic",
        "explicit_genre",
        "genre",
        "theme",
    ]
