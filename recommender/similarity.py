"""Find each anime's closest neighbors without ever building the full similarity table.

With 27,000 titles, a full table would hold 27,000 x 27,000 numbers (about 6 GB as 64-bit
floats). Instead we take 1,000 query titles at a time, score them against everyone, keep
the best few per row, and throw the rest away before the next chunk.
"""

import logging

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import rankdata

from recommender.franchise import KEY_WORDS, franchise_key, title_words

logger = logging.getLogger(__name__)

TEXT_WEIGHT = 0.7
TAG_WEIGHT = 0.3
DEFAULT_K = 10
CHUNK_SIZE = 1000
# How many candidates per wanted slot to take before dropping repeats of a franchise.
FRANCHISE_POOL = 5


def franchise_codes(titles: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Turn titles into integer codes so the franchise rule can be checked on whole arrays.

    Returns (first-word code, first-two-words code, number of key words) per title.
    A code of -1 means "no such key", which never equals a real code.
    """
    words = [title_words(t)[:KEY_WORDS] for t in titles]
    one = pd.Series([w[0] if w else None for w in words], dtype=object)
    two = pd.Series([" ".join(w) if len(w) == KEY_WORDS else None for w in words], dtype=object)
    return pd.factorize(one)[0], pd.factorize(two)[0], np.array([len(w) for w in words])


def franchise_mask(
    rows: np.ndarray, codes: tuple[np.ndarray, ...], columns: np.ndarray
) -> np.ndarray:
    """True where a candidate column starts with the same key words as the query row.

    Same rule as franchise.same_franchise, checked for a whole chunk at once.
    """
    one, two, n_words = codes
    by_two = two[rows][:, None] == two[columns][None, :]
    by_one = one[rows][:, None] == one[columns][None, :]
    mask = np.where((n_words[rows] == KEY_WORDS)[:, None], by_two, by_one)
    # A title made only of filler words has no key, so it hides nobody.
    return mask & (n_words[rows] > 0)[:, None]


def franchise_keys(titles: list[str]) -> np.ndarray:
    """One integer per title for its franchise key, so a list can hold one title per key.

    Two titles share a code only when their keys are exactly equal. A title with no key
    words gets a code of its own, so it is never grouped with anything.
    """
    keys = pd.Series([franchise_key(t) or None for t in titles], dtype=object)
    codes = pd.factorize(keys)[0]
    no_key = codes == -1
    codes[no_key] = codes.max() + 1 + np.arange(no_key.sum())
    return codes


def cosines(
    text: sparse.csr_matrix, tags: sparse.csr_matrix, rows: np.ndarray, columns: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Raw text cosine and tag cosine for each query row against the candidate columns."""
    text_sim = np.asarray((text[rows] @ text[columns].T).todense())
    tag_sim = np.asarray((tags[rows] @ tags[columns].T).todense())
    return text_sim, tag_sim


def rank_rescale(scores: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """Replace each allowed score by its percentile rank in its row, from 0 (worst) to 1 (best).

    Text and tag cosines live on very different scales, so blending them raw lets tags
    decide almost everything. Ranks put both on the same 0-to-1 scale, and unlike stretching
    by the lowest and highest value, one near-duplicate cannot squash everyone else toward 0.
    Ties share the average rank. Masked candidates get 0 and are not counted. A row where
    every allowed score is equal cannot tell candidates apart, so it becomes all 0.
    """
    low = np.where(allowed, scores, np.inf).min(axis=1, keepdims=True)
    high = np.where(allowed, scores, -np.inf).max(axis=1, keepdims=True)
    # Masked candidates are set below every real score, so they take the lowest ranks
    # and the allowed ones start right after them.
    ranks = rankdata(np.where(allowed, scores, -np.inf), method="average", axis=1)
    n_masked = (~allowed).sum(axis=1, keepdims=True)
    n_allowed = allowed.shape[1] - n_masked
    percentile = (ranks - n_masked - 1) / np.maximum(n_allowed - 1, 1)
    return np.where(allowed & (high > low), percentile, 0.0)


def blended_scores(
    text_sim: np.ndarray, tag_sim: np.ndarray, allowed: np.ndarray, both_have_text: np.ndarray
) -> np.ndarray:
    """0.7 x text rank + 0.3 x tag rank, with both ranks taken among the allowed candidates.

    One formula for every pair. When either title has no synopsis, the text part is 0, so
    the pair can reach at most 0.3 and never jump ahead on tags alone.
    """
    text_part = np.where(both_have_text, rank_rescale(text_sim, allowed), 0.0)
    tag_part = rank_rescale(tag_sim, allowed)
    return (TEXT_WEIGHT * text_part + TAG_WEIGHT * tag_part).astype(np.float32)


def best_k(scores: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Row and column positions of the k highest finite scores in each row, best first.

    argpartition finds the k-th best score per row without fully sorting 27,000 numbers.
    Every candidate at or above it is then sorted by (score high to low, column low to high),
    so ties always break toward the lower mal_id and the output never changes between runs.
    """
    k = min(k, scores.shape[1])
    top = np.argpartition(scores, -k, axis=1)[:, -k:]
    threshold = np.take_along_axis(scores, top, axis=1).min(axis=1)
    candidates = (scores >= threshold[:, None]) & np.isfinite(scores)
    row, col = np.nonzero(candidates)
    order = np.lexsort((col, -scores[row, col], row))
    row, col = row[order], col[order]
    keep = position_in_row(row) < k
    return row[keep], col[keep]


def position_in_row(row: np.ndarray) -> np.ndarray:
    """0 for the first entry of each row, 1 for the next, and so on (rows must be sorted)."""
    return np.arange(len(row)) - np.searchsorted(row, row, side="left")


def one_per_franchise(
    row: np.ndarray, col: np.ndarray, keys: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray]:
    """Keep only the best-ranked candidate per franchise key in each row, then the first k.

    Input must be sorted best first within each row, as best_k returns it.
    """
    first_of_key = ~pd.DataFrame({"row": row, "key": keys[col]}).duplicated().to_numpy()
    row, col = row[first_of_key], col[first_of_key]
    keep = position_in_row(row) < k
    return row[keep], col[keep]


def top_k(
    ids: np.ndarray,
    text: sparse.csr_matrix,
    tags: sparse.csr_matrix,
    eligible: np.ndarray,
    titles: list[str],
    k: int = DEFAULT_K,
    chunk_size: int = CHUNK_SIZE,
    query_rows: np.ndarray | None = None,
    skip_franchise: bool = True,
) -> pd.DataFrame:
    """Top k recommendations for each query title.

    Any title can be a query. Only `eligible` titles can be recommended, so only they are
    scored and ranked. A title never recommends itself, never a title in its own franchise,
    never two titles from one franchise, and never a title it shares nothing with. If fewer
    than k are left, it gets fewer rows.
    """
    n = len(ids)
    rows_to_score = np.arange(n) if query_rows is None else np.asarray(query_rows)
    columns = np.flatnonzero(eligible)
    # Where each title sits among the candidate columns (-1 if it is not a candidate).
    column_of = np.full(n, -1)
    column_of[columns] = np.arange(len(columns))
    codes = franchise_codes(titles)
    keys = franchise_keys(titles)[columns]
    has_text = np.diff(text.indptr) > 0
    # Take extra candidates so the list can still reach k after repeats of a franchise go.
    wide = FRANCHISE_POOL * k if skip_franchise else k
    parts = []
    for start in range(0, len(rows_to_score), chunk_size):
        rows = rows_to_score[start : start + chunk_size]
        text_sim, tag_sim = cosines(text, tags, rows, columns)
        allowed = np.ones(text_sim.shape, dtype=bool)
        is_candidate = column_of[rows] >= 0
        allowed[np.flatnonzero(is_candidate), column_of[rows[is_candidate]]] = False
        if skip_franchise:
            allowed &= ~franchise_mask(rows, codes, columns)
        both_have_text = has_text[rows][:, None] & has_text[columns][None, :]
        scores = blended_scores(text_sim, tag_sim, allowed, both_have_text)
        # A pair that shares no word and no tag is never recommended.
        scores[~allowed | (text_sim + tag_sim <= 0)] = -np.inf
        row, col = best_k(scores, wide)
        if skip_franchise:
            row, col = one_per_franchise(row, col, keys, k)
        parts.append(
            pd.DataFrame(
                {
                    "anime_id": ids[rows[row]],
                    "rank": position_in_row(row) + 1,
                    "similar_id": ids[columns[col]],
                    "similarity": scores[row, col].round(4),
                }
            )
        )
        logger.info("Scored %d of %d titles", min(start + chunk_size, len(rows_to_score)), n)
    return pd.concat(parts, ignore_index=True).astype(
        {"anime_id": "int64", "rank": "int64", "similar_id": "int64", "similarity": "float32"}
    )
