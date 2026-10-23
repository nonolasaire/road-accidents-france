"""Section 2 - Where? Killed per inhabitant by département, fatal accidents map, road types."""
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.filters import Filters, filter_people
from utils.prep import ROADS
from utils.viz import (COLORS, MIN_KILLED, NATIONAL_LABEL, PLOTLY_CONFIG, SEQ_RED, TRANSPARENT, apply_layout,
                       enough_data, fmt_int, kicker)

KM_PER_DEG_LAT = 110.57


# ---------- Data ----------

@st.cache_data
def dep_rates(_people: pd.DataFrame, _pop: pd.DataFrame, years: tuple, modes: tuple) -> pd.DataFrame:
    """Killed per million inhabitants per year, by département, for the selected years and road users.
    Cached on (years, modes): the leading underscore tells Streamlit not to hash the large DataFrames
    (they never change during a session)."""
    p = _people[_people["year"].between(*years) & _people["mode"].isin(modes)]
    killed = p[p["killed"]].groupby("dep", observed=False).size()   # observed=False keeps départements with 0
    killed.index = killed.index.astype(str)
    pop = (_pop[_pop["year"].between(*years)]
           .groupby("dep").agg(dep_name=("dep_name", "first"), population=("population", "sum")))
    t = pop.join(killed.rename("killed")).fillna({"killed": 0}).astype({"killed": int})
    # population is summed over the years (person-years), so the rate is per year
    t["rate"] = t["killed"] / t["population"] * 1e6
    t["enough"] = t["killed"] >= MIN_KILLED                          # small-number rule
    t["rank"] = t["rate"].where(t["enough"]).rank(ascending=False, method="min")   # 1 = highest rate
    return t.reset_index()


def ring_area_km2(ring: list) -> float:
    """Area of one polygon ring (lon/lat degrees) in km², with a local flat-earth approximation
    (good enough at the scale of a département) and the shoelace formula."""
    pts = np.array(ring)
    lat0 = math.radians(pts[:, 1].mean())
    x = pts[:, 0] * KM_PER_DEG_LAT * math.cos(lat0)
    y = pts[:, 1] * KM_PER_DEG_LAT
    return abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2


@st.cache_data
def dep_area(_geojson: dict) -> pd.Series:
    """Area of each département in km² (outer rings only; the simplified outlines have no holes)."""
    areas = {}
    for ft in _geojson["features"]:
        geom = ft["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        areas[ft["properties"]["code"]] = sum(ring_area_km2(poly[0]) for poly in polys)
    return pd.Series(areas, name="area_km2")


def density_link(t: pd.DataFrame, area: pd.Series) -> float:
    """Rank correlation between population density and the death rate (départements with enough data).
    Negative = the less densely populated, the higher the rate. Ranks then Pearson = Spearman's rho."""
    ok = t[t["enough"]].set_index("dep")
    # population is summed over the selected years: same factor for every département, so ranks are unchanged
    density = ok["population"] / area.reindex(ok.index)
    return float(ok["rate"].rank().corr(density.rank()))


def road_table(people: pd.DataFrame) -> pd.DataFrame:
    """People involved and killed by road type, with shares and lethality (NaN under the small-number rule)."""
    t = people.groupby("road", observed=False).agg(people=("killed", "size"), killed=("killed", "sum"))
    t["involved_pct"] = t["people"] / t["people"].sum() * 100
    t["deaths_pct"] = t["killed"] / max(t["killed"].sum(), 1) * 100
    t["lethality"] = [k / n * 100 if enough_data(n, k) else math.nan for n, k in zip(t["people"], t["killed"])]
    return t


def plural(road: str) -> str:
    """'Departmental road' -> 'Departmental roads', 'Other' -> 'Other roads'."""
    return "Other roads" if road == "Other" else f"{road}s"


# ---------- Choropleth ----------

def choropleth(t: pd.DataFrame, geojson: dict, selected: str | None) -> go.Figure:
    """Départements coloured by killed per million inhabitants per year; selected one outlined in yellow."""
    ok, low = t[t["enough"]], t[~t["enough"]]
    border = dict(color=COLORS["map_border"], width=0.5)
    fig = go.Figure(go.Choropleth(
        geojson=geojson, featureidkey="properties.code", locations=ok["dep"], z=ok["rate"],
        colorscale=SEQ_RED, marker=dict(line=border),
        customdata=ok[["dep_name", "killed", "rank"]],
        hovertemplate=("<b>%{customdata[0]} (%{location})</b><br>Killed: %{customdata[1]:,}"
                       "<br>Killed per million inhabitants per year: %{z:.1f}"
                       f"<br>Rank: %{{customdata[2]:.0f}} of {len(ok)} (1 = highest rate)<extra></extra>"),
        colorbar=dict(title=dict(text="Killed per million<br>inhabitants per year", side="top",
                                 font=dict(color=COLORS["text_secondary"], size=12)),
                      thickness=12, len=0.6, tickfont=dict(color=COLORS["text_secondary"])),
    ))
    if len(low):   # under the small-number rule: grey, no rate
        fig.add_trace(go.Choropleth(
            geojson=geojson, featureidkey="properties.code", locations=low["dep"], z=np.zeros(len(low)),
            colorscale=[[0, COLORS["grid"]], [1, COLORS["grid"]]], showscale=False, marker=dict(line=border),
            customdata=low[["dep_name", "killed"]],
            hovertemplate="<b>%{customdata[0]} (%{location})</b><br>Not enough data (n = %{customdata[1]} killed)"
                          "<extra></extra>",
        ))
    if selected:   # yellow outline only (transparent fill), drawn on top, no tooltip of its own
        fig.add_trace(go.Choropleth(
            geojson=geojson, featureidkey="properties.code", locations=[selected], z=[0],
            colorscale=[[0, TRANSPARENT], [1, TRANSPARENT]], showscale=False, hoverinfo="skip",
            marker=dict(line=dict(color=COLORS["highlight"], width=2.5)),
        ))
    # Conic conformal (Lambert) is the usual projection for maps of France
    fig.update_geos(fitbounds="locations", visible=False, bgcolor=COLORS["surface"],
                    projection=dict(type="conic conformal", parallels=[44, 49]))
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0), dragmode=False)
    return fig


def render_choropleth(data: dict, f: Filters, t: pd.DataFrame) -> None:
    ok = t[t["enough"]].sort_values("rate", ascending=False)
    rho = density_link(t, dep_area(data["geojson"])) if len(ok) >= 10 else math.nan
    # Headline = the insight, only if the data support it for the current filters
    if rho <= -0.3:
        st.header("Rural départements are the deadliest per inhabitant")
    elif len(ok) >= 2:
        st.header(f"Deaths per inhabitant vary up to ×{ok['rate'].max() / ok['rate'].min():.0f} between départements")
    else:
        st.header("Deaths per inhabitant by département")
    st.subheader(f"Killed per million inhabitants per year, {f.period}")
    st.plotly_chart(choropleth(t, data["geojson"], f.dep), width="stretch")

    national = t["killed"].sum() / t["population"].sum() * 1e6
    top = ", ".join(f"{r.dep_name} ({r.rate:.1f})" for r in ok.head(3).itertuples())
    bottom = ", ".join(f"{r.dep_name} ({r.rate:.1f})" for r in ok.tail(3).itertuples())
    text = (f"Highest rates: {top}. Lowest: {bottom}. {NATIONAL_LABEL}: {national:.1f} killed per million "
            "inhabitants per year.")
    if not math.isnan(rho):
        text += (f" The less densely populated a département, the higher its rate tends to be "
                 f"(rank correlation with density: {rho:.2f})." if rho <= -0.3 else
                 f" The rate is only weakly linked to population density (rank correlation: {rho:.2f}).")
    if not f.is_national:
        row = t.set_index("dep").loc[f.dep]
        text += (f" **{f.territory}: {row.rate:.1f}, rank {row['rank']:.0f} of {len(ok)}.**" if row.enough
                 else f" **{f.territory}: not enough data ({row.killed} killed).**")
    st.markdown(text)
    n_low = int((~t["enough"]).sum())
    st.caption("Rates relate deaths to the resident population (INSEE), but people killed are not always "
               "residents of the département where the accident happened (transit, tourism)."
               + (f" {n_low} départements in grey: fewer than {MIN_KILLED} deaths, no rate shown." if n_low else ""))
    st.caption(f"Alt text: map of the 96 metropolitan départements coloured from dark to bright red by people "
               f"killed per million inhabitants per year, {f.period}"
               + (f" ({n_low} in grey for lack of data)" if n_low else "") + f". Brightest: {top}.")
    with st.expander("See the data"):
        st.dataframe(ok[["dep", "dep_name", "killed", "rate", "rank"]].rename(columns={
            "dep": "Code", "dep_name": "Département", "killed": "Killed",
            "rate": "Killed per million inhabitants per year", "rank": "Rank"}).round(1),
            hide_index=True, width="stretch")


# ---------- Point map ----------

def feature_bounds(geojson: dict, dep: str) -> tuple[dict, tuple[float, float, float, float]]:
    """GeoJSON feature of one département and its bounding box (min lon, min lat, max lon, max lat)."""
    feature = next(ft for ft in geojson["features"] if ft["properties"]["code"] == dep)
    coords = feature["geometry"]["coordinates"]
    rings = coords if feature["geometry"]["type"] == "Polygon" else [r for poly in coords for r in poly]
    pts = np.array([pt for ring in rings for pt in ring])
    return feature, (*pts.min(axis=0), *pts.max(axis=0))


def fatal_map(points: pd.DataFrame, feature: dict, bounds: tuple) -> go.Figure:
    """One red dot per fatal accident, on a dark basemap, with the département outline in yellow."""
    lon0, lat0, lon1, lat1 = bounds
    # Zoom so that the whole département fits: each zoom level halves the visible span
    zoom = float(np.clip(8.6 - math.log2(max(lon1 - lon0, (lat1 - lat0) * 1.4)), 5, 11.5))
    hours = points["hour"].map(lambda h: f"{h:02d}:00–{h:02d}:59")
    fig = go.Figure(go.Scattermap(
        lat=points["lat"], lon=points["long"], mode="markers",
        marker=dict(size=9, color=COLORS["killed"], opacity=0.85),
        customdata=np.stack([points["date"].dt.strftime("%d %b %Y"), hours, points["road"].astype(str),
                             points["killed"], points["victims"]], axis=-1),
        hovertemplate=("<b>%{customdata[0]}, %{customdata[1]}</b><br>%{customdata[2]}"
                       "<br>Killed: %{customdata[3]}<br>Victims: %{customdata[4]}<extra></extra>"),
    ))
    fig.update_layout(
        height=520, margin=dict(l=0, r=0, t=0, b=0),
        map=dict(style="carto-darkmatter", zoom=zoom, center=dict(lon=(lon0 + lon1) / 2, lat=(lat0 + lat1) / 2),
                 layers=[dict(source=feature, type="line", color=COLORS["highlight"], line=dict(width=1.5))]),
    )
    return fig


def render_points(data: dict, f: Filters, people: pd.DataFrame) -> None:
    st.subheader(f"Where people died in {f.territory}" if not f.is_national else "Where exactly do people die?")
    if f.is_national:
        st.info("Choose a département in the sidebar to see each of its fatal accidents on a map.")
        return
    # Accidents with at least one person killed among the filtered road users
    ids = people.loc[people["killed"], "Num_Acc"].unique()
    points = data["fatal_accidents"][data["fatal_accidents"]["Num_Acc"].isin(ids)]
    if points.empty:
        st.info("No fatal accident for this selection.")
        return
    feature, bounds = feature_bounds(data["geojson"], f.dep)
    st.plotly_chart(fatal_map(points, feature, bounds), width="stretch")   # mode bar kept (zoom)
    st.markdown(f"{fmt_int(len(points))} fatal accidents, {f.period}. Each dot is one accident; "
                "hover for the date, road type and victims.")
    st.caption("Positions as recorded by the police. The victims listed are all the people killed in the accident, "
               "including road users outside the current filter.")
    st.caption(f"Alt text: map of {f.territory} with one red dot per fatal accident ({len(points)} dots), "
               f"{f.period}, showing where along the road network people were killed.")


# ---------- Road types ----------

def road_chart(here: pd.DataFrame, nat: pd.DataFrame | None) -> go.Figure:
    """Paired horizontal bars: share of people involved (grey) vs share of deaths (red), by road type."""
    roads = list(here.index)
    leth = [f"{v:.1f} killed per 100 involved" if not math.isnan(v) else f"not enough data (n = {k} killed)"
            for v, k in zip(here["lethality"], here["killed"])]
    nat_txt = ("" if nat is None else
               [f"<br>{NATIONAL_LABEL}: {v:.1f}%" for v in nat["deaths_pct"]])
    fig = go.Figure()
    fig.add_bar(y=roads, x=here["involved_pct"], orientation="h", name="Share of people involved",
                marker_color=COLORS["muted"], customdata=here[["people"]],
                hovertemplate="<b>%{y}</b><br>People involved: %{customdata[0]:,} (%{x:.1f}%)<extra></extra>")
    fig.add_bar(y=roads, x=here["deaths_pct"], orientation="h", name="Share of deaths",
                marker_color=COLORS["killed"], customdata=np.stack([here["killed"], leth], axis=-1),
                hovertemplate=("<b>%{y}</b><br>Killed: %{customdata[0]} (%{x:.1f}% of deaths)"
                               "<br>Lethality: %{customdata[1]}" + ("%{text}" if nat is not None else "") +
                               "<extra></extra>"),
                text=nat_txt if nat is not None else None, textposition="none")
    if nat is not None:   # national reference: outline bar, no fill
        fig.add_bar(y=roads, x=nat["deaths_pct"], orientation="h", name=f"Share of deaths – {NATIONAL_LABEL}",
                    marker=dict(color=TRANSPARENT, line=dict(color=COLORS["reference"], width=1.5)),
                    hovertemplate=f"<b>%{{y}}</b><br>{NATIONAL_LABEL}: %{{x:.1f}}% of deaths<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.05)
    fig.update_yaxes(categoryorder="array", categoryarray=roads, autorange="reversed", showgrid=False)
    fig.update_xaxes(ticksuffix="%", rangemode="tozero")
    return apply_layout(fig, "Share of the total (%)", "Road type", height=380 if nat is None else 460)


def road_sentence(here: pd.DataFrame, people: pd.DataFrame, road: str, territory: str) -> str:
    """Factual text about the road type with the most deaths: shares, then its lethality vs all other roads."""
    row = here.loc[road]
    link = "but" if round(row.deaths_pct) > round(row.involved_pct) else "and"   # "but" only if over-represented
    text = (f"In {territory}, {plural(road).lower()} account for **{row.involved_pct:.0f}%** of the people "
            f"involved in injury accidents {link} **{row.deaths_pct:.0f}%** of the deaths.")
    rest = people[people["road"] != road]
    n, k = len(rest), int(rest["killed"].sum())
    if not math.isnan(row.lethality) and enough_data(n, k):            # no comparison under the small-number rule
        other = k / n * 100
        compare = "more" if row.lethality > other else "less"
        text += (f" An injury accident there is {compare} often fatal: {row.lethality:.1f} killed per 100 people "
                 f"involved, against {other:.1f} on all other roads.")
    return text


def render_roads(f: Filters, people: pd.DataFrame, nat_people: pd.DataFrame | None, top: str) -> None:
    here = road_table(people)
    nat = road_table(nat_people) if nat_people is not None else None
    keep = (nat if nat is not None else here)["people"] > 0          # same rows in both tables
    here = here[keep]
    nat = nat[keep] if nat is not None else None

    # Headline = the road type with the most deaths in the territory (departmental roads nationally, not in Paris);
    # neutral when there are too few deaths to name one
    if here["killed"].sum() >= MIN_KILLED:
        st.header(f"{plural(top)} concentrate the deaths" + ("" if f.is_national else f" in {f.territory}"))
    else:
        st.header("Deaths by road type")
    st.subheader(f"Share of people involved vs share of deaths, by road type, {f.period}")
    if here["killed"].sum() < MIN_KILLED:
        st.info(f"Not enough data for this selection (n = {int(here['killed'].sum())} killed).")
        return
    st.plotly_chart(road_chart(here, nat), width="stretch", config=PLOTLY_CONFIG)

    st.markdown(road_sentence(here, people, top, f.territory))
    row = here.loc[top]
    st.caption(f"Alt text: horizontal bar chart comparing, for each road type, the share of people involved "
               f"(grey) with the share of people killed (red) in {f.territory}, {f.period}"
               + (f", with {NATIONAL_LABEL} as grey outline bars" if nat is not None else "")
               + f". {plural(top)}: {row.involved_pct:.0f}% of people involved, {row.deaths_pct:.0f}% of deaths.")
    with st.expander("See the data"):
        table = here[["people", "killed", "involved_pct", "deaths_pct", "lethality"]].round(1)
        table.columns = ["People involved", "Killed", "Share involved (%)", "Share of deaths (%)",
                         "Killed per 100 involved"]
        st.dataframe(table, width="stretch")


# ---------- Section ----------

def render(data: dict, f: Filters) -> None:
    people = filter_people(data["people"], f)
    nat_people = None if f.is_national else filter_people(data["people"], f, national=True)

    deaths = people[people["killed"]].groupby("road", observed=True).size()
    top = deaths.idxmax() if deaths.sum() >= MIN_KILLED else "Departmental road"

    kicker("Where")
    render_choropleth(data, f, dep_rates(data["people"], data["population"], f.years, f.modes))
    render_points(data, f, people)
    render_roads(f, people, nat_people, top)
