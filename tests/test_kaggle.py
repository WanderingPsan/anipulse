"""Tests for the Kaggle CSV reader, using 21 real rows in tests/fixtures/kaggle_sample.csv."""

from pathlib import Path

import pandas as pd
import pytest

from ingest.kaggle import COLUMN_MAP, MissingColumnsError, read_kaggle_csv

FIXTURE = Path(__file__).parent / "fixtures" / "kaggle_sample.csv"


def test_reader_keeps_and_renames_mapped_columns() -> None:
    df = read_kaggle_csv(FIXTURE)

    assert list(df.columns) == list(COLUMN_MAP.values())
    assert len(df) == 21


def test_frieren_row_reads_correctly() -> None:
    df = read_kaggle_csv(FIXTURE)
    frieren = df[df["mal_id"] == 52991].iloc[0]

    assert frieren["title"] == "Sousou no Frieren"
    assert frieren["episodes"] == 28
    assert frieren["genres"] == "Adventure, Drama, Fantasy"


def test_unknown_values_stay_empty_not_zero() -> None:
    df = read_kaggle_csv(FIXTURE)
    one_piece = df[df["mal_id"] == 21].iloc[0]  # still airing, so episode count is unknown

    assert str(df["episodes"].dtype) == "Int64"
    assert pd.isna(one_piece["episodes"])


def test_missing_column_raises_clear_error(tmp_path: Path) -> None:
    broken = tmp_path / "broken.csv"
    pd.read_csv(FIXTURE).drop(columns=["score", "genres"]).to_csv(broken, index=False)

    with pytest.raises(MissingColumnsError, match="score, genres"):
        read_kaggle_csv(broken)
