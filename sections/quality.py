"""Section 7 - Data quality and methodology (reads data["quality"], built by scripts/build_data.py)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.filters import Filters
from utils.viz import COLORS, MIN_KILLED, MIN_PEOPLE, PLOTLY_CONFIG, apply_layout, fmt_int, kicker

VARIABLES = {  # BAAC column -> readable name, for the missing-values chart
    "lum": "Light conditions (lum)", "agg": "Urban / rural area (agg)", "catr": "Road type (catr)",
    "catu": "User category (catu)", "grav": "Injury severity (grav)", "catv": "Vehicle category (catv)",
    "an_nais": "Year of birth (an_nais)", "lat": "Latitude (lat)", "long": "Longitude (long)",
}
DROPPED = ("lartpc (100% empty), occutc (99%), v2 (92%), larrout (74%), pr / pr1 (~42%), v1 (23%), "
           "pedestrian-only locp / actp / etatp, secu2 / secu3")


def per_year(q: dict, key: str, sub: str) -> dict[str, int]:
    """One value per year from quality.json, e.g. per_year(q, 'rows_removed', 'people_overseas')."""
    return {y: v[key].get(sub, 0) for y, v in q["per_year"].items()}


def render_sources(q: dict) -> None:
    st.subheader("Sources")
    st.markdown(
        "- **Road accidents**: ONISR / Ministère de l'Intérieur, *Bases de données annuelles des accidents "
        "corporels de la circulation routière* (BAAC), 2019–2024, "
        "[data.gouv.fr](https://www.data.gouv.fr/fr/datasets/53698f4ca3a729239d2036df/), Licence Ouverte 2.0.\n"
        "- **Population**: INSEE, *Estimations de population au 1er janvier par département*, January 2026 edition "
        "([insee.fr](https://www.insee.fr/fr/statistiques/8721456)). 2019–2023 are final, **2024 is provisional**.\n"
        "- **Département outlines**: IGN Admin Express with INSEE codes, simplified "
        "([france-geojson](https://github.com/gregoiredavid/france-geojson)), Licence Ouverte.\n"
        f"- Final dataset: **{fmt_int(q['final_rows']['people'])} people involved** in metropolitan France and "
        f"{fmt_int(q['final_rows']['fatal_accidents'])} fatal accidents with coordinates."
    )


def render_validation(q: dict) -> None:
    st.subheader("Deaths match the official ONISR figures every year")
    rows = [{"Year": y, "Killed in this app": v["data"], "Official ONISR figure": v["onisr"],
             "Match": "✓" if v["match"] else "✗"} for y, v in q["killed_vs_onisr"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("People killed within 30 days in metropolitan France. The build script stops if any year differs.")


def render_rows(q: dict) -> None:
    st.subheader("Rows per table and integrity checks")
    rows = pd.DataFrame({y: v["rows_raw"] for y, v in q["per_year"].items()}).T
    rows.columns = [f"{c} (rows)" for c in rows.columns]
    st.dataframe(rows, width="stretch")
    checks = pd.DataFrame({y: v["integrity"] for y, v in q["per_year"].items()})
    checks.index = checks.index.str.replace("_", " ").str.capitalize()
    st.dataframe(checks, width="stretch")
    st.caption("Raw files, all territories. Duplicates and orphans (child rows without an accident) are 0 except "
               "the identical rows explained below. 'Duplicate people' cannot be checked for 2019–2020: those "
               "files have no person identifier.")


def render_cleaning(q: dict) -> None:
    lieux = per_year(q, "rows_removed", "lieux_extra_roads_at_intersections")
    overseas = sum(per_year(q, "rows_removed", "people_overseas").values())
    severity = sum(per_year(q, "rows_removed", "people_unknown_severity").values())
    usagers = per_year(q, "integrity", "identical_rows_usagers")
    ages = {y: v["implausible_age_set_unknown"] for y, v in q["per_year"].items()}
    multi = {y: n for y, n in lieux.items() if n}
    st.subheader("Cleaning decisions")
    st.markdown(
        "- **Text clean-up**: every value is quoted text with stray spaces, including non-breaking spaces; they are "
        "stripped. Missing markers (`-1`, `N/A`, empty) become missing values.\n"
        "- **One road per accident**: when an accident happens at a junction, the `lieux` table has one row per road. "
        "The main road is kept (lowest road category: motorway < national < departmental < municipal). "
        f"Such rows exist only from 2023: {', '.join(f'{fmt_int(n)} rows removed in {y}' for y, n in multi.items())}; "
        "every accident is kept.\n"
        "- **Département codes** are padded to 2 characters (`1` in 2019, `01` afterwards); `2A`/`2B` kept. "
        f"Metropolitan France = 2-character codes: {fmt_int(overseas)} people in overseas territories left out.\n"
        f"- **Unknown injury severity**: {fmt_int(severity)} people left out of all severity figures.\n"
        f"- **Identical rows in `usagers`** for 2019 ({usagers.get('2019', 0)}) and 2020 ({usagers.get('2020', 0)}) "
        "are kept: these years have no person identifier, so two passengers of the same age and sex in the same "
        "vehicle look identical. The exact match with ONISR deaths confirms they are real people.\n"
        f"- **Implausible birth years** (born in 1900–1901, a placeholder): {sum(ages.values())} people "
        f"({', '.join(f'{n} in {y}' for y, n in ages.items() if n)}) set to unknown age; none of them was killed.\n"
        f"- **Dropped columns** (too empty or out of scope): {DROPPED}.\n"
        "- **No imputation**: missing values stay in an *Unknown* category "
        f"(age group {q['unknown_categories_pct']['age_group']:.1f}%, road user "
        f"{q['unknown_categories_pct']['mode']:.2f}% of people involved).\n"
        f"- **Small-number rule**: no rate is shown below {MIN_PEOPLE} people involved or {MIN_KILLED} deaths; "
        "such cells are greyed out or marked *Not enough data*."
    )


def missing_chart(q: dict) -> go.Figure:
    m = pd.DataFrame(q["missing_total"]).T.rename(index=VARIABLES).sort_values("share_pct")
    fig = go.Figure(go.Bar(
        y=m.index, x=m["share_pct"], orientation="h", marker_color=COLORS["muted"],
        text=[f"{v:.2f}%" for v in m["share_pct"]], textposition="outside", customdata=m[["count"]],
        hovertemplate="<b>%{y}</b><br>Missing: %{customdata[0]:,.0f} (%{x:.2f}%)<extra></extra>",
    ))
    fig.update_layout(bargap=0.3)
    fig.update_xaxes(ticksuffix="%", rangemode="tozero", range=[0, max(m["share_pct"].max() * 1.3, 0.5)])
    fig.update_yaxes(showgrid=False)
    return apply_layout(fig, "Missing values (% of people involved)", "Variable", height=380)


def render_missing(q: dict) -> None:
    st.subheader("Very few missing values in the variables used")
    st.plotly_chart(missing_chart(q), width="stretch", config=PLOTLY_CONFIG)
    worst = max(q["missing_total"].items(), key=lambda kv: kv[1]["share_pct"])
    st.caption(f"Alt text: horizontal bar chart of the share of missing values for each variable used, after "
               f"cleaning, all years. The highest is {VARIABLES[worst[0]]} at {worst[1]['share_pct']:.2f}%; "
               "the others are close to 0%.")


def render(data: dict, f: Filters) -> None:
    q = data["quality"]
    kicker("Method")
    st.header("Data quality & methodology: every death is accounted for")
    render_sources(q)
    render_validation(q)
    render_cleaning(q)
    render_missing(q)
    with st.expander("See the row counts and integrity checks"):
        render_rows(q)
