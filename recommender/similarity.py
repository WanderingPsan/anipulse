"""Find each anime's closest neighbors without ever building the full similarity table.

With 27,000 titles, a full table would hold 27,000 x 27,000 numbers (about 6 GB as 64-bit
floats). Instead we take 1,000 query titles at a time, score them against everyone, keep
the best few per row, and throw the rest away before the next chunk.
"""

import logging

import numpy as np
import pandas as pd
from scipy import sparse

from recommender.franchise import KEY_WORDS, title_words

logger = logging.getLogger(__name__)

TEXT_WEIGHT = 0.7
TAG_WEIGHT = 0.3
DEFAULT_K = 10
CHUNK_SIZE = 1000


def franchise_codes(titles: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Turn titles into integer codes so the franchise rule can be checked on whole arrays.

    Returns (first-word code, first-two-words code, number of key words) per title.
    A code of -1 means "no such key", which never equals a real code.
    """
    words = [title_words(t)[:KEY_WORDS] for t in titles]
    one = pd.Series([w[0] if w else None for w in words], dtype=object)
    two = pd.Series([" ".join(w) if len(w) == KEY_WORDS else None for w in words], dtype=object)
    return pd.factorize(one)[0], pd.factorize(two)[0], np.array([len(w) for w in words])


def franchise_mask(rows: np.ndarray, codes: tuple[np.ndarray, ...]) -> np.ndarray:
    """True where a candidate starts with the same key words as the query row.

    Same rule as franchise.same_franchise, checked for a whole chunk at once.
    """
    one, two, n_words = codes
    by_two = two[rows][:, None] == two[None, :]
    by_one = one[rows][:, None] == one[None, :]
    mask = np.where((n_words[rows] == KEY_WORDS)[:, None], by_two, by_one)
    # A title made only of filler words has no key, so it hides nobody.
    return mask & (n_words[rows] > 0)[:, None]


def blended_scores(
    text: sparse.csr_matrix, tags: sparse.csr_matrix, rows: np.ndarray
) -> np.ndarray:
    """0.7 x text cosine + 0.3 x tag cosine for each query row against every title.

    One formula for every pair. A title with no synopsis has an all-zero text row, so its
    text part is 0 and it can only reach 0.3, never jump ahead on tags alone.
    """
    scores = TEXT_WEIGHT * (text[rows] @ text.T) + TAG_WEIGHT * (tags[rows] @ tags.T)
    return np.asarray(scores.todense(), dtype=np.float32)


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
    # Position within each row: 0 for the best, 1 for the next, and so on.
    first = np.searchsorted(row, row, side="left")
    keep = np.arange(len(row)) - first < k
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

    Any title can be a query. Only `eligible` titles can be recommended. A title never
    recommends itself, never a title in its own franchise, and never a title it shares
    nothing with (score 0). If fewer than k are left, it gets fewer rows.
    """
    n = len(ids)
    rows_to_score = np.arange(n) if query_rows is None else np.asarray(query_rows)
    codes = franchise_codes(titles)
    blocked = ~eligible
    parts = []
    for start in range(0, len(rows_to_score), chunk_size):
        rows = rows_to_score[start : start + chunk_size]
        scores = blended_scores(text, tags, rows)
        scores[:, blocked] = -np.inf
        scores[np.arange(len(rows)), rows] = -np.inf
        if skip_franchise:
            scores[franchise_mask(rows, codes)] = -np.inf
        scores[scores <= 0] = -np.inf
        row, col = best_k(scores, k)
        rank = np.arange(len(row)) - np.searchsorted(row, row, side="left") + 1
        parts.append(
            pd.DataFrame(
                {
                    "anime_id": ids[rows[row]],
                    "rank": rank,
                    "similar_id": ids[col],
                    "similarity": scores[row, col].round(4),
                }
            )
        )
        logger.info("Scored %d of %d titles", min(start + chunk_size, len(rows_to_score)), n)
    return pd.concat(parts, ignore_index=True).astype(
        {"anime_id": "int64", "rank": "int64", "similar_id": "int64", "similarity": "float32"}
    )
