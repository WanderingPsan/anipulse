"""The AniPulse dashboard.

    python -m streamlit run dashboard/app.py

Streamlit runs this file from top to bottom on every click. It sets up the page list and
the sidebar, then runs whichever page is open.
"""

import sys
from pathlib import Path

# Streamlit puts this file's folder (dashboard/) on the import path, not the repo root.
# Adding the root lets every page import the project's packages, like api and analysis.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from api.data import ATTRIBUTION  # noqa: E402

PAGES_DIR = Path(__file__).parent / "pages"

st.set_page_config(page_title="AniPulse", layout="wide")

pages = [
    st.Page(PAGES_DIR / "overview.py", title="Overview", default=True),
    st.Page(PAGES_DIR / "predictors.py", title="What predicts a high score?"),
    st.Page(PAGES_DIR / "explore.py", title="Explore"),
    st.Page(PAGES_DIR / "recommender.py", title="Recommender"),
]
page = st.navigation(pages)

# The data license (ODbL) asks for this notice wherever the data is shown.
st.sidebar.caption(f"**Data notice.** {ATTRIBUTION}")

page.run()
