"""Match tag names from the data to MyAnimeList's official tag list."""

from typing import Any, NamedTuple

from transform.aliases import TAG_ALIASES


class TagMatch(NamedTuple):
    """Which tags we found an ID for, and which names we could not match."""

    genre_ids: list[int]
    unmatched: list[str]


def build_tag_lookup(reference: list[dict[str, Any]]) -> dict[str, int]:
    """Turn the reference list into {"Adventure": 2, ...} for fast lookups by name."""
    return {tag["name"]: tag["genre_id"] for tag in reference}


def classify_tags(names: list[str], lookup: dict[str, int]) -> TagMatch:
    """Find the genre ID for each tag name, trying the alias dict when the name is old.

    Unmatched names are returned, not dropped, so the pipeline can log and count them.
    Duplicates are removed because one anime has each tag once.
    """
    genre_ids: list[int] = []
    unmatched: list[str] = []
    for name in names:
        genre_id = lookup.get(name)
        if genre_id is None:
            genre_id = lookup.get(TAG_ALIASES.get(name, ""))
        if genre_id is None:
            unmatched.append(name)
        elif genre_id not in genre_ids:
            genre_ids.append(genre_id)
    return TagMatch(genre_ids, unmatched)
