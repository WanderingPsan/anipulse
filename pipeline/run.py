"""Run the whole pipeline: extract, transform, load.

    python -m pipeline.run --base csv --api-pages 2

--base csv loads the Kaggle snapshot (the backbone). --base none skips it.
--api-pages N then refreshes the top N pages of anime from the live API, whose newer values
overwrite the CSV's. N = 0 skips the API. The run exits with an error code only when the
base load fails: the API is an optional extra, so an outage there is reported, not fatal.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from db.load import count_rows, finish_run, load_records, start_run
from db.session import get_engine
from ingest.anime_api import get_top_anime
from ingest.build_genre_reference import REFERENCE_PATH
from ingest.kaggle import DEFAULT_PATH, read_kaggle_csv
from transform.records import (
    dedupe_by_mal_id,
    flatten_jikan_anime,
    is_excluded,
    kaggle_row_to_record,
)

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    """The numbers printed at the end of a run and saved to pipeline_runs."""

    anime_upserted: int = 0
    rx_dropped: int = 0
    duplicates_dropped: int = 0
    unmatched_tags: int = 0
    api_pages_failed: list[int] = field(default_factory=list)


def read_reference(path: Path = REFERENCE_PATH) -> list[dict[str, Any]]:
    """Load the committed MyAnimeList tag list."""
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(records: list[dict[str, Any]], summary: RunSummary) -> list[dict[str, Any]]:
    """Drop Rx titles and repeated mal_ids, counting both so nothing disappears silently."""
    kept = [r for r in records if not is_excluded(r)]
    summary.rx_dropped += len(records) - len(kept)
    kept, duplicates = dedupe_by_mal_id(kept)
    summary.duplicates_dropped += duplicates
    return kept


def csv_records(path: Path = DEFAULT_PATH) -> list[dict[str, Any]]:
    """Read the Kaggle CSV and turn every row into a record."""
    df = read_kaggle_csv(path)
    return [kaggle_row_to_record(row) for row in df.to_dict("records")]


def api_records(pages: int) -> tuple[list[dict[str, Any]], list[int]]:
    """Fetch the top `pages` pages from the live API. Returns records and the failed pages."""
    result = get_top_anime(pages)
    return [flatten_jikan_anime(raw) for raw in result.items], result.failed_pages


def load_source(
    engine: Engine,
    records: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    summary: RunSummary,
) -> None:
    """Prepare and load one source's records, adding its numbers to the summary."""
    stats = load_records(engine, prepare(records, summary), reference)
    summary.anime_upserted += stats.anime_upserted
    summary.unmatched_tags += sum(stats.unmatched_tags.values())


def run(engine: Engine, base: str, api_pages: int, csv_path: Path = DEFAULT_PATH) -> int:
    """Run the pipeline against `engine` and return the process exit code."""
    reference = read_reference()
    summary = RunSummary()
    run_id = start_run(engine, base, api_pages)
    notes: list[str] = []

    if base == "csv":
        try:
            load_source(engine, csv_records(csv_path), reference, summary)
        except Exception as err:  # any failure here means there is no usable base data
            logger.exception("Base CSV load failed")
            finish_run(engine, run_id, "failed", summary.anime_upserted, 0, f"CSV load: {err}")
            print(f"Base load failed: {err}")
            return 1

    if api_pages > 0:
        try:
            records, summary.api_pages_failed = api_records(api_pages)
            load_source(engine, records, reference, summary)
        except Exception as err:  # the API is optional, so report and keep the CSV data
            logger.exception("Live API refresh failed")
            summary.api_pages_failed = list(range(1, api_pages + 1))
            notes.append(f"API refresh failed: {err}")

    status = "partial" if summary.api_pages_failed else "success"
    notes.append(
        f"rx_dropped={summary.rx_dropped} duplicates_dropped={summary.duplicates_dropped} "
        f"unmatched_tags={summary.unmatched_tags}"
    )
    finish_run(
        engine,
        run_id,
        status,
        summary.anime_upserted,
        len(summary.api_pages_failed),
        "; ".join(notes),
    )
    print_summary(summary, count_rows(engine), status)
    return 0


def print_summary(summary: RunSummary, counts: dict[str, int], status: str) -> None:
    """Print what the run did, then how many rows each table holds now."""
    print(f"Run status: {status}")
    print(f"Anime upserted: {summary.anime_upserted}")
    print(f"Rx titles dropped: {summary.rx_dropped}")
    print(f"Duplicate rows dropped: {summary.duplicates_dropped}")
    print(f"Unmatched tags: {summary.unmatched_tags}")
    failed = ", ".join(map(str, summary.api_pages_failed)) or "none"
    print(f"API pages failed: {failed}")
    print("Rows in database: " + ", ".join(f"{name}={n}" for name, n in counts.items()))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load anime data into Postgres.")
    parser.add_argument("--base", choices=["csv", "none"], default="csv")
    parser.add_argument("--api-pages", type=int, default=0, help="0 skips the live API")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    return run(get_engine(), args.base, args.api_pages)


if __name__ == "__main__":
    sys.exit(main())
