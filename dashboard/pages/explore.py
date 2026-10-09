"""Explore: filter the whole catalog and sort the table by any column."""

import streamlit as st

from dashboard import data
from dashboard.logic import SOURCE_CAPTION, filter_catalog, list_options

catalog = data.store().catalog

st.title("Explore the catalog")

years = catalog["year"].dropna()
first_year, last_year = int(years.min()), int(years.max())

# All filters sit in one row above the table, so the table keeps the full width.
cols = st.columns([2, 2, 2, 2, 1.5])
types = cols[0].multiselect("Type", sorted(catalog["type"].dropna().unique()))
year_range = cols[1].slider("Year", first_year, last_year, (first_year, last_year))
genre = cols[2].selectbox("Genre or tag", list_options(catalog, "genres"), index=None)
studio = cols[3].selectbox("Studio", list_options(catalog, "studios"), index=None)
min_members = cols[4].number_input("Minimum members", min_value=0, value=1000, step=1000)

# The full year range means "any year", which also keeps titles with no year.
chosen_years = None if year_range == (first_year, last_year) else year_range
matches = filter_catalog(catalog, types, chosen_years, genre, studio, int(min_members))

st.write(f"**{len(matches):,}** of {len(catalog):,} titles match.")
table = matches.drop(columns=["mal_id"]).assign(
    genres=matches["genres"].map(", ".join),
    studios=matches["studios"].map(", ".join),
)
st.dataframe(
    table.sort_values("members", ascending=False, na_position="last"),
    hide_index=True,
    height=560,
    column_config={
        "title": "Title",
        "title_english": "English title",
        "type": "Type",
        "year": st.column_config.NumberColumn("Year", format="%d"),
        "score": st.column_config.NumberColumn("Score", format="%.2f"),
        "members": st.column_config.NumberColumn("Members", format="localized"),
        "genres": "Genres and tags",
        "studios": "Studios",
    },
)
st.caption(f"Click a column header to sort. {SOURCE_CAPTION}")
