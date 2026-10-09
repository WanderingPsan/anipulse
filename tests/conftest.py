"""Fixtures shared by several test files. pytest loads this file automatically."""

import os
from collections.abc import Iterator

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import Engine, create_engine, text

from db.models import Base

TEST_SCHEMA = "anipulse_test"


@pytest.fixture
def engine() -> Iterator[Engine]:
    """An engine whose tables live in a fresh, empty test schema."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is not set")
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
    # Every table name without a schema is quietly sent to the test schema instead.
    test_engine = admin.execution_options(schema_translate_map={None: TEST_SCHEMA})
    Base.metadata.create_all(test_engine)
    yield test_engine
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {TEST_SCHEMA} CASCADE"))
    admin.dispose()


@pytest.fixture(scope="session")
def synthetic_frames() -> dict[str, pd.DataFrame]:
    """Made-up query results for 300 anime, shaped like the real SQL output.

    Scores are built with known patterns (TV scores higher, Drama scores higher, more
    members means a higher score) so tests can check the analysis finds them.
    """
    rng = np.random.default_rng(0)
    n = 300
    mal_id = np.arange(1, n + 1)
    anime_type = rng.choice(["TV", "Movie", "OVA"], n)
    drama = rng.random(n) < 0.3
    score = 6.5 + 0.6 * (anime_type == "TV") + 0.4 * drama + rng.normal(0, 0.3, n)
    factors = pd.DataFrame(
        {
            "mal_id": mal_id,
            "score": score.round(2),
            "type": anime_type,
            "source": rng.choice(["Manga", "Original", None], n),
            "episodes": rng.integers(1, 50, n).astype(float),
            "duration_min": rng.integers(5, 30, n).astype(float),
            "rating": rng.choice(["PG-13 - Teens 13 or older", "G - All Ages"], n),
            "season": rng.choice(["winter", "spring", "summer", "fall"], n),
            "year": rng.integers(1990, 2026, n).astype(float),
            "demographic": rng.choice(["None", "Shounen"], n),
            "studio_group": rng.choice(["Madhouse", "Other", "Unknown"], n),
        }
    )
    tag_rows = [(i, "Drama", "genre") for i in mal_id[drama]]
    for name, kind in [("Action", "genre"), ("School", "theme"), ("Award Winning", "genre")]:
        tag_rows += [(i, name, kind) for i in mal_id[rng.random(n) < 0.4]]
    tags = pd.DataFrame(tag_rows, columns=["mal_id", "tag", "kind"])

    members = (np.exp(score) * rng.uniform(50, 150, n)).astype(int)
    popularity = pd.DataFrame({"mal_id": mal_id, "score": factors.score, "members": members})
    popularity["members_decile"] = pd.qcut(popularity.members, 10, labels=False) + 1

    top = factors.nlargest(60, "score")[["mal_id", "score"]]
    top["score_rank"] = np.arange(1, len(top) + 1)

    years = factors.groupby("year").score.agg(["size", "median", "mean"]).reset_index()
    by_year = pd.DataFrame(
        {
            "year": years.year.astype(int),
            "titles_in_catalog": years["size"] * 2,
            "titles_in_population": years["size"],
            "median_score": years["median"],
            "mean_score": years["mean"],
        }
    )
    return {
        "q1_factors": factors,
        "q1_tags": tags,
        "q2_popularity": popularity,
        "q3_top250": top,
        "q4_by_year": by_year,
    }
