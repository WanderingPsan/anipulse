"""Database tests: loading is repeatable, links are replaced, and the live API wins.

They need PostgreSQL, so they are marked `db` and skipped when DATABASE_URL is not set. They
work in a throwaway schema called anipulse_test, so they never touch the real tables.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, select, text

from db.load import count_rows, load_records
from db.models import Anime, AnimeCompany, AnimeGenre, Base, Company, PipelineRun
from ingest.kaggle import read_kaggle_csv
from pipeline.run import RunSummary, prepare, read_reference, run
from transform.records import flatten_jikan_anime, kaggle_row_to_record

pytestmark = pytest.mark.db

FIXTURES = Path(__file__).parent / "fixtures"
KAGGLE_CSV = FIXTURES / "kaggle_sample.csv"
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


@pytest.fixture(scope="module")
def reference() -> list[dict]:
    return read_reference()


def kaggle_fixture_records() -> list[dict]:
    rows = read_kaggle_csv(KAGGLE_CSV).to_dict("records")
    return prepare([kaggle_row_to_record(row) for row in rows], RunSummary())


def api_fixture_records() -> list[dict]:
    raw = json.loads((FIXTURES / "jikan_top_anime_page1.json").read_text(encoding="utf-8"))
    return prepare([flatten_jikan_anime(anime) for anime in raw], RunSummary())


def test_loading_twice_gives_identical_row_counts(engine: Engine, reference: list[dict]) -> None:
    load_records(engine, kaggle_fixture_records(), reference)
    load_records(engine, api_fixture_records(), reference)
    first = count_rows(engine)

    load_records(engine, kaggle_fixture_records(), reference)
    load_records(engine, api_fixture_records(), reference)

    assert count_rows(engine) == first
    assert first["anime"] > 0 and first["anime_genres"] > 0


def test_join_rows_are_replaced_on_reload(engine: Engine, reference: list[dict]) -> None:
    frieren = next(r for r in kaggle_fixture_records() if r["mal_id"] == 52991)
    load_records(engine, [frieren], reference)

    changed = frieren | {"tags": ["Comedy"], "companies": frieren["companies"][:1]}
    load_records(engine, [changed], reference, batch_size=1)

    with engine.connect() as conn:
        genre_ids = conn.scalars(select(AnimeGenre.genre_id).where(AnimeGenre.anime_id == 52991))
        companies = conn.scalars(
            select(AnimeCompany.company_id).where(AnimeCompany.anime_id == 52991)
        ).all()
    assert list(genre_ids) == [4]  # Comedy is genre 4; Adventure, Drama, and others are gone
    assert len(companies) == 1


def test_api_record_overrides_kaggle_record(engine: Engine, reference: list[dict]) -> None:
    load_records(engine, kaggle_fixture_records(), reference)
    load_records(engine, api_fixture_records(), reference)

    with engine.connect() as conn:
        frieren = conn.execute(select(Anime).where(Anime.mal_id == 52991)).one()
        madhouse_id = conn.scalar(select(Company.mal_id).where(Company.name == "Madhouse"))
        # 59193 has no season in the CSV (the month rule says winter); the API says summer.
        season = conn.scalar(select(Anime.season).where(Anime.mal_id == 59193))
    assert frieren.data_source == "api"
    assert madhouse_id == 11  # only the API knows company IDs
    assert season == "summer"


def test_kaggle_reload_keeps_company_ids_from_the_api(
    engine: Engine, reference: list[dict]
) -> None:
    load_records(engine, api_fixture_records(), reference)
    load_records(engine, kaggle_fixture_records(), reference)

    with engine.connect() as conn:
        assert conn.scalar(select(Company.mal_id).where(Company.name == "Madhouse")) == 11


def test_run_records_itself_in_pipeline_runs(
    engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = run(engine, base="csv", api_pages=0, csv_path=KAGGLE_CSV)

    with engine.connect() as conn:
        logged = conn.execute(select(PipelineRun)).one()
    assert exit_code == 0
    assert logged.status == "success"
    assert logged.anime_upserted == 20  # 21 rows minus one Rx title
    assert "Rx titles dropped: 1" in capsys.readouterr().out


def test_run_fails_with_exit_code_when_base_load_fails(engine: Engine, tmp_path: Path) -> None:
    exit_code = run(engine, base="csv", api_pages=0, csv_path=tmp_path / "missing.csv")

    with engine.connect() as conn:
        assert conn.scalar(select(PipelineRun.status)) == "failed"
    assert exit_code == 1
