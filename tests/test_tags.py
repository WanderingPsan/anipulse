"""Tests for matching tag names to MyAnimeList's tag IDs."""

from transform.tags import build_tag_lookup, classify_tags

REFERENCE = [
    {"genre_id": 2, "name": "Adventure", "kind": "genre"},
    {"genre_id": 8, "name": "Drama", "kind": "genre"},
    {"genre_id": 26, "name": "Girls Love", "kind": "genre"},
    {"genre_id": 27, "name": "Shounen", "kind": "demographic"},
]
LOOKUP = build_tag_lookup(REFERENCE)


def test_frieren_tags_match_their_ids() -> None:
    match = classify_tags(["Adventure", "Drama", "Shounen"], LOOKUP)
    assert match.genre_ids == [2, 8, 27]
    assert match.unmatched == []


def test_renamed_tag_matches_through_alias() -> None:
    assert classify_tags(["Shoujo Ai"], LOOKUP).genre_ids == [26]


def test_unknown_tag_is_reported_not_dropped() -> None:
    match = classify_tags(["Adventure", "Made Up Tag"], LOOKUP)
    assert match.genre_ids == [2]
    assert match.unmatched == ["Made Up Tag"]


def test_repeated_tag_is_kept_once() -> None:
    assert classify_tags(["Drama", "Drama"], LOOKUP).genre_ids == [8]
