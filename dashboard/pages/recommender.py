"""Recommender: search for a title and see the ten most similar shows."""

import pandas as pd
import streamlit as st

from api.data import recommend, search
from dashboard import data
from dashboard.logic import SOURCE_CAPTION, shared_tags, title_label

store = data.store()
catalog = store.catalog

st.title("If you liked this, try these")

query = st.text_input("Search a title (Japanese or English name)", value="Frieren")
matches = search(catalog, query, limit=20) if query.strip() else []
if not matches:
    st.warning(f'No title contains "{query}". Try a shorter or different spelling.')
    st.stop()


picked = st.selectbox(
    "Pick the exact title",
    matches,
    format_func=lambda m: title_label(m["title"], m["type"], m["year"]),
)
mal_id = picked["mal_id"]
query_genres = list(catalog.loc[mal_id, "genres"])
recs = recommend(store, mal_id, k=10)

if not recs:
    # D-052: a real title can have zero picks. Say why instead of showing an empty table.
    st.info(
        f"**{picked['title']}** has no recommendations. A few titles have no synopsis and no "
        "genres or tags that other shows share, so there is nothing to compare them with. "
        "Try another title, like Sousou no Frieren."
    )
    st.stop()

table = pd.DataFrame(recs)
# Type and year go inside the title, and the English title is left out, so the table fits a
# 1280-wide window with no sideways scrolling (D-076). The fixed widths below add up to 800
# pixels, the table's width at 1280; a longer title is cut off at its column's edge.
table["title"] = [title_label(r["title"], r["type"], r["year"]) for r in recs]
table["shared"] = [
    ", ".join(shared_tags(query_genres, list(catalog.loc[rec["mal_id"], "genres"]))) for rec in recs
]
st.subheader(f"{len(recs)} picks for {picked['title']}")
st.dataframe(
    table[["rank", "title", "match_score", "shared", "score"]],
    hide_index=True,
    column_config={
        "rank": st.column_config.NumberColumn("Rank", width=50),
        "title": st.column_config.TextColumn("Title", width=300),
        "score": st.column_config.NumberColumn("Score", format="%.2f", width=60),
        "match_score": st.column_config.ProgressColumn(
            "Match rank (0-1)",
            help=(
                "Where this pick ranks among all candidates for this one title, from 0 "
                "(worst) to 1 (best). It is not a percentage match and cannot be compared "
                "between titles."
            ),
            min_value=0.0,
            max_value=1.0,
            format="%.3f",
            width=150,
        ),
        "shared": st.column_config.TextColumn("Shared genres and tags", width=240),
    },
)
st.caption(
    "Match rank blends synopsis words (70%) and genres and tags (30%), each turned into a "
    "rank within this title's own candidates. A 0.99 means near the top of this list, not "
    "99% similar, so compare it only with the other picks above. Each franchise gets at "
    f"most one slot. {SOURCE_CAPTION}"
)
