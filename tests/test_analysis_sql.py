"""The analysis SQL runs against a real (test) database and agrees with itself.

Marked `db`: the `engine` fixture skips these when DATABASE_URL is not set.
"""

import pandas as pd
import pytest
from sqlalchemy import Engine, text

from analysis.run import QUERIES, run_queries
from db.load import load_records
from pipeline.run import read_reference
from tests.conftest import TEST_SCHEMA
from tests.test_load import api_fixture_records, kaggle_fixture_records

pytestmark = pytest.mark.db


@pytest.fixture
def frames(engine: Engine) -> dict[str, pd.DataFrame]:
    """Load both fixtures into the test schema, then run every analysis query on it."""
    reference = read_reference()
    load_records(engine, kaggle_fixture_records(), reference)
    load_records(engine, api_fixture_records(), reference)
    with engine.connect() as conn:
        # The SQL files name tables without a schema, so point them at the test schema.
        conn.execute(text(f"SET search_path TO {TEST_SCHEMA}"))
        return run_queries(conn, QUERIES)


def test_funnel_ends_at_the_population_size(frames: dict[str, pd.DataFrame]) -> None:
    funnel = frames["funnel"].iloc[0]

    assert funnel.in_database == len(frames["database_ids"])
    assert funnel.in_database >= funnel.has_score >= funnel.enough_members >= funnel.has_aired
    assert funnel.has_aired == len(frames["q1_factors"]) == len(frames["q2_popularity"])


def test_factor_query_has_no_outcome_columns(frames: dict[str, pd.DataFrame]) -> None:
    columns = set(frames["q1_factors"].columns)

    assert not columns & {"members", "scored_by", "favorites"}
    assert frames["q1_factors"]["studio_group"].notna().all()


def test_frieren_is_in_the_population_with_its_tags(frames: dict[str, pd.DataFrame]) -> None:
    factors = frames["q1_factors"].set_index("mal_id")
    frieren_tags = set(frames["q1_tags"].query("mal_id == 52991").tag)

    assert factors.loc[52991, "demographic"] == "Shounen"
    assert factors.loc[52991, "studio_group"] == "Madhouse"
    assert {"Adventure", "Drama", "Fantasy"} <= frieren_tags


def test_catalog_lists_tags_and_studios(frames: dict[str, pd.DataFrame]) -> None:
    catalog = frames["catalog"].set_index("mal_id")

    assert "Madhouse" in catalog.loc[52991, "studios"]
    assert "Shounen" in catalog.loc[52991, "genres"]
