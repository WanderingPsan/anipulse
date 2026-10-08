"""Smoke command: fetch top anime from the anime API and save them to data/raw/top_anime.json.

Run with `python -m ingest.run_fetch`. It proves the client works against the live API.
"""

import json
import logging
import sys
from pathlib import Path

from ingest.anime_api import get_top_anime

RAW_DIR = Path("data/raw")
# On Day 1, Jikan returned repeated 504 errors for page 2, so the smoke test asks for one
# page (25 anime).
PAGES = 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = get_top_anime(pages=PAGES)
    if not result.items:
        print(f"The API failed for every page requested ({result.failed_pages}). Nothing saved.")
        return 1
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "top_anime.json"
    out_path.write_text(json.dumps(result.items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(result.items)} anime to {out_path}. Failed pages: {result.failed_pages}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
