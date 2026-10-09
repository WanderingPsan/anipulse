"""Load the prebuilt data files and answer lookups from them.

The API never queries Postgres. Everything it serves comes from three files that the
analysis and recommender commands write to data/processed/. Only `load_store` touches the
disk; the lookup functions take DataFrames and return plain dicts, so tests can call them
directly.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = "data/processed"
CATALOG_FILE = "catalog.parquet"
RECOMMENDATIONS_FILE = "recommendations.parquet"
METADATA_FILE = "metadata.json"

# The data license (ODbL) asks for this notice wherever the data is shown. It lives here, in a
# module with no web code, so the API and the dashboard share one copy and the dashboard
# never has to load the FastAPI app just to read a sentence.
ATTRIBUTION = (
    "Contains data from Anime Database (July 2025) by sazzadsiddiquelikhon on Kaggle, "
    "available under the ODbL v1.0. Original data from MyAnimeList via the Jikan API. "
    "Refreshed data from MyAnimeList via the Tenrai API."
)

# Columns shown for an anime in a search result or a recommendation (no tag lists).
SUMMARY_COLUMNS = ["mal_id", "title", "title_english", "type", "year", "score", "members"]


@dataclass(frozen=True)
class Store:
    """Everything the API serves, loaded once at startup."""

    catalog: pd.DataFrame  # one row per anime, indexed by mal_id
    recommendations: pd.DataFrame  # anime_id, rank, similar_id, similarity
    metadata: dict[str, Any]


def data_dir() -> Path:
    """The folder named by ANIPULSE_DATA_DIR (or .env), else data/processed."""
    load_dotenv()
    return Path(os.environ.get("ANIPULSE_DATA_DIR") or DEFAULT_DATA_DIR)


def load_store(folder: Path) -> Store:
    """Read the three files. Fails loudly, naming the file, if one is missing."""
    paths = [folder / name for name in (CATALOG_FILE, RECOMMENDATIONS_FILE, METADATA_FILE)]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing data files: {', '.join(missing)}")
    # mal_id stays a column too; the unnamed index is only for fast lookups by ID.
    catalog = pd.read_parquet(paths[0]).set_index("mal_id", drop=False).rename_axis(None)
    # Sorted once here so every lookup can just take the first k rows.
    recommendations = pd.read_parquet(paths[1]).sort_values(["anime_id", "rank"])
    metadata = json.loads(paths[2].read_text(encoding="utf-8"))
    logger.info("Loaded %d anime and %d recommendations", len(catalog), len(recommendations))
    return Store(catalog=catalog, recommendations=recommendations, metadata=metadata)


def plain(value: Any) -> Any:
    """Turn a pandas or numpy value into something JSON can hold.

    Parquet gives back numpy numbers, numpy arrays for the tag lists, and NaN or pd.NA for
    empty cells. Frieren's year 2023 arrives as a numpy integer; a title with no English
    name arrives as NaN and must become None (null in JSON).
    """
    if isinstance(value, (list, np.ndarray)):
        return [plain(item) for item in value]
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def row_dict(row: pd.Series, columns: list[str]) -> dict[str, Any]:
    """One catalog row as a dict with only the given columns."""
    return {column: plain(row[column]) for column in columns}


def find_anime(catalog: pd.DataFrame, mal_id: int) -> dict[str, Any] | None:
    """The full catalog entry for one anime, or None if the mal_id is unknown."""
    if mal_id not in catalog.index:
        return None
    return row_dict(catalog.loc[mal_id], list(catalog.columns))


def search(catalog: pd.DataFrame, query: str, limit: int) -> list[dict[str, Any]]:
    """Titles whose default or English title contains the query, ignoring case.

    Most-watched first, because "frieren" should show the main series before a recap.
    regex=False makes characters like "?" or "(" plain text, not pattern syntax.
    """
    in_title = catalog["title"].str.contains(query, case=False, regex=False, na=False)
    in_english = catalog["title_english"].str.contains(query, case=False, regex=False, na=False)
    matches = catalog[in_title | in_english].sort_values(
        ["members", "mal_id"], ascending=[False, True], na_position="last"
    )
    return [row_dict(row, SUMMARY_COLUMNS) for _, row in matches.head(limit).iterrows()]


def recommend(store: Store, mal_id: int, k: int) -> list[dict[str, Any]]:
    """Up to k recommendations for one anime, best first.

    Some titles have fewer than 10 (or none) because of the franchise and popularity rules,
    so this returns whatever exists. The stored "similarity" is renamed match_score: it is a
    rank within this title's own candidates, not a raw similarity.
    """
    recs = store.recommendations
    rows = recs[recs["anime_id"] == mal_id].head(k)
    results = []
    for rank, similar_id, similarity in zip(
        rows["rank"], rows["similar_id"], rows["similarity"], strict=True
    ):
        entry = row_dict(store.catalog.loc[similar_id], SUMMARY_COLUMNS)
        entry["rank"] = int(rank)
        entry["match_score"] = round(float(similarity), 4)
        results.append(entry)
    return results
