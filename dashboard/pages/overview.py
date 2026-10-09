"""Overview: the headline answer, the size of the data, and how it was narrowed down."""

import plotly.graph_objects as go
import streamlit as st

from dashboard import data
from dashboard.logic import POPULATION_NOTE, SOURCE_CAPTION, bin_label_for, score_histogram
from dashboard.style import highlight_colors, style_figure

store = data.store()
tables = data.analysis()
meta = store.metadata

st.title("AniPulse")
st.subheader("Which facts known before an anime airs go with a higher MyAnimeList score?")
# People land here first, so the answer comes before any chart.
st.info(tables["summary"]["headline"])

catalog = store.catalog
cols = st.columns(4)
cols[0].metric("Titles in the catalog", f"{len(catalog):,}")
cols[1].metric("Analysis population", f"{meta.get('analysis_population', 0):,}")
cols[2].metric("Titles with recommendations", f"{store.recommendations['anime_id'].nunique():,}")
cols[3].metric("Data last updated", str(meta.get("data_last_updated", "unknown"))[:10])

# Score distribution, with the bin that holds the median highlighted.
population = catalog[catalog["score"].notna() & (catalog["members"] >= 1000).fillna(False)]
scores = population["score"]
histogram = score_histogram(scores)
median = float(scores.median())
median_bin = bin_label_for(histogram, median)
fig = go.Figure(
    go.Bar(
        # Bars sit at each bin's center on a number axis, so ticks read 5, 6, 7.
        x=histogram["bin_start"] + 0.125,
        y=histogram["count"],
        width=0.22,
        marker_color=highlight_colors(histogram["label"].tolist(), median_bin),
        customdata=histogram["label"],
        hovertemplate="Score %{customdata}<br>%{y:,} titles<extra></extra>",
    )
)
fig.update_xaxes(title="MyAnimeList score")
fig.update_yaxes(title="Titles")
low, high = scores.quantile([0.25, 0.75])
title = (
    f"Half of all titles score between {low:.2f} and {high:.2f}; "
    f"the median is {median:.2f} (n = {len(scores):,})"
)
st.plotly_chart(style_figure(fig, title))
st.caption(f"{SOURCE_CAPTION} {POPULATION_NOTE} The highlighted bar holds the median.")

# The data funnel: every step from the raw CSV to the analysis population.
funnel = tables["funnel"]
labels = funnel["label"].tolist()
last = labels[-1]
fig = go.Figure(
    go.Bar(
        x=funnel["rows"],
        y=labels,
        orientation="h",
        marker_color=highlight_colors(labels, last),
        text=[f"{n:,}" for n in funnel["rows"]],
        textposition="outside",
        hovertemplate="%{y}<br>%{x:,} rows left<extra></extra>",
    )
)
fig.update_yaxes(autorange="reversed")
fig.update_xaxes(title="Rows left after the step")
kept, raw = int(funnel["rows"].iloc[-1]), int(funnel["rows"].iloc[0])
title = f"{kept:,} of {raw:,} raw rows ({kept / raw:.0%}) make it into the analysis"
st.plotly_chart(style_figure(fig, title, height=360))
st.caption(
    f"{SOURCE_CAPTION} Titles without a score, or with fewer than 1,000 members, are kept in "
    "the catalog and the recommender but left out of the score analysis."
)
