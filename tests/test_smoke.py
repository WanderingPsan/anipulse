"""A smoke test: proves pytest runs and the project's code can be imported."""

from ingest.jikan import BASE_URL


def test_jikan_base_url_points_to_v4() -> None:
    assert BASE_URL == "https://api.jikan.moe/v4"
