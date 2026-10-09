"""Tests for the small text-cleaning functions in transform/parsing.py."""

import math

import pandas as pd
import pytest

from transform.parsing import (
    clean_int,
    clean_text,
    is_missing,
    parse_duration,
    parse_season,
    parse_year,
    split_company_field,
    split_list_field,
)

FRIEREN_AIRED = "2023-09-29T00:00:00+00:00"


@pytest.mark.parametrize("value", [None, math.nan, pd.NA, "", "   "])
def test_every_kind_of_empty_cell_is_missing(value: object) -> None:
    assert is_missing(value)


@pytest.mark.parametrize("value", [0, "0", "Unknown", 9.25])
def test_real_values_are_not_missing(value: object) -> None:
    assert not is_missing(value)


def test_clean_helpers_turn_empty_into_none() -> None:
    assert clean_text("  Frieren ") == "Frieren"
    assert clean_text(math.nan) is None
    assert clean_int(28.0) == 28
    assert clean_int(pd.NA) is None


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("24 min per ep", 24),
        ("24 min. per ep.", 24),
        ("24 min", 24),
        ("1 hr 55 min", 115),
        ("2 hr", 120),
        ("1 hr per ep", 60),
        ("33 sec per ep", 1),  # rounds to 1, never 0
        ("1 min 40 sec", 2),
        ("Unknown", None),
        (math.nan, None),
        ("", None),
    ],
)
def test_parse_duration(text: object, minutes: int | None) -> None:
    assert parse_duration(text) == minutes


def test_parse_year_keeps_the_source_year() -> None:
    assert parse_year(2023, FRIEREN_AIRED) == 2023


def test_parse_year_keeps_source_year_even_when_air_date_disagrees() -> None:
    # A show that starts in late December can be listed in the next year's winter season.
    assert parse_year(2024, "2023-12-30T00:00:00+00:00") == 2024


def test_parse_year_fills_missing_year_from_air_date() -> None:
    assert parse_year(math.nan, FRIEREN_AIRED) == 2023


def test_parse_year_is_none_when_both_are_missing() -> None:
    assert parse_year(None, None) is None


def test_parse_season_keeps_the_source_season() -> None:
    assert parse_season("fall", FRIEREN_AIRED) == "fall"


def test_parse_season_lowercases() -> None:
    assert parse_season("Fall", None) == "fall"


@pytest.mark.parametrize(
    ("month", "season"),
    [
        (1, "winter"),
        (3, "winter"),
        (4, "spring"),
        (6, "spring"),
        (7, "summer"),
        (9, "summer"),
        (10, "fall"),
        (12, "fall"),
    ],
)
def test_parse_season_fills_missing_season_from_month(month: int, season: str) -> None:
    assert parse_season(None, f"2020-{month:02d}-15T00:00:00+00:00") == season


def test_month_rule_can_differ_from_listed_season() -> None:
    # Frieren started on September 29, 2023, which the month rule calls summer. The source
    # lists it as fall, which is why the source's own season always wins when it has one.
    assert parse_season(math.nan, FRIEREN_AIRED) == "summer"
    assert parse_season("fall", FRIEREN_AIRED) == "fall"


def test_parse_season_is_none_without_season_or_date() -> None:
    assert parse_season(None, "not a date") is None


def test_split_list_field() -> None:
    assert split_list_field("Adventure, Drama, Fantasy") == ["Adventure", "Drama", "Fantasy"]
    assert split_list_field("Shounen") == ["Shounen"]


@pytest.mark.parametrize("value", ["Unknown", "", math.nan, None])
def test_split_list_field_empty_values_give_empty_list(value: object) -> None:
    assert split_list_field(value) == []


def test_split_company_field_keeps_legal_suffix_with_its_name() -> None:
    cell = "NIS America, Inc., Aniplex, Horgos Coloroom Pictures Co., Ltd."
    assert split_company_field(cell) == [
        "NIS America, Inc.",
        "Aniplex",
        "Horgos Coloroom Pictures Co., Ltd.",
    ]
