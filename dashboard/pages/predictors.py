"""What predicts a high score? The headline, then each kind of evidence behind it."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis.questions import CATEGORICAL_FACTORS, FACTOR_NAMES
from dashboard import data
from dashboard.logic import (
    POPULATION_NOTE,
    SOURCE_CAPTION,
    best_group,
    factor_test,
    range_restriction,
    top_coefficients,
)
from dashboard.style import ACCENT, MUTED, highlight_colors, style_figure

tables = data.analysis()
tests = tables["tests"]

st.title("What predicts a high score?")
st.info(tables["summary"]["headline"])
st.caption(
    "Effect size is the share of the variation in score ranks a factor explains, from 0 to 1. "
    "Below 0.01 is negligible, 0.01 to 0.06 small, 0.06 to 0.14 medium, 0.14 and up large."
)


def median_dots(groups: pd.DataFrame, highlight: str, x_title: str) -> go.Figure:
    """Median score per group as dots, with 95% interval whiskers. One row per group."""
    labels = groups["group"].astype(str).tolist()
    return go.Figure(
        go.Scatter(
            x=groups["median"],
            y=labels,
            mode="markers",
            marker={"size": 11, "color": highlight_colors(labels, highlight)},
            error_x={
                "type": "data",
                "symmetric": False,
                "array": groups["ci_high"] - groups["median"],
                "arrayminus": groups["median"] - groups["ci_low"],
                "color": MUTED,
                "thickness": 2,
            },
            customdata=groups["n"],
            hovertemplate="%{y}<br>Median %{x:.2f}<br>n = %{customdata:,}<extra></extra>",
        )
    ).update_xaxes(title=x_title)


# 1. Factor explorer: pick a category, see each group's median score.
st.header("Factor explorer")
factor = st.selectbox(
    "Factor", CATEGORICAL_FACTORS, format_func=lambda name: FACTOR_NAMES.get(name, name)
)
groups = tables["factor_groups"]
groups = groups[groups["factor"] == factor].sort_values("median")
top = best_group(groups)
test = factor_test(tests, factor)
name = FACTOR_NAMES.get(factor, factor)
fig = median_dots(groups, str(top["group"]), "Median score (dot) with 95% interval")
title = (
    f"{name}: {top['group']} has the highest median score ({top['median']:.2f}, "
    f"n = {int(top['n']):,})"
)
st.plotly_chart(style_figure(fig, title, height=max(300, 34 * len(groups) + 90)))
st.caption(
    f"Effect size {test['effect_size']:.3f} ({test['effect_label']}), Kruskal-Wallis test, "
    f"n = {int(test['n']):,}. {SOURCE_CAPTION} {POPULATION_NOTE}"
)

# 2. Episodes and episode length: one rho each, plus the shape behind it.
st.header("Episodes and episode length")
bins = tables["numeric_bins"]
cols = st.columns(2)
for col, numeric in zip(cols, ["episodes", "duration_min"], strict=True):
    rows = bins[bins["factor"] == numeric].sort_values("order", ascending=False)
    top = best_group(rows)
    test = factor_test(tests, numeric)
    name = FACTOR_NAMES[numeric]
    fig = median_dots(rows, str(top["group"]), "Median score with 95% interval")
    fig.update_yaxes(title=name)
    title = (
        f"{name}: {top['group']} scores highest ({top['median']:.2f}).<br>"
        f"Spearman rho = {test['statistic']:.2f}, n = {int(test['n']):,}"
    )
    col.plotly_chart(style_figure(fig, title, height=360))
    col.caption(
        f"Effect size {test['effect_size']:.3f} ({test['effect_label']}). Titles missing the "
        f"value are left out. {SOURCE_CAPTION}"
    )

# 3. All factors at once: the regression's biggest category and tag effects.
st.header("All factors at once")
coefs = top_coefficients(tables["ols_coefficients"])
biggest = coefs.loc[coefs["size"].idxmax()]
fit = tables["summary"]
fig = go.Figure(
    go.Scatter(
        x=coefs["coef"],
        y=coefs["name"],
        mode="markers",
        marker={"size": 11, "color": highlight_colors(coefs["name"].tolist(), biggest["name"])},
        error_x={
            "type": "data",
            "symmetric": False,
            "array": coefs["ci_high"] - coefs["coef"],
            "arrayminus": coefs["coef"] - coefs["ci_low"],
            "color": MUTED,
            "thickness": 2,
        },
        hovertemplate="%{y}<br>%{x:+.2f} points<extra></extra>",
    )
)
fig.add_vline(x=0, line_color=MUTED)
fig.update_xaxes(title="Change in score vs the reference group, others held fixed")
title = (
    f"Holding the rest fixed, {biggest['name']} moves score the most ({biggest['coef']:+.2f}); "
    f"n = {int(fit['model_n']):,}"
)
st.plotly_chart(style_figure(fig, title, height=560))
st.caption(
    f"The 15 largest category and tag terms of a linear regression (OLS, robust 95% intervals). "
    f"The model explains about {fit['model_r2']:.0%} of score variation on held-out titles. "
    f"{SOURCE_CAPTION}"
)

# 4. Range restriction: tag effects inside the top 250 versus everywhere.
st.header("Inside the top 250")
fit = tables["summary"]
gaps = range_restriction(tables["top250_tags"], tables["tag_effects"])
all_gap = gaps["difference"].abs().mean()
top_gap = gaps["difference_top250"].abs().mean()
fig = go.Figure(
    [
        go.Bar(
            x=gaps["difference"],
            y=gaps["name"],
            orientation="h",
            name="All titles",
            marker_color=MUTED,
            hovertemplate="%{y}<br>All titles: %{x:+.2f}<extra></extra>",
        ),
        go.Bar(
            x=gaps["difference_top250"],
            y=gaps["name"],
            orientation="h",
            name="Top 250",
            marker_color=ACCENT,
            hovertemplate="%{y}<br>Top 250: %{x:+.2f}<extra></extra>",
        ),
    ]
)
fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.1)
fig.update_xaxes(title="Median score with the tag minus without it")
title = (
    f"Inside the top 250, tag score gaps shrink: {all_gap:.2f} points on average in all "
    f"titles, {top_gap:.2f} in the top 250 (n = {fit['population_n']:,} and {fit['top250_n']:,})"
)
fig = style_figure(fig, title, height=620)
fig.update_layout(
    showlegend=True,
    legend={"orientation": "h", "y": 1.0, "yanchor": "bottom", "x": 0},
    margin={"t": 90},
)
st.plotly_chart(fig)
st.caption(
    "When every score is already high, there is little room for a tag to make a difference "
    f"(range restriction). Tags with no top-250 titles are left out. {SOURCE_CAPTION} "
    f"{POPULATION_NOTE}"
)
