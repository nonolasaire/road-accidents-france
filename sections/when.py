"""Section 4 - When? Deaths by hour of day × day of week, and night vs day lethality."""
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.filters import Filters, group_table
from utils.prep import DAYS
from utils.viz import COLORS, MIN_KILLED, NATIONAL_LABEL, PLOTLY_CONFIG, SEQ_RED, apply_layout, kicker

HOURS = list(range(24))
MIN_KILLED_HEATMAP = 50   # below this, 168 cells are mostly 0 or 1: the pattern would be noise
RUSH = [7, 8, 9, 17, 18, 19]                                   # weekday rush hours
WEEKEND_NIGHT = {("Friday", h) for h in (22, 23)} | {("Saturday", h) for h in (*range(6), 22, 23)} \
                | {("Sunday", h) for h in range(6)}            # Friday 22:00 to Sunday 05:59


def hour_label(h: int) -> str:
    return f"{h:02d}:00–{h:02d}:59"


def night_vs_day(t: pd.DataFrame) -> tuple[float, float]:
    """Lethality at night (no daylight: lum 3-5) and the rest of the time (daylight, dusk/dawn).
    NaN under the small-number rule or if absent. t is grouped by the nullable 'night' column (NA dropped)."""
    return t["lethality"].get(True, math.nan), t["lethality"].get(False, math.nan)


def full_grid(t: pd.DataFrame) -> pd.DataFrame:
    """All 7 × 24 cells with plain str/int keys (the grouped table uses a categorical day and int8 hours)."""
    t = t.reset_index().astype({"day_of_week": str, "hour": int}).set_index(["day_of_week", "hour"])
    grid = t.reindex(pd.MultiIndex.from_product([DAYS, HOURS], names=["day_of_week", "hour"]))
    return grid.fillna({"people": 0, "killed": 0})


def time_shares(t: pd.DataFrame) -> tuple[float, float]:
    """Share of deaths during weekday rush hours and during weekend nights."""
    k = t["killed"]
    total = max(k.sum(), 1)
    rush = sum(k.get((d, h), 0) for d in DAYS[:5] for h in RUSH)
    night = sum(k.get(key, 0) for key in WEEKEND_NIGHT)
    return rush / total * 100, night / total * 100


def heatmap(t: pd.DataFrame) -> go.Figure:
    """Deaths by day (rows) and hour (columns); lethality in the tooltip when the rule allows it."""
    z = t["killed"].unstack().reindex(index=DAYS, columns=HOURS)
    texts = [[f"<b>{d}, {hour_label(h)}</b><br>Killed: {int(t.loc[(d, h), 'killed'])}"
              f"<br>People involved: {int(t.loc[(d, h), 'people']):,}<br>"
              + (f"Killed per 100 involved: {t.loc[(d, h), 'lethality']:.1f}"
                 if not math.isnan(t.loc[(d, h), "lethality"]) else "Lethality: not enough data")
              for h in HOURS] for d in DAYS]
    fig = go.Figure(go.Heatmap(
        x=HOURS, y=DAYS, z=z.values, colorscale=SEQ_RED, xgap=1, ygap=1,
        customdata=np.array(texts), hovertemplate="%{customdata}<extra></extra>",
        colorbar=dict(title=dict(text="Killed", side="top", font=dict(color=COLORS["text_secondary"], size=12)),
                      thickness=12, len=0.8, tickfont=dict(color=COLORS["text_secondary"])),
    ))
    fig.update_xaxes(tickvals=list(range(0, 24, 3)), ticktext=[f"{h:02d}h" for h in range(0, 24, 3)], showgrid=False)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return apply_layout(fig, "Hour of day", "Day of week", height=380)


def render(data: dict, f: Filters) -> None:
    people = data["people"]
    t = full_grid(group_table(people, f, ["day_of_week", "hour"]))
    nd = group_table(people, f, "night")
    night, day = night_vs_day(nd)
    killed = int(t["killed"].sum())

    kicker("When")
    ratio = night / day if not (math.isnan(night) or math.isnan(day)) else math.nan
    if not math.isnan(ratio) and ratio >= 1.1:
        st.header(f"Risk is spread over the week, with deadlier nights (×{ratio:.1f})")
    else:
        st.header("Risk is spread over the week and over the day")
    st.subheader(f"People killed by hour of day and day of week, {f.period}")

    if killed < MIN_KILLED_HEATMAP:
        st.info(f"Only {killed} death{'s' if killed != 1 else ''} in this selection: too few to read an "
                "hour × day pattern.")
    else:
        st.plotly_chart(heatmap(t), width="stretch", config=PLOTLY_CONFIG)
        rush, wk_night = time_shares(t)
        peak = t["killed"].idxmax()
        st.markdown(
            f"The deadliest time slot is **{peak[0]}, {hour_label(peak[1])}** ({int(t['killed'].max())} deaths). "
            f"Weekday rush hours (07:00–09:59 and 17:00–19:59) account for **{rush:.0f}%** of deaths, for 18% of "
            f"the hours of the week; weekend nights (Friday 22:00 to Sunday 05:59) for **{wk_night:.0f}%**, for 10% "
            "of the hours. These shares also reflect how many people are on the road at those times.")
        st.caption(f"Alt text: heatmap of people killed by hour of day (columns, 0 to 23 h) and day of week "
                   f"(rows, Monday to Sunday) in {f.territory}, {f.period}; brighter red = more deaths. "
                   f"Deadliest slot: {peak[0]} {hour_label(peak[1])}.")

    if not math.isnan(ratio):
        text = (f"At night (no daylight), **{night:.1f}** people are killed per 100 people involved, against "
                f"**{day:.1f}** in daylight or at dusk/dawn: an injury accident at night is **{ratio:.1f}×** as "
                "likely to be fatal.")
        if not f.is_national:
            n_nat, d_nat = night_vs_day(group_table(people, f, "night", national=True))
            if not (math.isnan(n_nat) or math.isnan(d_nat)):
                text += f" {NATIONAL_LABEL}: ×{n_nat / d_nat:.1f}."
        st.markdown(text)
    else:
        st.caption(f"Night vs day lethality: not enough data (fewer than {MIN_KILLED} deaths in one of the two).")

    if killed >= MIN_KILLED_HEATMAP:
        with st.expander("See the data"):
            table = t["killed"].unstack().reindex(index=DAYS, columns=HOURS)
            table.columns = [f"{h:02d}h" for h in HOURS]
            st.dataframe(table, width="stretch")
