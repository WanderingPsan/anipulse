"""Load the prebuilt data files once and keep them in Streamlit's cache.

The dashboard reads the same files as the API (data/processed/), not the API itself, and
not Postgres. A free API host sleeps when idle, and waking it can take 30 to 60 seconds,
which would stall a demo.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from api.data import Store, data_dir, load_store

ANALYSIS_TABLES = [
    "funnel",
    "tests",
    "factor_groups",
    "tag_effects",
    "ols_coefficients",
    "top250_tags",
    "numeric_bins",
]
SUMMARY_FILE = "summary.json"


@st.cache_data(show_spinner=False)
def cached_store(folder: str) -> Store:
    """The catalog, recommendations, and metadata (the API's loader, cached)."""
    return load_store(Path(folder))


@st.cache_data(show_spinner=False)
def cached_analysis(folder: str) -> dict[str, Any]:
    """Every chart-ready table from the analysis, plus the headline and key counts."""
    analysis_dir = Path(folder) / "analysis"
    paths = [analysis_dir / f"{name}.parquet" for name in ANALYSIS_TABLES]
    paths.append(analysis_dir / SUMMARY_FILE)
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing data files: {', '.join(missing)}")
    tables: dict[str, Any] = {
        name: pd.read_parquet(analysis_dir / f"{name}.parquet") for name in ANALYSIS_TABLES
    }
    tables["summary"] = json.loads(paths[-1].read_text(encoding="utf-8"))
    return tables


def store() -> Store:
    """The cached store, or a clear error on the page if a file is missing."""
    try:
        return cached_store(str(data_dir()))
    except FileNotFoundError as error:
        st.error(f"{error}. Run the pipeline, analysis, and recommender first.")
        st.stop()


def analysis() -> dict[str, Any]:
    """The cached analysis tables, or a clear error on the page if a file is missing."""
    try:
        return cached_analysis(str(data_dir()))
    except FileNotFoundError as error:
        st.error(f"{error}. Run `python -m analysis.run` first.")
        st.stop()
