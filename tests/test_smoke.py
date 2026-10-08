"""A smoke test: proves pytest runs and the project's code can be imported."""

import pytest

from ingest.anime_api import DEFAULT_BASE_URL, base_url_from_env


def test_base_url_defaults_to_tenrai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANIME_API_BASE_URL", raising=False)
    assert base_url_from_env() == DEFAULT_BASE_URL == "https://api.tenrai.org/v1"


def test_base_url_comes_from_env_without_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANIME_API_BASE_URL", "http://localhost:8080/v4/")
    assert base_url_from_env() == "http://localhost:8080/v4"
