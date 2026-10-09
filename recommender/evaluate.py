"""Measure the recommendations. Pure: DataFrames in, numbers out.

There are no "right answers" to check against, so we use proxies: do suggestions share a
genre with the query, and does the list reach beyond the same few famous shows?
"""

import numpy as np
import pandas as pd
from scipy import sparse

# Five well-known titles to read by eye: Frieren, Fullmetal Alchemist: Brotherhood,
# Steins;Gate, Shingeki no Kyojin, and Cowboy Bebop.
SPOT_CHECK_IDS = [52991, 5114, 9253, 16498, 1]


def tag_overlap(recs: pd.DataFrame, genres: pd.DataFrame) -> float:
    """Share of recommendations that share at least one genre with their query.

    Only queries that have a genre are counted; a title with no genres cannot overlap.
    """
    sets = genres.groupby("mal_id")["tag"].apply(frozenset).to_dict()
    scored = recs[recs["anime_id"].isin(sets)]
    shared = [
        bool(sets[q] & sets.get(s, frozenset()))
        for q, s in zip(scored["anime_id"], scored["similar_id"], strict=True)
    ]
    return sum(shared) / len(shared) if shared else 0.0


def coverage(recs: pd.DataFrame, n_titles: int) -> float:
    """Share of n_titles that appear in at least one title's recommendations."""
    return recs["similar_id"].nunique() / n_titles if n_titles else 0.0


def median_parts(
    recs: pd.DataFrame, ids: np.ndarray, text: sparse.csr_matrix, tags: sparse.csr_matrix
) -> dict[str, float]:
    """Median text cosine and tag cosine of the recommended pairs.

    Shows which half of the 0.7 / 0.3 blend actually decides the lists.
    """
    position = pd.Series(np.arange(len(ids)), index=ids)
    query = position[recs["anime_id"]].to_numpy()
    similar = position[recs["similar_id"]].to_numpy()
    text_cos = np.asarray(text[query].multiply(text[similar]).sum(axis=1)).ravel()
    tag_cos = np.asarray(tags[query].multiply(tags[similar]).sum(axis=1)).ravel()
    return {
        "median_text_cosine": round(float(np.median(text_cos)), 3),
        "median_tag_cosine": round(float(np.median(tag_cos)), 3),
    }


def spot_checks(
    recs: pd.DataFrame, titles: dict[int, str], ids: list[int], top: int = 5
) -> dict[str, list[str]]:
    """The top few recommended titles for each spot-check id that exists in the data."""
    result = {}
    for mal_id in ids:
        if mal_id not in titles:
            continue
        rows = recs[(recs["anime_id"] == mal_id) & (recs["rank"] <= top)]
        result[titles[mal_id]] = [titles[s] for s in rows.sort_values("rank")["similar_id"]]
    return result
