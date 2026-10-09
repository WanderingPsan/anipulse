"""Run the whole analysis and regenerate every output from the database.

    python -m analysis.run

Reads the database (and the committed CSV, for the first funnel steps), answers the four
questions, and writes data/processed/ (parquet files, metadata.json) and analysis/FINDINGS.md.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import Connection, Engine, text

from analysis.findings import headline, render_findings
from analysis.funnel import Funnel, build_funnel, count_csv_steps
from analysis.questions import Results, analyze
from db.load import count_rows
from db.session import get_engine
from pipeline.run import csv_records

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).parent / "sql"
FINDINGS_PATH = Path(__file__).parent / "FINDINGS.md"
PROCESSED_DIR = Path("data/processed")
ANALYSIS_DIR = PROCESSED_DIR / "analysis"
QUERIES = [
    "funnel",
    "database_ids",
    "q1_factors",
    "q1_tags",
    "q2_popularity",
    "q3_top250",
    "q4_by_year",
    "catalog",
]


def read_sql(name: str) -> str:
    """Load one query from analysis/sql/."""
    return (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")


def run_queries(conn: Connection, names: list[str] = QUERIES) -> dict[str, pd.DataFrame]:
    """Create the population view, then run each query on the same connection.

    The view is temporary, so it must be created on the connection that uses it.
    """
    conn.execute(text(read_sql("population")))
    return {name: pd.read_sql(text(read_sql(name)), conn) for name in names}


def funnel_from(frames: dict[str, pd.DataFrame]) -> Funnel:
    """Count the CSV's cleaning steps, then join them to the database's counts."""
    csv = count_csv_steps(csv_records())
    ids = frames["database_ids"]
    sources = dict(zip(ids["mal_id"], ids["data_source"], strict=True))
    counts = frames["funnel"].iloc[0].astype(int).to_dict()
    return build_funnel(csv, sources, counts)


def read_metadata(engine: Engine, conn: Connection, population: int) -> dict:
    """Row counts and freshness, for the API and dashboard to show "data as of"."""
    last_updated = conn.execute(text("SELECT MAX(updated_at) FROM anime")).scalar_one()
    sources = conn.execute(
        text("SELECT data_source, COUNT(*) FROM anime GROUP BY data_source ORDER BY 1")
    ).all()
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_last_updated": last_updated.isoformat(timespec="seconds"),
        "row_counts": count_rows(engine),
        "data_source_counts": {source: n for source, n in sources},
        "analysis_population": population,
    }


def funnel_table(funnel: Funnel) -> pd.DataFrame:
    return pd.DataFrame([vars(step) for step in funnel.steps]).astype({"change": "Int64"})


def write_summary(results: Results) -> Path:
    """Save the headline sentence and key counts, so the dashboard shows FINDINGS.md's words.

    The model fit lives only in memory otherwise, and rebuilding the sentence elsewhere could
    let the dashboard and FINDINGS.md drift apart.
    """
    fit = results.model_fit
    summary = {
        "headline": headline(results),
        "model_r2": fit["model_r2"],
        "baseline_r2": fit["baseline_r2"],
        "model_n": fit["n"],
        "population_n": results.population_n,
        "top250_n": results.top250_n,
    }
    path = ANALYSIS_DIR / "summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path


def write_outputs(
    results: Results, funnel: Funnel, catalog: pd.DataFrame, metadata: dict
) -> list[Path]:
    """Save the chart-ready files and FINDINGS.md. Returns the paths written."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    tables = {
        "funnel": funnel_table(funnel),
        "tests": results.tests,
        "factor_groups": results.factor_groups,
        "tag_effects": results.tag_effects,
        "ols_coefficients": results.coefficients,
        "popularity_deciles": results.popularity_deciles,
        "top250_tags": results.top250,
        "by_year": results.by_year,
        "by_decade": results.decades,
        "numeric_bins": results.numeric_bins,
    }
    written = []
    for name, table in tables.items():
        path = ANALYSIS_DIR / f"{name}.parquet"
        table.to_parquet(path, index=False)
        written.append(path)

    written.append(write_summary(results))
    catalog_path = PROCESSED_DIR / "catalog.parquet"
    # A column with any missing value comes back as floats (year 2023.0). Int64 keeps 2023.
    catalog.astype({"year": "Int64", "members": "Int64"}).to_parquet(catalog_path, index=False)
    metadata_path = PROCESSED_DIR / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    findings = render_findings(results, funnel, metadata["data_last_updated"])
    FINDINGS_PATH.write_text(findings, encoding="utf-8")
    return written + [catalog_path, metadata_path, FINDINGS_PATH]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    engine = get_engine()
    with engine.connect() as conn:
        frames = run_queries(conn)
        funnel = funnel_from(frames)
        results = analyze(frames)
        metadata = read_metadata(engine, conn, results.population_n)
    for path in write_outputs(results, funnel, frames["catalog"], metadata):
        print(f"Wrote {path}")
    print(f"Analysis population: {results.population_n:,} titles")


if __name__ == "__main__":
    main()
