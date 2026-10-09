"""Dashboard tests: the pure helpers, plus smoke tests that run every page with AppTest.

AppTest runs a Streamlit script in this process, without a browser, and records every
element and exception. The smoke tests point the dashboard at tiny files in a temporary
folder, so they never need the real data or a database.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from analysis.findings import headline
from analysis.questions import Results, analyze
from dashboard.logic import (
    bin_label_for,
    filter_catalog,
    range_restriction,
    score_histogram,
    shared_tags,
    top_coefficients,
)
from dashboard.style import ACCENT, MUTED, highlight_colors
from tests.test_api import FRIEREN, write_fixture_files

# AppTest resolves relative paths from this test file, so give it the full path.
APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")


# --- pure helpers -----------------------------------------------------------------------


def catalog() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mal_id": [FRIEREN, 2, 3],
            "type": ["TV", "Movie", "TV"],
            "year": pd.array([2023, 2010, None], dtype="Int64"),
            "members": pd.array([1_500_000, 500, None], dtype="Int64"),
            "genres": [["Adventure", "Fantasy"], ["Drama"], ["Fantasy"]],
            "studios": [["Madhouse"], ["Bones"], []],
        }
    )


def test_highlight_colors_accent_only_the_named_label() -> None:
    assert highlight_colors(["TV", "Movie", "OVA"], "Movie") == [MUTED, ACCENT, MUTED]
    assert highlight_colors(["TV", "Movie"], ["TV", "Movie"]) == [ACCENT, ACCENT]


def test_score_histogram_counts_every_score_and_finds_the_median_bin() -> None:
    scores = pd.Series([6.1, 6.2, 6.8, 9.25, None])
    histogram = score_histogram(scores)
    assert histogram["count"].sum() == 4
    assert histogram["label"].iloc[0] == "6.00-6.25"
    assert bin_label_for(histogram, 6.8) == "6.75-7.00"


def test_filter_catalog_with_no_filters_keeps_everything() -> None:
    assert len(filter_catalog(catalog(), [], None, None, None, 0)) == 3


def test_filter_catalog_applies_each_filter() -> None:
    cat = catalog()
    assert filter_catalog(cat, ["TV"], None, None, None, 0)["mal_id"].tolist() == [FRIEREN, 3]
    # A year range drops the title with no year.
    assert filter_catalog(cat, [], (2000, 2030), None, None, 0)["mal_id"].tolist() == [FRIEREN, 2]
    assert filter_catalog(cat, [], None, "Fantasy", None, 0)["mal_id"].tolist() == [FRIEREN, 3]
    assert filter_catalog(cat, [], None, None, "Bones", 0)["mal_id"].tolist() == [2]
    assert filter_catalog(cat, [], None, None, None, 1000)["mal_id"].tolist() == [FRIEREN]


def test_shared_tags_are_the_sorted_overlap() -> None:
    assert shared_tags(["Fantasy", "Adventure", "Drama"], ["Drama", "Adventure"]) == [
        "Adventure",
        "Drama",
    ]
    assert shared_tags(["Fantasy"], []) == []


def test_top_coefficients_skip_number_terms_and_sort_by_effect() -> None:
    coefs = pd.DataFrame(
        {
            "term": ["const", "year", "type=Movie", "genre=Drama", "studio_group=Bones"],
            "coef": [-26.0, 0.02, -0.3, 0.5, 0.1],
        }
    )
    top = top_coefficients(coefs, k=2)
    assert top["name"].tolist() == ["Movie (type)", "Drama (genre)"]


def test_range_restriction_drops_tags_missing_from_the_top_250() -> None:
    effects = pd.DataFrame({"factor": ["genre=Drama", "genre=Kids"], "difference": [0.3, -0.5]})
    top250 = pd.DataFrame(
        {
            "factor": ["genre=Drama", "genre=Kids"],
            "difference_top250": [0.05, None],
            "n_with_top250": [40, 0],
        }
    )
    assert range_restriction(top250, effects)["name"].tolist() == ["Drama (genre)"]


# --- smoke tests: every page runs without an exception ------------------------------------


def write_analysis_files(folder: Path, results: Results) -> None:
    """The analysis tables, built by the real analysis code from the synthetic data."""
    analysis_dir = folder / "analysis"
    analysis_dir.mkdir()
    funnel = pd.DataFrame(
        {
            "label": ["Rows in the raw CSV", "No score", "Analysis population"],
            "change": pd.array([None, -2, None], dtype="Int64"),
            "rows": [6, 4, 4],
        }
    )
    tables = {
        "funnel": funnel,
        "tests": results.tests,
        "factor_groups": results.factor_groups,
        "tag_effects": results.tag_effects,
        "ols_coefficients": results.coefficients,
        "top250_tags": results.top250,
        "numeric_bins": results.numeric_bins,
    }
    for name, table in tables.items():
        table.to_parquet(analysis_dir / f"{name}.parquet", index=False)
    summary = {
        "headline": headline(results),
        "model_r2": results.model_fit["model_r2"],
        "baseline_r2": results.model_fit["baseline_r2"],
        "model_n": results.model_fit["n"],
        "population_n": results.population_n,
        "top250_n": results.top250_n,
    }
    (analysis_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


@pytest.fixture(scope="module")
def results(synthetic_frames: dict[str, pd.DataFrame]) -> Results:
    return analyze(synthetic_frames)


@pytest.fixture
def data_folder(
    tmp_path: Path, results: Results, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    write_fixture_files(tmp_path)
    write_analysis_files(tmp_path, results)
    monkeypatch.setenv("ANIPULSE_DATA_DIR", str(tmp_path))
    yield tmp_path


def run_page(page: str | None = None) -> AppTest:
    """Run the app, switch to a page if one is given, and return the finished run."""
    app = AppTest.from_file(APP, default_timeout=60).run()
    if page:
        app.switch_page(page).run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def test_overview_page_runs(data_folder: Path) -> None:
    app = run_page()
    assert app.title[0].value == "AniPulse"
    assert app.info[0].value.startswith("Using only facts known before an anime airs")


def test_predictors_page_runs_for_every_factor(data_folder: Path) -> None:
    app = run_page("pages/predictors.py")
    picker = app.selectbox[0]
    for factor in picker.options:
        picker.set_value(factor).run()
        assert not app.exception


def test_explore_page_runs_and_filters(data_folder: Path) -> None:
    app = run_page("pages/explore.py")
    assert app.markdown[0].value.startswith("**")  # "**n** of 6 titles match."
    app.multiselect[0].set_value(["TV"]).run()
    assert not app.exception


def test_recommender_page_shows_picks_for_frieren(data_folder: Path) -> None:
    app = run_page("pages/recommender.py")
    assert not app.info  # Frieren has picks, so no "no recommendations" message.
    assert app.subheader[0].value == "3 picks for Sousou no Frieren"


def test_recommender_page_explains_a_title_with_no_picks(data_folder: Path) -> None:
    app = run_page("pages/recommender.py")
    app.text_input[0].set_value("Frieren Recap").run()
    assert not app.exception
    assert "has no recommendations" in app.info[0].value
