"""Tests for turning CSV rows and API anime into records, using the real fixtures."""

import json
from pathlib import Path

import pytest

from ingest.kaggle import read_kaggle_csv
from transform.records import (
    ANIME_COLUMNS,
    CompanyRef,
    dedupe_by_mal_id,
    flatten_jikan_anime,
    is_excluded,
    kaggle_row_to_record,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def kaggle_records() -> dict[int, dict]:
    df = read_kaggle_csv(FIXTURES / "kaggle_sample.csv")
    return {r["mal_id"]: r for r in map(kaggle_row_to_record, df.to_dict("records"))}


@pytest.fixture(scope="module")
def api_records() -> dict[int, dict]:
    raw = json.loads((FIXTURES / "jikan_top_anime_page1.json").read_text(encoding="utf-8"))
    return {r["mal_id"]: r for r in map(flatten_jikan_anime, raw)}


def test_kaggle_frieren_record(kaggle_records: dict[int, dict]) -> None:
    frieren = kaggle_records[52991]
    assert frieren["title"] == "Sousou no Frieren"
    assert frieren["episodes"] == 28
    assert frieren["duration_min"] == 24
    assert (frieren["season"], frieren["year"]) == ("fall", 2023)
    assert frieren["broadcast_day"] == "Fridays"
    assert frieren["data_source"] == "kaggle"
    assert frieren["tags"] == ["Adventure", "Drama", "Fantasy", "Shounen"]
    assert CompanyRef("Madhouse", "studio") in frieren["companies"]


def test_kaggle_missing_year_and_season_are_filled_from_air_date(
    kaggle_records: dict[int, dict],
) -> None:
    # Spirited Away (199) has no season or year in the CSV but aired on 2001-07-20.
    spirited_away = kaggle_records[199]
    assert (spirited_away["season"], spirited_away["year"]) == ("summer", 2001)


def test_kaggle_unknown_duration_is_none(kaggle_records: dict[int, dict]) -> None:
    assert kaggle_records[49233]["duration_min"] is None


def test_api_frieren_record(api_records: dict[int, dict]) -> None:
    frieren = api_records[52991]
    assert frieren["title"] == "Sousou no Frieren"
    assert frieren["duration_min"] == 24
    assert (frieren["season"], frieren["year"]) == ("fall", 2023)
    assert (frieren["broadcast_day"], frieren["broadcast_time"]) == ("Fridays", "23:00")
    assert frieren["data_source"] == "api"
    assert "Shounen" in frieren["tags"]
    assert CompanyRef("Madhouse", "studio", 11) in frieren["companies"]


def test_both_sources_give_the_same_shape(
    kaggle_records: dict[int, dict], api_records: dict[int, dict]
) -> None:
    expected = set(ANIME_COLUMNS) | {"tags", "companies"}
    assert set(kaggle_records[52991]) == expected
    assert set(api_records[52991]) == expected


def test_rx_titles_are_excluded(kaggle_records: dict[int, dict]) -> None:
    excluded = [mal_id for mal_id, r in kaggle_records.items() if is_excluded(r)]
    assert len(excluded) == 1
    assert kaggle_records[excluded[0]]["rating"].startswith("Rx")


def test_missing_rating_is_not_excluded() -> None:
    assert not is_excluded({"rating": None})


def test_dedupe_keeps_last_record_per_mal_id() -> None:
    records = [{"mal_id": 1, "v": "old"}, {"mal_id": 2}, {"mal_id": 1, "v": "new"}]
    kept, dropped = dedupe_by_mal_id(records)
    assert dropped == 1
    assert {"mal_id": 1, "v": "new"} in kept
