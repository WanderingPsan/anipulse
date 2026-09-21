import json
from pathlib import Path

from ingest.jikan import get_top_anime

RAW_DIR = Path("data/raw")


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    anime = get_top_anime(pages=1)  # 4 pages x 25 = 100 titles
    out_path = RAW_DIR / "top_anime.json"
    out_path.write_text(json.dumps(anime, indent=2))
    print(f"Saved {len(anime)} anime to {out_path}")


if __name__ == "__main__":
    main()
