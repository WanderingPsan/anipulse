"""The funnel accounts for every row, from the raw CSV to the analysis population."""

import pytest

from analysis.funnel import CsvCounts, build_funnel, count_csv_steps

FILTERS = {"in_database": 5, "has_score": 4, "enough_members": 3, "has_aired": 3}


def record(mal_id: int, rating: str = "PG-13 - Teens 13 or older") -> dict:
    return {"mal_id": mal_id, "rating": rating}


def test_count_csv_steps_counts_rx_and_duplicates() -> None:
    records = [record(1), record(1), record(2, "Rx - Hentai"), record(52991), record(3)]

    counts = count_csv_steps(records)

    assert counts.raw_rows == 5
    assert counts.rx_removed == 1
    assert counts.duplicates_removed == 1
    assert counts.kept_ids == {1, 3, 52991}


def test_funnel_adds_up_from_raw_rows_to_population() -> None:
    csv = CsvCounts(
        raw_rows=8, rx_removed=2, duplicates_removed=2, kept_ids=frozenset({1, 2, 3, 4})
    )
    # Title 5 is new from the API; title 1 is a CSV title the API refreshed.
    sources = {1: "api", 2: "kaggle", 3: "kaggle", 4: "kaggle", 5: "api"}

    funnel = build_funnel(csv, sources, FILTERS)

    rows = [step.rows for step in funnel.steps]
    assert rows == [8, 6, 4, 5, 4, 3, 3]
    assert funnel.steps[3].label == "Titles added by the live API"
    assert funnel.population == 3
    assert funnel.refreshed_by_api == 1
    # Each step's change is exactly the difference from the step before it.
    for before, after in zip(funnel.steps, funnel.steps[1:], strict=False):
        assert before.rows + after.change == after.rows


def test_funnel_shows_rows_that_came_from_neither_source() -> None:
    csv = CsvCounts(raw_rows=3, rx_removed=0, duplicates_removed=0, kept_ids=frozenset({1, 2, 9}))
    # 9 is missing from the database; 3, 4, 5 are kaggle rows from an older CSV.
    sources = {1: "kaggle", 2: "kaggle", 3: "kaggle", 4: "kaggle", 5: "kaggle"}

    funnel = build_funnel(csv, sources, FILTERS)

    labels = [step.label for step in funnel.steps]
    assert "CSV titles missing from the database" in labels
    assert "Database titles from an earlier load" in labels
    assert funnel.population == 3


def test_funnel_refuses_counts_that_do_not_add_up() -> None:
    csv = CsvCounts(raw_rows=4, rx_removed=0, duplicates_removed=0, kept_ids=frozenset({1, 2}))

    with pytest.raises(ValueError, match="database has 5"):
        build_funnel(csv, {1: "kaggle", 2: "kaggle"}, FILTERS)
