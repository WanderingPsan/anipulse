"""Pure helpers for the dashboard pages: DataFrames in, DataFrames or plain values out.

Nothing here touches Streamlit, the disk, or the network, so every function can be tested
with a tiny hand-made table. The pages only lay things out and draw.
"""

import numpy as np
import pandas as pd

from analysis.findings import factor_name

# Named under every chart. The full license notice sits in the sidebar of every page.
SOURCE_CAPTION = "Source: MyAnimeList data (Kaggle July 2025 snapshot, refreshed via Tenrai)."
POPULATION_NOTE = "Analysis population: scored titles with at least 1,000 members."


def score_histogram(scores: pd.Series, width: float = 0.25) -> pd.DataFrame:
    """Count scores into bins of equal width, labeled like "6.75-7.00".

    Bins start on a multiple of the width, so the edges are round numbers people can read.
    """
    known = scores.dropna()
    low = np.floor(known.min() / width) * width
    high = np.ceil(known.max() / width) * width + width
    edges = np.round(np.arange(low, high + width / 2, width), 2)
    counts, _ = np.histogram(known, bins=edges)
    starts = edges[:-1]
    return pd.DataFrame(
        {
            "bin_start": starts,
            "label": [f"{s:.2f}-{s + width:.2f}" for s in starts],
            "count": counts,
        }
    )


def bin_label_for(histogram: pd.DataFrame, value: float, width: float = 0.25) -> str:
    """The label of the histogram bin that holds a value (used to highlight the median)."""
    index = int(np.searchsorted(histogram["bin_start"].to_numpy(), value, side="right")) - 1
    return str(histogram["label"].iloc[max(index, 0)])


def best_group(groups: pd.DataFrame) -> pd.Series:
    """The group with the highest median score. Ties go to the larger group."""
    return groups.sort_values(["median", "n"], ascending=False).iloc[0]


def factor_test(tests: pd.DataFrame, factor: str) -> pd.Series:
    """The Question 1 test row for one factor (rho for Spearman, H for Kruskal-Wallis)."""
    rows = tests[(tests["question"] == "Q1") & (tests["factor"] == factor)]
    return rows.iloc[0]


def top_coefficients(coefficients: pd.DataFrame, k: int = 15) -> pd.DataFrame:
    """The k category and tag terms with the largest effect on score, in either direction.

    Only "factor=value" terms are kept. Their coefficient means "points of score compared
    with the reference group, holding everything else fixed", so they share one scale. The
    number terms (episodes, length, year) are per unit and would not compare fairly.
    """
    dummies = coefficients[coefficients["term"].str.contains("=", regex=False)].copy()
    dummies["name"] = dummies["term"].map(factor_name)
    dummies["size"] = dummies["coef"].abs()
    top = dummies.nlargest(k, "size")
    return top.sort_values("coef").reset_index(drop=True)


def range_restriction(top250: pd.DataFrame, tag_effects: pd.DataFrame) -> pd.DataFrame:
    """Each tag's score gap (with vs without the tag) in all titles and inside the top 250.

    Tags missing from the top 250 (no gap can be measured) are dropped.
    """
    merged = tag_effects[["factor", "difference"]].merge(
        top250[["factor", "difference_top250", "n_with_top250"]], on="factor"
    )
    merged = merged.dropna(subset=["difference_top250"])
    merged["name"] = merged["factor"].map(factor_name)
    merged["size"] = merged["difference"].abs()
    return merged.sort_values("size").reset_index(drop=True)


def list_options(catalog: pd.DataFrame, column: str) -> list[str]:
    """Every distinct value in a list column (genres or studios), sorted."""
    values = {item for items in catalog[column] for item in items}
    return sorted(values)


def filter_catalog(
    catalog: pd.DataFrame,
    types: list[str],
    year_range: tuple[int, int] | None,
    genre: str | None,
    studio: str | None,
    min_members: int,
) -> pd.DataFrame:
    """The titles that pass every filter. An empty or None filter means "don't filter".

    A title with no year is kept only when year_range is None, so the default view shows
    everything and narrowing the years never sneaks undated titles in.
    """
    keep = pd.Series(True, index=catalog.index)
    if types:
        keep &= catalog["type"].isin(types)
    if year_range is not None:
        keep &= catalog["year"].between(*year_range).fillna(False).astype(bool)
    if genre:
        keep &= catalog["genres"].map(lambda tags: genre in tags)
    if studio:
        keep &= catalog["studios"].map(lambda names: studio in names)
    if min_members > 0:
        keep &= (catalog["members"] >= min_members).fillna(False).astype(bool)
    return catalog[keep]


def shared_tags(query_tags: list[str], other_tags: list[str]) -> list[str]:
    """Tags two titles have in common, in alphabetical order."""
    return sorted(set(query_tags) & set(other_tags))
