"""Write FINDINGS.md from the analysis results.

The text lives in FINDINGS_TEMPLATE.md with $placeholders. This module turns results into the
values for those placeholders. string.Template.substitute raises an error if any placeholder
is left without a value, so the report can never ship with a gap or a hand-typed number.
"""

from pathlib import Path
from string import Template

import pandas as pd

from analysis.funnel import Funnel
from analysis.questions import FACTOR_NAMES, TOP_GENRES, TOP_THEMES, Results
from analysis.stats import BOOTSTRAP_SAMPLES, effect_size_label

TEMPLATE_PATH = Path(__file__).parent / "FINDINGS_TEMPLATE.md"
COEFFICIENTS_EACH_WAY = 10
# The Kaggle snapshot is from July 2025, so titles dated after 2024 are an incomplete picture.
LAST_FULL_YEAR = 2024


def fmt_int(n: float) -> str:
    return f"{int(n):,}"


def fmt_p(p: float) -> str:
    """Tiny p-values all read the same, so print them as a threshold instead of 0.000."""
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def fmt_r2(value: float, digits: int) -> str:
    """Round first, so a baseline of -0.00001 prints as 0.000 and not -0.000."""
    return f"{round(value, digits) + 0.0:.{digits}f}"


def fmt_change(change: float | None) -> str:
    if change is None or pd.isna(change):
        return ""
    if change == 0:
        return "0"
    return f"+{fmt_int(change)}" if change > 0 else f"-{fmt_int(-change)}"


def markdown_table(rows: list[list[str]], header: list[str]) -> str:
    """A GitHub markdown table. Number-looking columns are fine left-aligned for reading."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def short_name(factor: str) -> str:
    """A factor's name for use inside a sentence: "studio", "source material", "genre"."""
    return FACTOR_NAMES.get(factor, factor).split(" (")[0].lower()


def factor_name(factor: str) -> str:
    """Display name: "genre=Drama" -> "Drama (genre)", "studio_group=Bones" -> "Bones (studio)"."""
    if "=" in factor:
        kind, name = factor.split("=", 1)
        return f"{name} ({short_name(kind)})"
    return FACTOR_NAMES.get(factor, factor)


def funnel_table(funnel: Funnel) -> str:
    rows = [[s.label, fmt_change(s.change), fmt_int(s.rows)] for s in funnel.steps]
    rows.append(["**Analysis population**", "", f"**{fmt_int(funnel.population)}**"])
    return markdown_table(rows, ["Step", "Change", "Rows left"])


def refreshed_note(funnel: Funnel) -> str:
    return (
        f"The live API also refreshed {fmt_int(funnel.refreshed_by_api)} titles that were "
        "already in the CSV. Their newer values replaced the CSV's, which changes no row count."
    )


def test_cells(test: pd.Series) -> list[str]:
    """The columns every test table shares: n, effect size, label, raw p, adjusted p."""
    return [
        fmt_int(test.n),
        f"{test.effect_size:.3f}",
        test.effect_label,
        fmt_p(test.p_value),
        fmt_p(test.p_adjusted),
    ]


TEST_HEADER = ["n", "Effect size", "Size", "p", "Adjusted p"]


def factor_table(tests: pd.DataFrame) -> str:
    q1 = tests[(tests.question == "Q1") & ~tests.factor.str.contains("=")]
    rows = [
        [factor_name(t.factor), "Spearman" if t.test == "spearman" else "Kruskal-Wallis"]
        + test_cells(t)
        for t in q1.sort_values("effect_size", ascending=False).itertuples()
    ]
    return markdown_table(rows, ["Factor", "Test"] + TEST_HEADER)


def group_tables(groups: pd.DataFrame) -> str:
    """One small table per category factor, in the order the factors were tested."""
    parts = []
    for factor, table in groups.groupby("factor", sort=False):
        rows = [
            [str(g.group), fmt_int(g.n), f"{g.median:.2f}", f"{g.ci_low:.2f} to {g.ci_high:.2f}"]
            for g in table.itertuples()
        ]
        parts.append(
            f"**{factor_name(factor)}**\n\n"
            + markdown_table(rows, ["Group", "n", "Median score", "95% CI"])
        )
    return "\n\n".join(parts)


def tag_table(effects: pd.DataFrame, tests: pd.DataFrame) -> str:
    q1 = tests[tests.question == "Q1"].set_index("factor")
    merged = effects.join(q1, on="factor").sort_values("effect_size", ascending=False)
    rows = [
        [
            factor_name(e.factor),
            fmt_int(e.n_with),
            f"{e.median_with:.2f} ({e.ci_low_with:.2f} to {e.ci_high_with:.2f})",
            f"{e.median_without:.2f}",
            f"{e.difference:+.2f}",
            f"{e.effect_size:.3f}",
            e.effect_label,
            fmt_p(e.p_value),
            fmt_p(e.p_adjusted),
        ]
        for e in merged.itertuples()
    ]
    header = ["Tag", "Titles with it", "Median with (95% CI)", "Median without", "Gap"]
    return markdown_table(rows, header + ["Effect size", "Size", "p", "Adjusted p"])


def coefficient_table(coefficients: pd.DataFrame) -> str:
    """Category and tag coefficients only: numeric ones are per unit, so not comparable."""
    usable = coefficients[coefficients.term.str.contains("=") & (coefficients.p_value < 0.05)]
    ordered = usable.sort_values("coef", ascending=False)
    top = pd.concat(
        [ordered.head(COEFFICIENTS_EACH_WAY), ordered.tail(COEFFICIENTS_EACH_WAY)]
    ).drop_duplicates("term")
    rows = [
        [
            factor_name(c.term),
            f"{c.coef:+.2f}",
            f"{c.ci_low:+.2f} to {c.ci_high:+.2f}",
            fmt_p(c.p_value),
        ]
        for c in top.itertuples()
    ]
    return markdown_table(rows, ["Term", "Coefficient", "95% CI", "p"])


def decile_table(deciles: pd.DataFrame) -> str:
    rows = [
        [
            str(d.decile),
            f"{fmt_int(d.members_min)} to {fmt_int(d.members_max)}",
            fmt_int(d.n),
            f"{d.median:.2f}",
            f"{d.ci_low:.2f} to {d.ci_high:.2f}",
        ]
        for d in deciles.itertuples()
    ]
    return markdown_table(rows, ["Members decile", "Members", "n", "Median score", "95% CI"])


def top250_table(top250: pd.DataFrame, effects: pd.DataFrame, tests: pd.DataFrame) -> str:
    q1 = tests[tests.question == "Q1"].set_index("factor")
    q3 = tests[tests.question == "Q3"].set_index("factor")
    merged = top250.merge(effects[["factor", "difference"]], on="factor")
    merged = merged.join(q1[["effect_size"]], on="factor")
    merged = merged.join(q3[["effect_size", "p_adjusted"]], on="factor", rsuffix="_top")
    rows = []
    for m in merged.sort_values("effect_size", ascending=False).itertuples():
        tested = not pd.isna(m.effect_size_top)
        rows.append(
            [
                factor_name(m.factor),
                f"{m.share_population:.0%}",
                f"{m.share_top250:.0%}",
                f"{m.difference:+.2f}",
                f"{m.difference_top250:+.2f}" if tested else "n/a",
                f"{m.effect_size:.3f}",
                f"{m.effect_size_top:.3f}" if tested else "n/a",
                fmt_p(m.p_adjusted) if tested else "n/a",
            ]
        )
    header = ["Tag", "Share (all)", "Share (top 250)", "Gap (all)", "Gap (top 250)"]
    return markdown_table(rows, header + ["Effect (all)", "Effect (top 250)", "Adj. p (top 250)"])


def decade_table(decades: pd.DataFrame) -> str:
    rows = [
        [
            f"{d.decade}s",
            fmt_int(d.titles_in_catalog),
            fmt_int(d.titles_in_population),
            "n/a" if pd.isna(d.median_score) else f"{d.median_score:.2f}",
        ]
        for d in decades.itertuples()
    ]
    return markdown_table(rows, ["Decade", "Titles in catalog", "In population", "Median score"])


def headline(results: Results) -> str:
    """The top-line answer, built from the strongest effects and the model's honest R squared."""
    q1 = results.tests[results.tests.question == "Q1"].sort_values("effect_size", ascending=False)
    first, second, third = q1.head(3).itertuples()
    fit = results.model_fit
    return (
        f"Using only facts known before an anime airs, a linear model explains about "
        f"{fit['model_r2']:.0%} of the variation in MyAnimeList score on titles it has not seen "
        f"(5-fold cross-validated R squared {fmt_r2(fit['model_r2'], 2)}, versus "
        f"{fmt_r2(fit['baseline_r2'], 2)} for always predicting the mean). "
        f"{strength_sentence(first.effect_label)} "
        f"The strongest are {short_name(first.factor)} (effect size "
        f"{first.effect_size:.3f}, {first.effect_label}), "
        f"{short_name(second.factor)} ({second.effect_size:.3f}, "
        f"{second.effect_label}), and {short_name(third.factor)} "
        f"({third.effect_size:.3f}, {third.effect_label}). These are associations in "
        f"observational data, not causes."
    )


def strength_sentence(strongest_label: str) -> str:
    """Describe the strongest single factor's size in words, based on its effect-size label."""
    if strongest_label == "large":
        return "At least one factor has a large effect on its own."
    return f"No single factor has a large effect on its own: the biggest is {strongest_label}."


def _mean_gap(values: pd.Series) -> str:
    return f"{values.abs().mean():.2f}"


def placeholder_values(results: Results, funnel: Funnel, data_last_updated: str) -> dict:
    """Every value the template needs, keyed by placeholder name."""
    tests, fit = results.tests, results.model_fit
    significant = tests[tests.significant]
    q1_tags = tests[(tests.question == "Q1") & tests.factor.str.contains("=")]
    q3 = tests[tests.question == "Q3"]
    popularity = tests[tests.question == "Q2"].iloc[0]
    year = tests[(tests.question == "Q1") & (tests.factor == "year")].iloc[0]
    steps = {step.label: step for step in funnel.steps}
    recent = results.by_year.loc[results.by_year.year > LAST_FULL_YEAR, "titles_in_catalog"].sum()
    references = ", ".join(f"{short_name(k)} = {v}" for k, v in fit["references"].items())
    return {
        "data_last_updated": data_last_updated,
        "headline": headline(results),
        "population_n": fmt_int(results.population_n),
        "n_tests": fmt_int(len(tests)),
        "n_significant": fmt_int(len(significant)),
        "n_significant_negligible": fmt_int((significant.effect_label == "negligible").sum()),
        "funnel_table": funnel_table(funnel),
        "refreshed_note": refreshed_note(funnel),
        "factor_table": factor_table(tests),
        "bootstrap_samples": fmt_int(BOOTSTRAP_SAMPLES),
        "group_tables": group_tables(results.factor_groups),
        "n_genres": str(TOP_GENRES),
        "n_themes": str(TOP_THEMES),
        "tag_table": tag_table(results.tag_effects, tests),
        "model_n": fmt_int(fit["n"]),
        "model_dropped": fmt_int(fit["rows_dropped"]),
        "model_r2": f"{fit['r2']:.3f}",
        "model_adj_r2": f"{fit['adj_r2']:.3f}",
        "cv_r2": f"{fit['model_r2']:.3f}",
        "cv_r2_std": f"{fit['model_r2_std']:.3f}",
        "baseline_r2": fmt_r2(fit["baseline_r2"], 3),
        "references": references,
        "coefficient_table": coefficient_table(results.coefficients),
        "popularity_rho": f"{popularity.statistic:.2f}",
        "popularity_n": fmt_int(popularity.n),
        "popularity_effect": f"{popularity.effect_size:.3f}",
        "popularity_label": effect_size_label(popularity.effect_size),
        "decile_table": decile_table(results.popularity_deciles),
        "top250_n": fmt_int(results.top250_n),
        "n_tags": fmt_int(len(q1_tags)),
        "tags_significant_population": fmt_int(q1_tags.significant.sum()),
        "tags_significant_top250": fmt_int(q3.significant.sum()),
        "mean_gap_population": _mean_gap(results.tag_effects.difference),
        "mean_gap_top250": _mean_gap(results.top250.difference_top250.dropna()),
        "top250_table": top250_table(results.top250, results.tag_effects, tests),
        "year_rho": f"{year.statistic:.2f}",
        "year_effect": f"{year.effect_size:.3f}",
        "year_label": year.effect_label,
        "decade_table": decade_table(results.decades),
        "no_score_removed": fmt_int(-steps["No score"].change),
        "members_removed": fmt_int(-steps["Fewer than 1,000 members"].change),
        "recent_titles": fmt_int(recent),
        "last_full_year": str(LAST_FULL_YEAR),
        "lowest_decile_median": f"{results.popularity_deciles.iloc[0]['median']:.2f}",
        "highest_decile_median": f"{results.popularity_deciles.iloc[-1]['median']:.2f}",
    }


def render_findings(results: Results, funnel: Funnel, data_last_updated: str) -> str:
    """Fill the template. substitute() raises KeyError if any placeholder has no value."""
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.substitute(placeholder_values(results, funnel, data_last_updated))
