"""Tests for writing the genre reference file."""

import json
from pathlib import Path

from ingest.build_genre_reference import write_genre_reference


def test_reference_is_sorted_by_kind_then_id(tmp_path: Path) -> None:
    records = [
        {"genre_id": 27, "name": "Shounen", "kind": "demographic"},
        {"genre_id": 8, "name": "Drama", "kind": "genre"},
        {"genre_id": 2, "name": "Adventure", "kind": "genre"},
    ]
    path = tmp_path / "reference" / "jikan_genres.json"

    write_genre_reference(records, path)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [r["genre_id"] for r in saved] == [27, 2, 8]
