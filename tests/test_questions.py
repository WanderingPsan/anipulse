"""The four questions find the patterns built into the synthetic data, and the report fills in."""

import pandas as pd
import pytest

from analysis.findings import render_findings
from analysis.funnel import CsvCounts, build_funnel
from analysis.questions import Results, analyze, common_tags


@pytest.fixture(scope="module")
def results(synthetic_frames: dict[str, pd.DataFrame]) -> Results:
    return analyze(synthetic_frames)


def test_common_tags_skip_post_release_tags(synthetic_frames: dict[str, pd.DataFrame]) -> None:
    chosen = common_tags(synthetic_frames["q1_tags"])

    assert ("genre", "Award Winning") not in chosen
    assert ("genre", "Drama") in chosen


def test_built_in_effects_are_found(results: Results) -> None:
    tests = results.tests.set_index(["question", "factor"])

    assert tests.loc[("Q1", "type"), "significant"]
    assert tests.loc[("Q1", "genre=Drama"), "significant"]
    assert tests.loc[("Q2", "members"), "statistic"] > 0.5
    drama = results.tag_effects.set_index("factor").loc["genre=Drama"]
    assert drama.difference > 0


def test_every_test_has_an_adjusted_p_value_at_least_as_large(results: Results) -> None:
    tests = results.tests

    assert set(tests.question) == {"Q1", "Q2", "Q3"}
    assert (tests.p_adjusted >= tests.p_value).all()


def test_regression_uses_no_outcome_fields(results: Results) -> None:
    terms = set(results.coefficients.term)

    assert not any(word in term for term in terms for word in ("members", "favorites"))
    assert "log1p(episodes)" in terms
    assert results.model_fit["references"]["source"] in {"Manga", "Original", "Unknown"}


def test_findings_have_no_gaps_and_end_with_the_notice(results: Results) -> None:
    kept = frozenset(range(305))
    csv = CsvCounts(raw_rows=320, rx_removed=10, duplicates_removed=5, kept_ids=kept)
    sources = dict.fromkeys(kept, "kaggle")
    counts = {"in_database": 305, "has_score": 302, "enough_members": 300, "has_aired": 300}

    text = render_findings(results, build_funnel(csv, sources, counts), "2026-10-09")

    assert "$" not in text
    assert "effect size is what matters" in text
    assert "| Rows in the raw CSV |  | 320 |" in text
    assert text.rstrip().endswith("Refreshed data from\nMyAnimeList via the Tenrai API.")


def test_numeric_bins_cover_every_known_value_in_order(
    results: Results, synthetic_frames: dict[str, pd.DataFrame]
) -> None:
    bins = results.numeric_bins
    factors = synthetic_frames["q1_factors"]
    for factor in ["episodes", "duration_min"]:
        rows = bins[bins.factor == factor]
        # Every title with a known value lands in exactly one bucket.
        assert rows.n.sum() == factors[factor].notna().sum()
        assert rows.order.is_monotonic_increasing
        assert (rows.ci_low <= rows["median"]).all() and (rows["median"] <= rows.ci_high).all()
    # 13 episodes is one cour, so it belongs with 7-13, not 14-26.
    assert bins[bins.factor == "episodes"].group.tolist()[:3] == ["1", "2-6", "7-13"]
