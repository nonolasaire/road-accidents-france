"""Section 3 - Who? Road users (share involved vs share of deaths) and age group × road user lethality."""
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.filters import Filters, group_table
from utils.prep import AGE_GROUPS
from utils.viz import (COLORS, MIN_KILLED, MIN_PEOPLE, MODE_COLORS, MODE_ORDER, NATIONAL_LABEL, PLOTLY_CONFIG,
                       SEQ_RED, TRANSPARENT, annotate, apply_layout, kicker)

MAIN_MODES = [m for m in MODE_ORDER if m not in ("Other", "Unknown")]
GROUP_NAMES = {"Pedestrian": "pedestrians", "Bicycle": "cyclists", "E-scooter / PMD": "e-scooter users",
               "Powered two-wheeler": "powered two-wheeler riders", "Car / van": "car occupants",
               "Heavy vehicle / bus": "heavy-vehicle occupants"}
SHORT_MODE = {"Pedestrian": "Pedestrian", "Bicycle": "Bicycle", "E-scooter / PMD": "E-scooter",
              "Powered two-wheeler": "2-wheeler", "Car / van": "Car / van", "Heavy vehicle / bus": "Heavy veh."}
OVER = 1.2   # "over-represented" = share of deaths at least 1.2× the share of people involved


def join_names(names: list[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b and c'."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def over_represented(t: pd.DataFrame) -> list[str]:
    """Road users whose share of deaths exceeds their share of people involved (small-number rule applied),
    most over-represented first."""
    t = t.loc[[m for m in MAIN_MODES if m in t.index]]
    t = t[t["lethality"].notna() & (t["deaths_pct"] >= OVER * t["involved_pct"])]
    return list((t["deaths_pct"] / t["involved_pct"]).sort_values(ascending=False).index)


# ---------- Road users ----------

def mode_chart(here: pd.DataFrame, nat: pd.DataFrame | None) -> go.Figure:
    """Paired horizontal bars: share involved (grey) vs share of deaths (road-user colour)."""
    modes = list(here.index)
    leth = [f"{v:.1f} killed per 100 involved" if not math.isnan(v) else f"not enough data (n = {k} killed)"
            for v, k in zip(here["lethality"], here["killed"])]
    nat_txt = [f"<br>{NATIONAL_LABEL}: {v:.1f}% of deaths" for v in nat["deaths_pct"]] if nat is not None else None
    fig = go.Figure()
    fig.add_bar(y=modes, x=here["involved_pct"], orientation="h", name="Share of people involved",
                marker_color=COLORS["muted"], customdata=here[["people"]],
                hovertemplate="<b>%{y}</b><br>People involved: %{customdata[0]:,} (%{x:.1f}%)<extra></extra>")
    fig.add_bar(y=modes, x=here["deaths_pct"], orientation="h", name="Share of deaths (colour = road user)",
                marker_color=[MODE_COLORS[m] for m in modes], customdata=np.stack([here["killed"], leth], axis=-1),
                text=nat_txt, textposition="none",
                hovertemplate=("<b>%{y}</b><br>Killed: %{customdata[0]} (%{x:.1f}% of deaths)"
                               "<br>Lethality: %{customdata[1]}" + ("%{text}" if nat is not None else "")
                               + "<extra></extra>"))
    if nat is not None:   # national reference: outline bars
        fig.add_bar(y=modes, x=nat["deaths_pct"], orientation="h", name=f"Share of deaths – {NATIONAL_LABEL}",
                    marker=dict(color=TRANSPARENT, line=dict(color=COLORS["reference"], width=1.5)),
                    hovertemplate=f"<b>%{{y}}</b><br>{NATIONAL_LABEL}: %{{x:.1f}}% of deaths<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.05)
    fig.update_yaxes(categoryorder="array", categoryarray=modes, autorange="reversed", showgrid=False)
    fig.update_xaxes(ticksuffix="%", rangemode="tozero")
    return apply_layout(fig, "Share of the total (%)", "Road user", height=400 if nat is None else 480)


def render_modes(data: dict, f: Filters) -> None:
    t = group_table(data["people"], f, "mode")
    nat = None if f.is_national else group_table(data["people"], f, "mode", national=True)
    # Same rows for the territory and the reference: main road users present in the selection
    rows = [m for m in MAIN_MODES if m in f.modes and (nat if nat is not None else t).loc[m, "people"] > 0]
    here = t.loc[rows]

    st.subheader(f"Share of people involved vs share of deaths, by road user, {f.period}")
    if t["killed"].sum() < MIN_KILLED:
        st.info(f"Not enough data for this selection (n = {int(t['killed'].sum())} killed).")
        return
    st.plotly_chart(mode_chart(here, nat.loc[rows] if nat is not None else None), width="stretch",
                    config=PLOTLY_CONFIG)

    over = over_represented(t)
    if over:
        top = t.loc[over[0]]
        st.markdown(f"In {f.territory}, {GROUP_NAMES[over[0]]} make up **{top.involved_pct:.0f}%** of the people "
                    f"involved in injury accidents but **{top.deaths_pct:.0f}%** of the deaths "
                    f"({top.lethality:.1f} killed per 100 involved, against "
                    f"{t['killed'].sum() / t['people'].sum() * 100:.1f} on average).")
    hidden = t.loc[["Other", "Unknown"], "deaths_pct"].sum()
    st.caption(f"Other vehicles (tractors, quads, special vehicles) and unknown vehicle types: {hidden:.1f}% of "
               "deaths, not shown.")
    st.caption(f"Alt text: horizontal bar chart comparing, for each road user, the share of people involved (grey) "
               f"with the share of people killed (in the road user's colour) in {f.territory}, {f.period}"
               + (f", with {NATIONAL_LABEL} as grey outline bars" if nat is not None else "")
               + (f". Over-represented among deaths: {join_names([GROUP_NAMES[m] for m in over])}." if over else "."))
    with st.expander("See the data"):
        table = here[["people", "killed", "involved_pct", "deaths_pct", "lethality"]].round(1)
        table.columns = ["People involved", "Killed", "Share involved (%)", "Share of deaths (%)",
                         "Killed per 100 involved"]
        st.dataframe(table, width="stretch")


# ---------- Age group × road user ----------

def cell_texts(t: pd.DataFrame, nat: pd.DataFrame | None, modes: list[str]) -> np.ndarray:
    """Tooltip text for every cell (rows = age groups, columns = road users)."""
    texts = []
    for age in AGE_GROUPS:
        row = []
        for m in modes:
            c = t.loc[(age, m)]
            head = f"<b>{m}, {age} years</b><br>"
            if math.isnan(c.lethality):
                body = f"Not enough data (n = {int(c.people)} involved, {int(c.killed)} killed)"
            else:
                body = (f"Killed per 100 involved: {c.lethality:.1f}<br>Killed: {int(c.killed):,}"
                        f"<br>People involved: {int(c.people):,}")
            if nat is not None and not math.isnan(nat.loc[(age, m), "lethality"]):
                body += f"<br>{NATIONAL_LABEL}: {nat.loc[(age, m), 'lethality']:.1f} per 100"
            row.append(head + body)
        texts.append(row)
    return np.array(texts)


def age_heatmap(t: pd.DataFrame, nat: pd.DataFrame | None, modes: list[str], avg: float) -> go.Figure:
    """Lethality by age group × road user; cells under the small-number rule in grey."""
    z = t["lethality"].unstack().reindex(index=AGE_GROUPS, columns=modes)
    fig = go.Figure()
    # Grey layer underneath: visible where the main layer has no value (small-number rule)
    fig.add_heatmap(x=modes, y=AGE_GROUPS, z=np.ones(z.shape), colorscale=[[0, COLORS["grid"]], [1, COLORS["grid"]]],
                    showscale=False, hoverinfo="skip", xgap=2, ygap=2)
    fig.add_heatmap(
        x=modes, y=AGE_GROUPS, z=z.values, colorscale=SEQ_RED, xgap=2, ygap=2, hoverongaps=True,
        customdata=cell_texts(t, nat, modes), hovertemplate="%{customdata}<extra></extra>",
        colorbar=dict(title=dict(text="Killed per 100<br>people involved", side="top",
                                 font=dict(color=COLORS["text_secondary"], size=12)),
                      thickness=12, len=0.8, tickfont=dict(color=COLORS["text_secondary"])),
    )
    # Values written in the cells (colour never carries meaning alone). A text layer instead of the heatmap's
    # own texttemplate, so that bright cells get dark text and dark cells light text (readable contrast).
    cells = z.stack().dropna()                                # empty when every cell is under the rule
    bright = cells > cells.min() + 0.6 * (cells.max() - cells.min()) if len(cells) else cells.astype(bool)
    fig.add_scatter(x=cells.index.get_level_values(1).astype(str), y=cells.index.get_level_values(0).astype(str),
                    mode="text",
                    text=[f"{v:.1f}" for v in cells], hoverinfo="skip", showlegend=False,
                    textfont=dict(size=12, color=[COLORS["background"] if b else COLORS["text"] for b in bright]))
    # 75+ is the top row (y not reversed), so the callout sits in the top margin, clear of the x-axis labels
    if "Pedestrian" in modes and not math.isnan(z.loc["75+", "Pedestrian"]):
        v = z.loc["75+", "Pedestrian"]
        annotate(fig, "Pedestrian", "75+", f"Pedestrians 75+: ×{v / avg:.1f} the average", ax=45, ay=-42,
                 xanchor="left", yanchor="bottom", standoff=12)   # standoff: arrow stops before the cell value
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(showgrid=False, tickangle=0, tickvals=modes, ticktext=[SHORT_MODE[m] for m in modes])
    fig.update_layout(margin=dict(t=70))
    return apply_layout(fig, "Road user", "Age group (years)", height=490)


def render_ages(data: dict, f: Filters) -> None:
    by = ["age_group", "mode"]
    t = group_table(data["people"], f, by)
    nat = None if f.is_national else group_table(data["people"], f, by, national=True)
    ages = group_table(data["people"], f, "age_group")
    total = group_table(data["people"], f, "mode")
    avg = total["killed"].sum() / max(total["people"].sum(), 1) * 100
    modes = [m for m in MAIN_MODES if m in f.modes]

    seniors = ages.loc["75+"]
    if not math.isnan(seniors.lethality) and avg > 0:
        st.subheader(f"At 75 and over, an injury accident is {seniors.lethality / avg:.1f}× as likely to be fatal")
    else:
        st.subheader("Lethality by age group and road user")
    st.caption(f"Killed per 100 people involved, by age group and road user, {f.territory}, {f.period}")
    if total["killed"].sum() < MIN_KILLED:
        st.info(f"Not enough data for this selection (n = {int(total['killed'].sum())} killed).")
        return
    st.plotly_chart(age_heatmap(t, nat, modes, avg), width="stretch", config=PLOTLY_CONFIG)

    text = f"Average lethality in {f.territory}: {avg:.1f} killed per 100 people involved."
    if not math.isnan(seniors.lethality):
        text += f" Among people aged 75+: {seniors.lethality:.1f}."
    st.markdown(text + " Physical frailty is a known factor: for the same impact, older people are more likely "
                "to die of their injuries. These figures show an association, not a cause.")
    unknown = ages.loc["Unknown", "people"] / max(ages["people"].sum(), 1) * 100
    st.caption(f"Grey cells: fewer than {MIN_PEOPLE} people involved or {MIN_KILLED} deaths, no rate shown. "
               f"People of unknown age ({unknown:.1f}% of people involved) are left out.")
    st.caption(f"Alt text: heatmap of lethality (killed per 100 people involved) by age group (rows, 0-17 at the bottom to 75+ at the top) "
               f"and road user (columns), {f.territory}, {f.period}; brighter red = more often fatal. "
               "The brightest cells are for the oldest age groups.")
    with st.expander("See the data"):
        table = t[["people", "killed", "lethality"]].reset_index()
        table = table[table["age_group"].isin(AGE_GROUPS) & table["mode"].isin(modes)].round(1)
        table.columns = ["Age group", "Road user", "People involved", "Killed", "Killed per 100 involved"]
        st.dataframe(table, hide_index=True, width="stretch")


# ---------- Section ----------

def render(data: dict, f: Filters) -> None:
    kicker("Who")
    t = group_table(data["people"], f, "mode")
    over = over_represented(t)
    if over:
        names = join_names([GROUP_NAMES[m] for m in over[:3]])
        st.header(f"{names[0].upper() + names[1:]} pay a higher price than their share of accidents")
    else:
        st.header("Who is killed on the roads")
    render_modes(data, f)
    render_ages(data, f)
