"""Read the Kaggle "Anime Database (July 2025)" CSV into a DataFrame with our column names."""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path("data/source/anime_july_2025.zip")

# CSV column name -> our column name. The dataset already uses Jikan's field names, so this
# is an identity mapping today. It still earns its place: it is the one list of columns we
# keep (image_*, trailer_*, aired_prop_*, rank, popularity and others are left out), and the
# one place to change if the source ever renames a column.
COLUMN_MAP: dict[str, str] = {
    "mal_id": "mal_id",
    "title": "title",
    "title_english": "title_english",
    "type": "type",
    "source": "source",
    "episodes": "episodes",
    "status": "status",
    "duration": "duration",
    "rating": "rating",
    "score": "score",
    "scored_by": "scored_by",
    "members": "members",
    "favorites": "favorites",
    "synopsis": "synopsis",
    "aired_from": "aired_from",
    "season": "season",
    "year": "year",
    "broadcast_day": "broadcast_day",
    "broadcast_time": "broadcast_time",
    "producers": "producers",
    "licensors": "licensors",
    "studios": "studios",
    "genres": "genres",
    "explicit_genres": "explicit_genres",
    "themes": "themes",
    "demographics": "demographics",
}

# pandas turns a whole-number column into floats when any cell is empty (episodes = 28.0).
# "Int64" is pandas' nullable integer type, so Frieren keeps episodes = 28 and an unknown
# count stays empty (<NA>) instead of becoming NaN.
INTEGER_COLUMNS = ["mal_id", "episodes", "scored_by", "members", "favorites", "year"]


class MissingColumnsError(ValueError):
    """The CSV does not have every column COLUMN_MAP expects."""


def find_missing_columns(columns: list[str]) -> list[str]:
    """Return the expected CSV columns that are not in `columns`, in COLUMN_MAP order."""
    present = set(columns)
    return [name for name in COLUMN_MAP if name not in present]


def read_kaggle_csv(path: Path = DEFAULT_PATH) -> pd.DataFrame:
    """Load the Kaggle CSV (zipped or plain), keep the mapped columns, and rename them.

    Reads the header first so a renamed or missing column fails with a clear message
    before pandas loads 28,000 rows.
    """
    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing = find_missing_columns(header)
    if missing:
        raise MissingColumnsError(f"{path} is missing required columns: {', '.join(missing)}")

    df = pd.read_csv(path, usecols=list(COLUMN_MAP))
    df = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    df = df.astype({name: "Int64" for name in INTEGER_COLUMNS})
    logger.info("Read %d rows from %s", len(df), path)
    return df
