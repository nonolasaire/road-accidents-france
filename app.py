"""Where roads kill: a guide for local authorities. Run with: streamlit run app.py"""
import json

import pandas as pd
import streamlit as st

from sections import implications, intro, quality, trend, when, where, who
from utils.filters import NATIONAL, Filters
from utils.io import PROCESSED_DIR
from utils.viz import MODE_ORDER

st.set_page_config(page_title="Where roads kill", page_icon="🛑", layout="centered")  # centered = article-like


@st.cache_data
def load_data() -> dict:
    """Read the processed files once (cached across reruns and users). Built by scripts/build_data.py."""
    data = {name: pd.read_parquet(PROCESSED_DIR / f"{name}.parquet")
            for name in ["people", "fatal_accidents", "population"]}
    data["quality"] = json.loads((PROCESSED_DIR / "quality.json").read_text(encoding="utf-8"))
    data["geojson"] = json.loads((PROCESSED_DIR / "departements.geojson").read_text(encoding="utf-8"))
    return data


def sidebar(data: dict) -> Filters:
    """Global controls; every section reads the returned Filters."""
    st.sidebar.header("Explore")
    names = data["population"].drop_duplicates("dep").set_index("dep")["dep_name"].sort_index()

    dep = st.sidebar.selectbox(
        "Territory", [None, *names.index],
        format_func=lambda d: NATIONAL if d is None else f"{d} – {names[d]}",
        help="Choose a département to see its figures next to the national ones.",
    )
    years = st.sidebar.slider("Years", 2019, 2024, (2019, 2024),
                              help="Filters every section except the trend, which always shows 2019–2024.")
    # Empty selection = all road users (incl. Other/Unknown, so that totals match the official ONISR figures).
    # This keeps the widget on one line by default instead of 8 chips.
    modes = st.sidebar.multiselect("Road users", MODE_ORDER, default=[], placeholder="All road users",
                                   help="Leave empty to include everyone.")
    modes = modes or MODE_ORDER

    st.sidebar.caption("Source: ONISR road accident files (data.gouv.fr), INSEE population estimates.")
    return Filters(dep=dep, dep_name=None if dep is None else names[dep], years=years, modes=tuple(modes))


data = load_data()
filters = sidebar(data)

# Storyboard order: Hook + KPIs (+ context) -> Where -> Who -> When -> Trend -> Implications -> Data quality
for section in [intro, where, who, when, trend, implications, quality]:
    section.render(data, filters)
