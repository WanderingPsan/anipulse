"""Turn synopses and tags into vectors. Pure: lists in, sparse matrices out.

Every row is scaled to length 1 (L2-normalized), so the dot product of two rows is their
cosine similarity: 1 means "pointing the same way", 0 means "nothing in common".
"""

import re

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer, normalize

from analysis.questions import POST_RELEASE_TAGS

MIN_MEMBERS = 1000
TAG_KINDS = frozenset({"genre", "theme", "demographic"})
# MyAnimeList fills empty synopses with a stock sentence. Every placeholder would share the
# same words, so treating it as text would make unrelated shows look alike.
PLACEHOLDER_SYNOPSIS = re.compile(r"^\s*no synopsis (information )?has been added", re.IGNORECASE)


def is_placeholder(synopsis: str | None) -> bool:
    """True when a synopsis is missing, blank, or MyAnimeList's stock placeholder."""
    if synopsis is None or pd.isna(synopsis) or not synopsis.strip():
        return True
    return bool(PLACEHOLDER_SYNOPSIS.match(synopsis))


def count_placeholders(synopses: list[str | None]) -> int:
    """How many synopses are the stock placeholder sentence (logged, and kept in the eval)."""
    return sum(1 for s in synopses if isinstance(s, str) and PLACEHOLDER_SYNOPSIS.match(s))


def clean_synopses(synopses: list[str | None]) -> list[str]:
    """Replace missing and placeholder synopses with "" so they become all-zero rows."""
    return ["" if is_placeholder(s) else s for s in synopses]


def text_matrix(synopses: list[str]) -> sparse.csr_matrix:
    """TF-IDF of each synopsis. An empty synopsis gives a row of zeros.

    A zero row has similarity 0 with everything, which is exactly the rule we want:
    text similarity is 0 when either title has no synopsis.
    """
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_features=30_000,
        dtype=np.float32,
    )
    # TfidfVectorizer already L2-normalizes rows (norm="l2" is its default).
    return vectorizer.fit_transform(synopses).tocsr()


def recommender_tags(tags: pd.DataFrame) -> pd.DataFrame:
    """Keep genre, theme, and demographic links, minus post-release tags like Award Winning."""
    keep = tags["kind"].isin(TAG_KINDS) & ~tags["tag"].isin(POST_RELEASE_TAGS)
    return tags[keep]


def tag_lists(mal_ids: list[int], tags: pd.DataFrame) -> list[list[str]]:
    """One list of tag names per anime, in the same order as mal_ids (empty if none)."""
    grouped = tags.groupby("mal_id")["tag"].apply(sorted).to_dict()
    return [grouped.get(mal_id, []) for mal_id in mal_ids]


def tag_matrix(lists: list[list[str]]) -> sparse.csr_matrix:
    """Multi-hot tags (one column per tag, 1 if the anime has it), each row scaled to length 1."""
    binarizer = MultiLabelBinarizer(sparse_output=True)
    multi_hot = binarizer.fit_transform(lists).astype(np.float32)
    return normalize(multi_hot, norm="l2").tocsr()


def recommendable(scores: pd.Series, members: pd.Series) -> np.ndarray:
    """Titles allowed to appear as a suggestion: scored and watched by at least 1,000 people."""
    return (scores.notna() & (members.fillna(0) >= MIN_MEMBERS)).to_numpy()
