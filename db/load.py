"""Write clean records into Postgres.

Every write is an upsert ("insert, or update if it is already there"), so loading the same
data twice leaves the database exactly as it was after the first load.
"""

import logging
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, Engine, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from db.models import Anime, AnimeCompany, AnimeGenre, Company, Genre, PipelineRun
from transform.records import ANIME_COLUMNS
from transform.tags import build_tag_lookup, classify_tags

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


@dataclass
class LoadStats:
    """What one load did. unmatched_tags counts each tag name we could not find an ID for."""

    anime_upserted: int = 0
    unmatched_tags: Counter[str] = field(default_factory=Counter)


def seed_genres(conn: Connection, reference: list[dict[str, Any]]) -> int:
    """Upsert every tag from the reference file, so the join table always has IDs to point at."""
    stmt = insert(Genre).values(reference)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Genre.genre_id],
        set_={"name": stmt.excluded.name, "kind": stmt.excluded.kind},
    )
    conn.execute(stmt)
    return len(reference)


def _batches(records: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    """Yield the records in chunks of `size`."""
    for start in range(0, len(records), size):
        yield records[start : start + size]


def _upsert_anime(conn: Connection, records: list[dict[str, Any]], now: datetime) -> None:
    """Insert new anime and overwrite existing ones with the newer values."""
    rows = [{col: r[col] for col in ANIME_COLUMNS} | {"updated_at": now} for r in records]
    stmt = insert(Anime)
    update_cols = {col: stmt.excluded[col] for col in ANIME_COLUMNS if col != "mal_id"}
    update_cols["updated_at"] = stmt.excluded.updated_at
    conn.execute(stmt.on_conflict_do_update(index_elements=["mal_id"], set_=update_cols), rows)


def _upsert_companies(conn: Connection, records: list[dict[str, Any]]) -> dict[str, int]:
    """Make sure every company in the batch exists, and return {name: company_id}.

    A company's MyAnimeList ID is filled in when the API gives one, and is never erased by a
    CSV row that does not know it (COALESCE keeps the first non-empty value).
    """
    mal_ids: dict[str, int | None] = {}
    for record in records:
        for ref in record["companies"]:
            if mal_ids.get(ref.name) is None:
                mal_ids[ref.name] = ref.mal_id
    if not mal_ids:
        return {}
    stmt = insert(Company).values([{"name": n, "mal_id": m} for n, m in mal_ids.items()])
    stmt = stmt.on_conflict_do_update(
        index_elements=[Company.name],
        set_={"mal_id": func.coalesce(stmt.excluded.mal_id, Company.mal_id)},
    ).returning(Company.name, Company.company_id)
    return {name: company_id for name, company_id in conn.execute(stmt)}


def _replace_join_rows(
    conn: Connection,
    records: list[dict[str, Any]],
    tag_lookup: dict[str, int],
    company_ids: dict[str, int],
    stats: LoadStats,
) -> None:
    """Delete this batch's old genre and company links, then insert the current ones.

    Delete-then-insert is simpler than working out which links changed, and because it runs
    in the batch's transaction, nobody ever sees an anime with no links halfway through.
    """
    anime_ids = [r["mal_id"] for r in records]
    conn.execute(delete(AnimeGenre).where(AnimeGenre.anime_id.in_(anime_ids)))
    conn.execute(delete(AnimeCompany).where(AnimeCompany.anime_id.in_(anime_ids)))

    genre_rows = []
    company_rows = set()
    for record in records:
        match = classify_tags(record["tags"], tag_lookup)
        stats.unmatched_tags.update(match.unmatched)
        genre_rows += [{"anime_id": record["mal_id"], "genre_id": g} for g in match.genre_ids]
        for ref in record["companies"]:
            company_rows.add((record["mal_id"], company_ids[ref.name], ref.role))

    if genre_rows:
        conn.execute(insert(AnimeGenre), genre_rows)
    if company_rows:
        conn.execute(
            insert(AnimeCompany),
            [{"anime_id": a, "company_id": c, "role": r} for a, c, r in sorted(company_rows)],
        )


def load_records(
    engine: Engine,
    records: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    batch_size: int = BATCH_SIZE,
) -> LoadStats:
    """Load records in batches, one transaction per batch.

    Records must already be filtered (no Rx titles) and have unique mal_ids.
    """
    stats = LoadStats()
    tag_lookup = build_tag_lookup(reference)
    now = datetime.now(UTC)
    with engine.begin() as conn:
        seed_genres(conn, reference)
    for batch in _batches(records, batch_size):
        with engine.begin() as conn:  # commits at the end of the block, rolls back on error
            _upsert_anime(conn, batch, now)
            company_ids = _upsert_companies(conn, batch)
            _replace_join_rows(conn, batch, tag_lookup, company_ids, stats)
        stats.anime_upserted += len(batch)
    for name, count in stats.unmatched_tags.items():
        logger.warning("Tag %r matched no reference tag (%d anime)", name, count)
    return stats


def start_run(engine: Engine, base_source: str, api_pages_requested: int) -> int:
    """Log that a run began and return its run_id."""
    with engine.begin() as conn:
        return conn.execute(
            insert(PipelineRun)
            .values(
                started_at=datetime.now(UTC),
                base_source=base_source,
                api_pages_requested=api_pages_requested,
                status="running",
            )
            .returning(PipelineRun.run_id)
        ).scalar_one()


def finish_run(
    engine: Engine,
    run_id: int,
    status: str,
    anime_upserted: int,
    api_pages_failed: int,
    message: str,
) -> None:
    """Fill in how the run ended."""
    with engine.begin() as conn:
        conn.execute(
            update(PipelineRun)
            .where(PipelineRun.run_id == run_id)
            .values(
                finished_at=datetime.now(UTC),
                status=status,
                anime_upserted=anime_upserted,
                api_pages_failed=api_pages_failed,
                message=message,
            )
        )


def count_rows(engine: Engine) -> dict[str, int]:
    """Row count per data table. Used by the run summary and the idempotency tests."""
    tables = [Anime, Genre, AnimeGenre, Company, AnimeCompany]
    with engine.connect() as conn:
        return {
            t.__tablename__: conn.execute(select(func.count()).select_from(t)).scalar_one()
            for t in tables
        }
