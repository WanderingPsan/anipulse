"""Statistics helpers give known answers on small, hand-built data."""

import numpy as np
import pandas as pd
import pytest

from analysis.stats import (
    adjust_pvalues,
    bootstrap_median_ci,
    check_no_outcomes,
    cross_validated_r2,
    design_matrix,
    effect_size_label,
    fit_ols,
    kruskal_test,
    spearman_test,
)


def test_spearman_of_a_perfect_ranking_is_one() -> None:
    result = spearman_test(pd.Series([1, 2, 3, 4, None]), pd.Series([10, 20, 30, 40, 50]))

    assert result["n"] == 4  # the row with a missing value is skipped
    assert result["statistic"] == pytest.approx(1.0)
    assert result["effect_size"] == pytest.approx(1.0)


def test_kruskal_finds_separated_groups_and_ignores_mixed_ones() -> None:
    separated = pd.DataFrame({"group": ["a"] * 20 + ["b"] * 20, "score": range(40)})
    mixed = pd.DataFrame({"group": ["a", "b"] * 20, "score": [5.0, 5.0] * 20})
    mixed.loc[0, "score"] = 6.0  # Kruskal-Wallis needs at least two different values

    strong = kruskal_test(separated, "group")
    weak = kruskal_test(mixed, "group")

    assert strong["p_value"] < 0.001
    assert strong["effect_size"] > 0.5
    assert weak["p_value"] > 0.05


def test_bootstrap_interval_contains_the_median() -> None:
    values = np.random.default_rng(1).normal(7.0, 0.5, 500)

    low, high = bootstrap_median_ci(values, np.random.default_rng(2))

    assert low < np.median(values) < high
    assert high - low < 0.2


def test_benjamini_hochberg_never_lowers_a_p_value() -> None:
    raw = pd.Series([0.001, 0.01, 0.04, 0.5])

    adjusted = adjust_pvalues(raw)

    assert (adjusted >= raw).all()
    assert adjusted.iloc[2] == pytest.approx(0.04 * 4 / 3)


@pytest.mark.parametrize(
    ("effect", "label"),
    [(0.005, "negligible"), (0.03, "small"), (0.1, "medium"), (0.4, "large")],
)
def test_effect_size_labels(effect: float, label: str) -> None:
    assert effect_size_label(effect) == label


@pytest.mark.parametrize("column", ["members", "log1p(members)", "score", "favorites=10"])
def test_outcome_fields_are_rejected_as_predictors(column: str) -> None:
    with pytest.raises(ValueError, match="Outcome fields"):
        check_no_outcomes(["episodes", column])


def test_design_matrix_drops_the_most_common_category() -> None:
    df = pd.DataFrame(
        {
            "type": ["TV", "TV", "TV", "Movie", "OVA"],
            "episodes": [12, 24, 12, 1, 6],
            "drama": [1] * 5,
        }
    )

    x, references = design_matrix(df, ["episodes"], ["type"], ["drama"])

    assert references == {"type": "TV"}
    assert list(x.columns) == ["episodes", "drama", "type=Movie", "type=OVA"]


def test_regression_recovers_a_known_effect() -> None:
    rng = np.random.default_rng(3)
    x = pd.DataFrame({"is_tv": rng.integers(0, 2, 400).astype(float)})
    y = pd.Series(6.0 + 0.8 * x.is_tv + rng.normal(0, 0.2, 400))

    coefficients, fit = fit_ols(x, y)
    cv = cross_validated_r2(x, y)

    tv = coefficients.set_index("term").loc["is_tv"]
    assert tv.ci_low < 0.8 < tv.ci_high
    assert fit["n"] == 400
    assert cv["model_r2"] > 0.7  # the true R squared here is 0.8
    assert cv["baseline_r2"] < 0.01
