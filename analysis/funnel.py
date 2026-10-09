"""The data funnel: every row from the raw CSV down to the analysis population.

A funnel is a list of steps. Each step says what happened ("Rx titles removed"), how many rows
that changed (-1,581), and how many rows are left. The first steps happen in the pipeline
before the database, so they are counted again here from the CSV with the pipeline's own
functions. The last steps are the population filters, counted in SQL.
"""

from dataclasses import dataclass
from typing import Any

from transform.records import dedupe_by_mal_id, is_excluded


@dataclass(frozen=True)
class CsvCounts:
    """What the pipeline's cleaning does to the CSV, before anything reaches the database."""

    raw_rows: int
    rx_removed: int
    duplicates_removed: int
    kept_ids: frozenset[int]


@dataclass(frozen=True)
class FunnelStep:
    """One line of the funnel. change is None for the starting row count."""

    label: str
    change: int | None
    rows: int


@dataclass(frozen=True)
class Funnel:
    """The steps, plus how many CSV titles the live API refreshed (a count that adds no rows)."""

    steps: list[FunnelStep]
    refreshed_by_api: int

    @property
    def population(self) -> int:
        return self.steps[-1].rows


def count_csv_steps(records: list[dict[str, Any]]) -> CsvCounts:
    """Apply the pipeline's Rx filter and de-duplication to CSV records, counting each step."""
    kept = [r for r in records if not is_excluded(r)]
    unique, duplicates = dedupe_by_mal_id(kept)
    return CsvCounts(
        raw_rows=len(records),
        rx_removed=len(records) - len(kept),
        duplicates_removed=duplicates,
        kept_ids=frozenset(r["mal_id"] for r in unique),
    )


def build_funnel(
    csv: CsvCounts, database_sources: dict[int, str], filter_counts: dict[str, int]
) -> Funnel:
    """Join the CSV's counts to the database's, so every row is accounted for.

    database_sources maps each mal_id in the anime table to its data_source. filter_counts
    holds funnel.sql's columns. Steps that change nothing are still shown for the population
    filters (a 0 is a finding), but the reconciliation steps only appear when they are not 0.
    """
    steps = [FunnelStep("Rows in the raw CSV", None, csv.raw_rows)]

    def add(label: str, change: int, always: bool = True) -> None:
        if always or change != 0:
            steps.append(FunnelStep(label, change, steps[-1].rows + change))

    add("Rx (adult) titles removed", -csv.rx_removed)
    add("Duplicate rows removed", -csv.duplicates_removed)

    db_ids = set(database_sources)
    extra_ids = db_ids - csv.kept_ids
    api_added = sum(1 for i in extra_ids if database_sources[i] == "api")
    # Neither expected case can happen after a normal `--base csv` run. They are shown, not
    # hidden, so a database loaded some other way still produces a funnel that adds up.
    add("CSV titles missing from the database", -len(csv.kept_ids - db_ids), always=False)
    add("Titles added by the live API", api_added)
    add("Database titles from an earlier load", len(extra_ids) - api_added, always=False)

    in_database = filter_counts["in_database"]
    if steps[-1].rows != in_database:
        raise ValueError(f"Funnel reaches {steps[-1].rows} rows but the database has {in_database}")

    add("No score", filter_counts["has_score"] - in_database)
    add("Fewer than 1,000 members", filter_counts["enough_members"] - filter_counts["has_score"])
    add("Not yet aired", filter_counts["has_aired"] - filter_counts["enough_members"])

    refreshed = sum(1 for i in csv.kept_ids & db_ids if database_sources[i] == "api")
    return Funnel(steps=steps, refreshed_by_api=refreshed)
