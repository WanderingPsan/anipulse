"""API tests against tiny data files written to a temporary folder."""

import json
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import ATTRIBUTION, app

FRIEREN = 52991


def write_fixture_files(folder: Path) -> None:
    """Six titles. Frieren has 3 picks, 900 has none, 905 has no English title or year."""
    catalog = pd.DataFrame(
        {
            "mal_id": [FRIEREN, 900, 901, 902, 903, 905],
            "title": [
                "Sousou no Frieren",
                "Frieren Recap",
                "Dungeon Meshi",
                "Mushoku Tensei",
                "Kusuriya no Hitorigoto",
                "Obscure Short",
            ],
            "title_english": [
                "Frieren: Beyond Journey's End",
                None,
                "Delicious in Dungeon",
                "Jobless Reincarnation",
                "The Apothecary Diaries",
                None,
            ],
            "type": ["TV", "Special", "TV", "TV", "TV", "ONA"],
            "year": pd.array([2023, 2024, 2024, 2021, 2023, None], dtype="Int64"),
            "score": [9.25, 7.0, 8.6, 8.4, 8.9, None],
            "members": pd.array([1_500_000, 2_000, 600_000, 900_000, 700_000, None], dtype="Int64"),
            "genres": [["Adventure", "Fantasy"], [], ["Fantasy"], ["Fantasy"], ["Drama"], []],
            "studios": [["Madhouse"], [], ["Trigger"], ["Studio Bind"], ["OLM"], []],
        }
    )
    catalog.to_parquet(folder / "catalog.parquet", index=False)
    recs = pd.DataFrame(
        {
            "anime_id": [FRIEREN, FRIEREN, FRIEREN, 901],
            "rank": [1, 2, 3, 1],
            "similar_id": [901, 902, 903, FRIEREN],
            "similarity": pd.array([0.9953, 0.9, 0.81, 0.97], dtype="float32"),
        }
    )
    # Written out of order to check the API sorts by rank itself.
    recs.iloc[::-1].to_parquet(folder / "recommendations.parquet", index=False)
    metadata = {"data_last_updated": "2026-10-09T00:20:52+00:00"}
    (folder / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    write_fixture_files(tmp_path)
    monkeypatch.setenv("ANIPULSE_DATA_DIR", str(tmp_path))
    # The with block runs the startup hook, which loads the files.
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body == {
        "status": "ok",
        "last_updated": "2026-10-09T00:20:52+00:00",
        "anime_count": 6,
        "attribution": ATTRIBUTION,
    }


def test_attribution_is_in_docs_description(client: TestClient) -> None:
    assert ATTRIBUTION in client.get("/openapi.json").json()["info"]["description"]


def test_search_matches_both_titles_ignoring_case_most_members_first(client: TestClient) -> None:
    body = client.get("/anime/search", params={"q": "FRIEREN"}).json()
    assert [r["mal_id"] for r in body["results"]] == [FRIEREN, 900]
    assert body["count"] == 2
    english = client.get("/anime/search", params={"q": "apothecary"}).json()
    assert [r["mal_id"] for r in english["results"]] == [903]


def test_search_respects_limit_and_treats_query_as_plain_text(client: TestClient) -> None:
    body = client.get("/anime/search", params={"q": "o", "limit": 2}).json()
    assert [r["mal_id"] for r in body["results"]] == [FRIEREN, 902]
    assert client.get("/anime/search", params={"q": "("}).json()["count"] == 0


def test_search_rejects_empty_query_and_bad_limit(client: TestClient) -> None:
    assert client.get("/anime/search", params={"q": ""}).status_code == 422
    assert client.get("/anime/search", params={"q": "a", "limit": 0}).status_code == 422


def test_get_anime(client: TestClient) -> None:
    body = client.get(f"/anime/{FRIEREN}").json()
    assert body["title"] == "Sousou no Frieren"
    assert body["year"] == 2023
    assert body["genres"] == ["Adventure", "Fantasy"]


def test_missing_values_become_null(client: TestClient) -> None:
    body = client.get("/anime/905").json()
    assert body["title_english"] is None
    assert body["year"] is None
    assert body["score"] is None
    assert body["members"] is None
    assert body["studios"] == []


def test_unknown_anime_is_404(client: TestClient) -> None:
    assert client.get("/anime/123456").status_code == 404
    assert client.get("/recommend/123456").status_code == 404


def test_recommend_in_rank_order_with_match_score(client: TestClient) -> None:
    body = client.get(f"/recommend/{FRIEREN}").json()
    assert body["title"] == "Sousou no Frieren"
    assert body["count"] == 3
    assert [r["mal_id"] for r in body["recommendations"]] == [901, 902, 903]
    first = body["recommendations"][0]
    assert first["rank"] == 1
    assert first["match_score"] == 0.9953
    assert "similarity" not in first


def test_recommend_respects_k(client: TestClient) -> None:
    body = client.get(f"/recommend/{FRIEREN}", params={"k": 2}).json()
    assert [r["rank"] for r in body["recommendations"]] == [1, 2]


def test_short_list_returns_what_exists(client: TestClient) -> None:
    # Frieren has only 3 picks in the fixture; asking for 10 is not an error.
    response = client.get(f"/recommend/{FRIEREN}", params={"k": 10})
    assert response.status_code == 200
    assert response.json()["count"] == 3


def test_title_with_no_recommendations_gets_empty_list(client: TestClient) -> None:
    response = client.get("/recommend/900")
    assert response.status_code == 200
    assert response.json()["recommendations"] == []


@pytest.mark.parametrize("k", [0, 11])
def test_k_out_of_range_is_rejected(client: TestClient, k: int) -> None:
    assert client.get(f"/recommend/{FRIEREN}", params={"k": k}).status_code == 422


def test_cors_allows_any_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "https://example.com"})
    assert response.headers["access-control-allow-origin"] == "*"


def test_missing_data_file_fails_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANIPULSE_DATA_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="catalog.parquet"):
        with TestClient(app):
            pass
