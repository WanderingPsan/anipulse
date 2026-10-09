"""Answer the four analysis questions from the query results. Pure: DataFrames in, results out.

1. Which pre-release factors are associated with higher scores?
2. Does popularity track quality?
3. Do genre effects seen in the whole population still show up within the top 250?
4. How have scores and the number of titles changed by year?
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from analysis.stats import (
    SEED,
    adjust_pvalues,
    cross_validated_r2,
    design_matrix,
    effect_size_label,
    fit_ols,
    group_medians,
    kruskal_test,
    spearman_test,
)

NUMERIC_FACTORS = ["episodes", "duration_min", "year"]
CATEGORICAL_FACTORS = ["type", "source", "rating", "season", "demographic", "studio_group"]
# Episodes and duration are very skewed (most shows have 12 episodes, a few have 1,000+).
# log(1 + x) pulls in the long tail so a handful of huge shows cannot steer the model.
LOGGED_FACTORS = ["episodes", "duration_min"]
TOP_GENRES = 15
# MyAnimeList adds "Award Winning" after a show wins an award, so it is an outcome, not a
# pre-release factor (D-007). Using it would explain good scores with good reception.
POST_RELEASE_TAGS = frozenset({"Award Winning"})
TOP_THEMES = 10
SIGNIFICANCE = 0.05
# Buckets for charting episodes and episode length. Edges are chosen to match how shows are
# made: 1 episode is a movie or special, 12-13 is one cour (season), 24-26 is two cours.
# Each bucket includes its upper edge, so 13 episodes lands in "7-13".
NUMERIC_BINS = {
    "episodes": ([0, 1, 6, 13, 26, 52, np.inf], ["1", "2-6", "7-13", "14-26", "27-52", "53+"]),
    "duration_min": (
        [0, 4, 14, 29, 59, np.inf],
        ["1-4", "5-14", "15-29", "30-59", "60+"],
    ),
}

FACTOR_NAMES = {
    "episodes": "Episodes",
    "duration_min": "Episode length (minutes)",
    "year": "Year",
    "type": "Type",
    "source": "Source material",
    "rating": "Content rating",
    "season": "Season",
    "demographic": "Demographic",
    "studio_group": "Studio (top 15, rest as Other)",
}


@dataclass
class Results:
    """Everything the analysis found. run.py saves it and findings.py writes it up."""

    population_n: int
    tests: pd.DataFrame
    factor_groups: pd.DataFrame
    tag_effects: pd.DataFrame
    coefficients: pd.DataFrame
    model_fit: dict[str, Any]
    popularity_deciles: pd.DataFrame
    top250: pd.DataFrame
    top250_n: int
    by_year: pd.DataFrame
    decades: pd.DataFrame
    numeric_bins: pd.DataFrame


def fill_unknown(factors: pd.DataFrame) -> pd.DataFrame:
    """Give missing categories a name, so "unknown source" is a group and not a dropped row."""
    return factors.fillna({col: "Unknown" for col in CATEGORICAL_FACTORS})


def common_tags(tags: pd.DataFrame) -> list[tuple[str, str]]:
    """The most frequent genres and themes in the population, as (kind, name) pairs."""
    chosen = []
    for kind, top in (("genre", TOP_GENRES), ("theme", TOP_THEMES)):
        usable = tags[(tags["kind"] == kind) & ~tags["tag"].isin(POST_RELEASE_TAGS)]
        counts = usable["tag"].value_counts()
        # Sort by count, then name, so a tie never changes which tags are picked.
        counts = counts.sort_index().sort_values(ascending=False, kind="stable")
        chosen += [(kind, name) for name in counts.index[:top]]
    return chosen


def tag_indicators(
    mal_ids: pd.Series, tags: pd.DataFrame, chosen: list[tuple[str, str]]
) -> pd.DataFrame:
    """One True/False column per chosen tag (named like "genre=Drama"), one row per anime."""
    columns = {}
    for kind, name in chosen:
        tagged = set(tags.loc[(tags["kind"] == kind) & (tags["tag"] == name), "mal_id"])
        columns[f"{kind}={name}"] = mal_ids.isin(tagged).to_numpy()
    return pd.DataFrame(columns, index=mal_ids.index)


def _test_row(question: str, factor: str, test: str, result: dict[str, float]) -> dict:
    return {"question": question, "factor": factor, "test": test, **result}


def factor_tests(
    factors: pd.DataFrame, indicators: pd.DataFrame, rng: np.random.Generator
) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    """Question 1, one factor at a time. Returns test rows, group medians, and tag effects."""
    tests = []
    for col in NUMERIC_FACTORS:
        tests.append(_test_row("Q1", col, "spearman", spearman_test(factors[col], factors.score)))

    groups = []
    for col in CATEGORICAL_FACTORS:
        tests.append(_test_row("Q1", col, "kruskal", kruskal_test(factors, col)))
        groups.append(group_medians(factors, col, rng).assign(factor=col))

    effects = []
    for col in indicators.columns:
        has_tag = factors[["score"]].assign(has_tag=indicators[col])
        tests.append(_test_row("Q1", col, "kruskal", kruskal_test(has_tag, "has_tag")))
        medians = group_medians(has_tag, "has_tag", rng).set_index("group")
        kind, name = col.split("=", 1)
        effects.append(
            {
                "factor": col,
                "kind": kind,
                "tag": name,
                "n_with": int(medians.loc[True, "n"]),
                "median_with": medians.loc[True, "median"],
                "ci_low_with": medians.loc[True, "ci_low"],
                "ci_high_with": medians.loc[True, "ci_high"],
                "n_without": int(medians.loc[False, "n"]),
                "median_without": medians.loc[False, "median"],
                "difference": medians.loc[True, "median"] - medians.loc[False, "median"],
            }
        )
    factor_groups = pd.concat(groups, ignore_index=True)[
        ["factor", "group", "n", "median", "ci_low", "ci_high"]
    ]
    return tests, factor_groups, pd.DataFrame(effects)


def regression(factors: pd.DataFrame, indicators: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Question 1, all factors at once: OLS coefficients plus cross-validated R squared.

    Rows missing a numeric factor are left out of the model; the fit reports how many remain.
    """
    df = pd.concat([factors, indicators], axis=1).dropna(subset=NUMERIC_FACTORS)
    logged = {col: f"log1p({col})" for col in LOGGED_FACTORS}
    df[LOGGED_FACTORS] = np.log1p(df[LOGGED_FACTORS])
    df = df.rename(columns=logged)
    numeric = [logged.get(col, col) for col in NUMERIC_FACTORS]
    x, references = design_matrix(df, numeric, CATEGORICAL_FACTORS, list(indicators.columns))
    coefficients, fit = fit_ols(x, df["score"])
    fit |= cross_validated_r2(x, df["score"])
    fit["references"] = references
    fit["rows_dropped"] = len(factors) - len(df)
    return coefficients, fit


def popularity(scores: pd.DataFrame, rng: np.random.Generator) -> tuple[dict, pd.DataFrame]:
    """Question 2: Spearman of members and score, plus median score per members decile."""
    test = _test_row("Q2", "members", "spearman", spearman_test(scores.members, scores.score))
    medians = group_medians(scores, "members_decile", rng).rename(columns={"group": "decile"})
    ranges = scores.groupby("members_decile")["members"].agg(["min", "max"])
    ranges.columns = ["members_min", "members_max"]
    deciles = medians.merge(ranges, left_on="decile", right_index=True).sort_values("decile")
    return test, deciles.reset_index(drop=True)


def range_restriction(
    factors: pd.DataFrame, indicators: pd.DataFrame, top_ids: pd.Series
) -> tuple[list[dict], pd.DataFrame]:
    """Question 3: compare each tag's share and score gap in the population and the top 250.

    Inside the top 250 every score is high (a narrow range), so differences between groups
    shrink. That is range restriction: an effect can vanish just because the range is small.
    """
    in_top = factors["mal_id"].isin(set(top_ids))
    top, top_tags = factors[in_top], indicators[in_top]
    tests, rows = [], []
    for col in indicators.columns:
        has_tag = top[["score"]].assign(has_tag=top_tags[col])
        with_tag = has_tag.loc[has_tag.has_tag, "score"]
        without = has_tag.loc[~has_tag.has_tag, "score"]
        testable = len(with_tag) > 0 and len(without) > 0
        if testable:
            tests.append(_test_row("Q3", col, "kruskal", kruskal_test(has_tag, "has_tag")))
        rows.append(
            {
                "factor": col,
                "share_population": float(indicators[col].mean()),
                "share_top250": float(top_tags[col].mean()),
                "n_with_top250": len(with_tag),
                "difference_top250": (with_tag.median() - without.median()) if testable else np.nan,
            }
        )
    return tests, pd.DataFrame(rows)


def decade_summary(by_year: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Question 4 in a readable size: titles and median score per decade."""
    counts = by_year.assign(decade=by_year.year // 10 * 10).groupby("decade")[
        ["titles_in_catalog", "titles_in_population"]
    ]
    medians = (
        factors.dropna(subset=["year"])
        .assign(decade=lambda d: d.year // 10 * 10)
        .groupby("decade")["score"]
        .median()
        .rename("median_score")
    )
    summary = counts.sum().join(medians).reset_index()
    return summary.astype({"decade": int})


def numeric_bins(factors: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Median score per bucket of episodes and of episode length, for charts.

    The Spearman test gives one number for "more episodes, higher score". Buckets show the
    shape behind it: for example, whether 1-episode titles are the ones pulling scores down.
    Titles missing the value are left out of that factor's buckets.
    """
    frames = []
    for col, (edges, labels) in NUMERIC_BINS.items():
        known = factors.dropna(subset=[col])
        buckets = pd.cut(known[col], bins=edges, labels=labels)
        groups = group_medians(known.assign(bucket=buckets), "bucket", rng)
        # group_medians sorts by median; put the buckets back in their natural order.
        groups["order"] = groups["group"].map(labels.index)
        frames.append(groups.sort_values("order").assign(factor=col))
    table = pd.concat(frames, ignore_index=True)
    return table[["factor", "group", "order", "n", "median", "ci_low", "ci_high"]].astype(
        {"group": str, "order": int}
    )


def finish_tests(rows: list[dict]) -> pd.DataFrame:
    """Put every test in one table, adjust all p-values together, and label effect sizes."""
    tests = pd.DataFrame(rows)
    tests["p_adjusted"] = adjust_pvalues(tests["p_value"])
    tests["effect_label"] = tests["effect_size"].map(effect_size_label)
    tests["significant"] = tests["p_adjusted"] < SIGNIFICANCE
    return tests


def analyze(frames: dict[str, pd.DataFrame]) -> Results:
    """Run all four questions on the query results (keyed by SQL file name)."""
    rng = np.random.default_rng(SEED)
    factors = fill_unknown(frames["q1_factors"])
    tags = frames["q1_tags"]
    indicators = tag_indicators(factors["mal_id"], tags, common_tags(tags))

    q1_tests, factor_groups, tag_effects = factor_tests(factors, indicators, rng)
    coefficients, model_fit = regression(factors, indicators)
    q2_test, deciles = popularity(frames["q2_popularity"], rng)
    q3_tests, top250 = range_restriction(factors, indicators, frames["q3_top250"]["mal_id"])

    return Results(
        population_n=len(factors),
        tests=finish_tests(q1_tests + [q2_test] + q3_tests),
        factor_groups=factor_groups,
        tag_effects=tag_effects,
        coefficients=coefficients,
        model_fit=model_fit,
        popularity_deciles=deciles,
        top250=top250,
        top250_n=len(frames["q3_top250"]),
        by_year=frames["q4_by_year"],
        decades=decade_summary(frames["q4_by_year"], factors),
        # Computed last so the random draws above, and so every earlier interval, stay the same.
        numeric_bins=numeric_bins(factors, rng),
    )
