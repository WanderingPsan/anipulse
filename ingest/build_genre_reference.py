"""Write data/reference/mal_genres.json, the list of every MyAnimeList genre-like tag.

Run once with `python -m ingest.build_genre_reference` and commit the output, so later
builds never need the anime API to be up just to know that Adventure is genre 2.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import requests

from ingest.anime_api import get_genre_reference

REFERENCE_PATH = Path("data/reference/mal_genres.json")


def write_genre_reference(records: list[dict[str, Any]], path: Path) -> None:
    """Save the tags sorted by kind then ID, so re-running gives a clean git diff."""
    ordered = sorted(records, key=lambda r: (r["kind"], r["genre_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        records = get_genre_reference()
    except requests.RequestException as err:
        print(f"Could not reach the anime API, so nothing was written: {err}")
        return 1
    write_genre_reference(records, REFERENCE_PATH)
    print(f"Saved {len(records)} tags to {REFERENCE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
