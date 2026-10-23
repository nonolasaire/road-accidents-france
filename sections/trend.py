"""Section 5 - Trend 2019-2024: always the full period (the year slider is ignored on purpose)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.filters import Filters, filter_people
from utils.prep import YEARS
from utils.viz import (COLORS, MIN_KILLED, MIN_PEOPLE, MODE_COLORS, NATIONAL_LABEL, PLOTLY_CONFIG, annotate,
                       apply_layout, kicker)

YEARS = list(YEARS)              # plain list for Plotly
FULL = (YEARS[0], YEARS[-1])


@st.cache_data
def yearly(_people: pd.DataFrame, _pop: pd.DataFrame, f: Filters, national: bool = False) -> pd.DataFrame:
    """Per year 2019-2024: killed, killed per million inhabitants, share of 65+ and of cyclists among deaths."""
    k = filter_people(_people, f, national=national, years=FULL)
    k = k[k["killed"]]
    g = k.groupby("year")
    t = pd.DataFrame({
        "killed": g.size(),
        "aged_65": g["age"].apply(lambda s: (s >= 65).mean() * 100),     # among known ages
        "cyclists": g["mode"].apply(lambda s: (s == "Bicycle").mean() * 100),
    }).reindex(YEARS).fillna({"killed": 0})
    pop = _pop if (national or f.is_national) else _pop[_pop["dep"] == f.dep]
    t["per_million"] = t["killed"] / pop.groupby("year")["population"].sum().reindex(YEARS) * 1e6
    return t


def headline(t: pd.DataFrame) -> str:
    """'No real improvement since 2019' / 'Deaths down x% since 2019', plus the ageing toll if the share of 65+
    rose. Neutral title if the yearly counts are too small to compare."""
    first, last = t["killed"].iloc[0], t["killed"].iloc[-1]
    if min(first, last) < MIN_PEOPLE:
        return "Deaths per year, 2019–2024"
    change = (last - first) / first * 100
    title = ("No real improvement since 2019" if abs(change) < 5 else
             f"Deaths {'down' if change < 0 else 'up'} {abs(change):.0f}% since 2019")
    if t["aged_65"].iloc[-1] - t["aged_65"].iloc[0] >= 1:
        title += ", and an ageing toll"
    return title


def killed_chart(t: pd.DataFrame, nat: pd.DataFrame | None, territory: str) -> go.Figure:
    """Line of deaths per year (count nationally, per million inhabitants with the national reference otherwise)."""
    rate = nat is not None
    y = t["per_million"] if rate else t["killed"]
    fig = go.Figure()
    if rate:   # dashed grey national reference, same unit
        fig.add_scatter(x=YEARS, y=nat["per_million"], name=NATIONAL_LABEL, mode="lines+markers",
                        line=dict(color=COLORS["reference"], width=2, dash="dash"), marker=dict(size=8),
                        hovertemplate=f"<b>%{{x}}</b><br>{NATIONAL_LABEL}: %{{y:.1f}} killed per million<extra></extra>")
    fig.add_scatter(x=YEARS, y=y, name=territory, mode="lines+markers",
                    line=dict(color=COLORS["killed"], width=2), marker=dict(size=8), customdata=t[["killed"]],
                    hovertemplate=("<b>%{x}</b><br>Killed: %{customdata[0]:,.0f}"
                                   + ("<br>Per million inhabitants: %{y:.1f}" if rate else "") + "<extra></extra>"))
    annotate(fig, 2020, y.loc[2020], "COVID lockdowns", ax=0, ay=45)
    fig.update_xaxes(dtick=1, showgrid=False)
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout(showlegend=rate)
    return apply_layout(fig, "Year", "Killed per million inhabitants" if rate else "People killed", height=380)


def shares_chart(t: pd.DataFrame, show_cyclists: bool) -> go.Figure:
    """Share of 65+ and of cyclists among deaths per year, with direct labels instead of a legend."""
    series = [("aged_65", "Aged 65+", COLORS["seniors"])]
    if show_cyclists:
        series.append(("cyclists", "Cyclists", MODE_COLORS["Bicycle"]))
    fig = go.Figure()
    for col, label, color in series:
        fig.add_scatter(x=YEARS, y=t[col], name=label, mode="lines+markers+text",
                        line=dict(color=color, width=2), marker=dict(size=8),
                        text=[""] * (len(YEARS) - 1) + [f"  {label}"], textposition="middle right",
                        textfont=dict(color=color), customdata=t[["killed"]],
                        hovertemplate=(f"<b>%{{x}}</b><br>{label}: %{{y:.1f}}% of deaths"
                                       "<br>(out of %{customdata[0]:,.0f} killed)<extra></extra>"))
    fig.update_xaxes(dtick=1, showgrid=False, range=[YEARS[0] - 0.3, YEARS[-1] + 0.9])   # room for the labels
    fig.update_yaxes(rangemode="tozero", ticksuffix="%")
    fig.update_layout(showlegend=False)
    return apply_layout(fig, "Year", "Share of people killed (%)", height=360)


def render(data: dict, f: Filters) -> None:
    people, pop = data["people"], data["population"]
    t = yearly(people, pop, f)
    nat = None if f.is_national else yearly(people, pop, f, national=True)

    kicker("Trend")
    st.header(headline(t))
    st.caption("This section always shows 2019–2024, whatever the year filter; territory and road-user filters apply.")

    # Chart 1: deaths per year
    compare = nat is not None and t["killed"].min() >= MIN_KILLED     # small-number rule for yearly rates
    st.subheader(f"{'Killed per million inhabitants' if compare else 'People killed'} per year, {f.territory}")
    st.plotly_chart(killed_chart(t, nat if compare else None, f.territory), width="stretch", config=PLOTLY_CONFIG)
    if nat is not None and not compare:
        st.caption(f"Fewer than {MIN_KILLED} deaths in at least one year: counts are shown, without a rate "
                   "comparison with France.")
    first, covid, last = (int(t["killed"].loc[y]) for y in (2019, 2020, 2024))
    text = f"{first:,} people killed in 2019, {covid:,} in 2020 and {last:,} in 2024"
    if covid < 0.9 * first and last >= 0.9 * first:          # wording follows the data, not the national story
        text += ": the drop in 2020, during the COVID lockdowns, did not last."
    elif covid < 0.9 * first:
        text += ": deaths fell in 2020, during the COVID lockdowns, and stayed below the 2019 level."
    st.markdown(text + ("." if not text.endswith(".") else ""))
    st.caption(f"Alt text: line chart of {'killed per million inhabitants' if compare else 'people killed'} per "
               f"year in {f.territory} from 2019 to 2024"
               + (f", with {NATIONAL_LABEL} as a dashed grey line" if compare else "")
               + ", with a dip in 2020 annotated 'COVID lockdowns'.")

    # Chart 2: who the dead are, year by year
    st.subheader("Share of seniors and cyclists among people killed")
    show_cyclists = "Bicycle" in f.modes and len(f.modes) > 1      # 100% cyclists would say nothing
    if t["killed"].min() < MIN_PEOPLE:
        st.info(f"Fewer than {MIN_PEOPLE} deaths in at least one year in {f.territory}: yearly shares would "
                "mostly show noise, so they are not drawn.")
    else:
        st.plotly_chart(shares_chart(t, show_cyclists), width="stretch", config=PLOTLY_CONFIG)
        text = f"People aged 65+: **{t['aged_65'].iloc[0]:.1f}%** of deaths in 2019, **{t['aged_65'].iloc[-1]:.1f}%** in 2024."
        if show_cyclists:
            text += f" Cyclists: {t['cyclists'].iloc[0]:.1f}% in 2019, {t['cyclists'].iloc[-1]:.1f}% in 2024."
        st.markdown(text + " The population is also ageing, which is part of the picture.")
        st.caption(f"Alt text: line chart of the share of people aged 65+"
                   + (" and of cyclists" if show_cyclists else "")
                   + f" among people killed each year in {f.territory}, 2019 to 2024.")
    with st.expander("See the data"):
        table = t[["killed", "per_million", "aged_65", "cyclists"]].round(1)
        table.columns = ["Killed", "Killed per million inhabitants", "Aged 65+ (% of deaths)",
                         "Cyclists (% of deaths)"]
        st.dataframe(table, width="stretch")
