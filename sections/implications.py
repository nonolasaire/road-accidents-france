"""Section 6 - Implications: where the territory stands out, priorities by type of authority, limitations."""
import math

import pandas as pd
import streamlit as st

from utils.filters import Filters, filter_people, population
from utils.viz import MIN_KILLED, NATIONAL_LABEL, enough_data, kicker

# Indicator name -> (unit suffix, number format)
INDICATORS = {
    "Killed per million inhabitants per year": ("", "{:.1f}"),
    "Killed per 100 people involved": ("", "{:.1f}"),
    "Deaths on departmental roads": ("%", "{:.0f}"),
    "Powered two-wheeler riders among deaths": ("%", "{:.0f}"),
    "People aged 65+ among deaths": ("%", "{:.0f}"),
    "Pedestrians among deaths": ("%", "{:.0f}"),
}
SHORT = {  # card labels short enough not to be cut; the full name is in the tooltip
    "Killed per million inhabitants per year": "Killed per million inhab.",
    "Killed per 100 people involved": "Killed per 100 involved",
    "Deaths on departmental roads": "Dept. roads (% deaths)",
    "Powered two-wheeler riders among deaths": "2-wheelers (% deaths)",
    "People aged 65+ among deaths": "Aged 65+ (% deaths)",
    "Pedestrians among deaths": "Pedestrians (% deaths)",
}


def indicators(people: pd.DataFrame, pop: int) -> dict[str, float]:
    """The six comparison indicators; empty dict under the small-number rule."""
    k = people[people["killed"]]
    if not enough_data(len(people), len(k)):
        return {}
    share = lambda mask: mask.mean() * 100
    return {
        "Killed per million inhabitants per year": len(k) / pop * 1e6,   # pop = person-years
        "Killed per 100 people involved": len(k) / len(people) * 100,
        "Deaths on departmental roads": share(k["road"] == "Departmental road"),
        "Powered two-wheeler riders among deaths": share(k["mode"] == "Powered two-wheeler"),
        "People aged 65+ among deaths": share(k["age"].dropna() >= 65),
        "Pedestrians among deaths": share(k["mode"] == "Pedestrian"),
    }


def fmt(name: str, value: float) -> str:
    unit, pattern = INDICATORS[name]
    return pattern.format(value) + unit


def stand_out(here: dict, nat: dict, n: int = 3) -> list[tuple[str, float]]:
    """The n indicators where the territory is furthest ABOVE the national value, as relative gaps
    (indicators have different units, so the gap is here / national - 1)."""
    gaps = {k: here[k] / nat[k] - 1 for k in here if nat.get(k)}
    return sorted(((k, g) for k, g in gaps.items() if g > 0.05), key=lambda kv: -kv[1])[:n]


def render_stand_out(data: dict, f: Filters) -> None:
    here = indicators(filter_people(data["people"], f), population(data["population"], f))
    nat = indicators(filter_people(data["people"], f, national=True), population(data["population"], f, national=True))
    if f.is_national:
        st.subheader(f"{NATIONAL_LABEL} at a glance, {f.period}")
        st.markdown(" · ".join(f"{name}: **{fmt(name, v)}**" for name, v in here.items()))
        st.caption("Select a département in the sidebar to see the three indicators where it stands furthest "
                   "above the national average.")
        return
    st.subheader(f"Where {f.territory} stands out, {f.period}")
    if not here:
        st.info(f"Not enough data to compare {f.territory} with France for this selection "
                f"(fewer than {MIN_KILLED} deaths).")
        return
    top = stand_out(here, nat)
    if not top:
        st.success(f"{f.territory} is not clearly above the national average on any of the six indicators "
                   "(all within 5% of the national value or below).")
        return
    for col, (name, gap) in zip(st.columns(len(top)), top):
        col.metric(SHORT[name], fmt(name, here[name]), delta=f"+{gap * 100:.0f}%", delta_description="vs France",
                   delta_color="inverse", border=True, help=f"{name}. {NATIONAL_LABEL}: {fmt(name, nat[name])}")
    fewer = (f"Only {len(top)} of the six indicators {'is' if len(top) == 1 else 'are'} more than 5% above "
             "the national value; the others are close to it or below. " if len(top) < 3 else "")
    st.caption(fewer + "Relative gap with France for the same years and road users. Indicators compared: "
               + ", ".join(n.lower() for n in INDICATORS) + ".")


def shares(people: pd.DataFrame) -> dict[str, float]:
    """Figures quoted in the two columns (NaN under the small-number rule)."""
    k = people[people["killed"]]
    ped, bike = k[k["mode"] == "Pedestrian"], k[k["mode"] == "Bicycle"]
    pct = lambda part, whole: part / len(whole) * 100 if len(whole) >= MIN_KILLED else math.nan
    return {
        "dep_road": pct((k["road"] == "Departmental road").sum(), k),
        "ptw": pct((k["mode"] == "Powered two-wheeler").sum(), k),
        "bike_rural": pct((bike["area"] == "Outside urban area").sum(), bike),
        "ped_urban": pct((ped["area"] == "Urban area").sum(), ped),
        "ped_65": pct((ped["age"] >= 65).sum(), ped),
    }


def fact(value: float, text: str) -> str:
    """'61% of deaths ...' or nothing under the small-number rule."""
    return f"- **{value:.0f}%** {text}\n" if not math.isnan(value) else ""


def render_priorities(data: dict, f: Filters) -> None:
    s = shares(filter_people(data["people"], f))
    left, right = st.columns(2)
    with left:
        st.subheader("Départements")
        st.markdown(
            f"*Rural roads, powered two-wheelers, cyclists between towns* — in {f.territory}:\n\n"
            + fact(s["dep_road"], "of deaths on departmental roads")
            + fact(s["ptw"], "of deaths are powered two-wheeler riders")
            + fact(s["bike_rural"], "of cyclists killed died outside urban areas")
            + "\n**Measures to consider**, to assess locally:\n"
              "- speed management and checks on the sections with the most fatal accidents\n"
              "- safer junctions and roadsides (roundabouts, protection of fixed obstacles)\n"
              "- continuous, separated cycle routes between towns\n"
              "- crash barriers designed for motorcyclists on bends"
        )
    with right:
        st.subheader("Communes")
        st.markdown(
            f"*Pedestrians in towns, especially seniors* — in {f.territory}:\n\n"
            + fact(s["ped_urban"], "of pedestrians killed died in urban areas")
            + fact(s["ped_65"], "of pedestrians killed were aged 65 or over")
            + "\n**Measures to consider**, to assess locally:\n"
              "- safer crossings: shorter crossing distances, refuge islands, longer green time\n"
              "- lighting at crossings and clear sight lines\n"
              "- 30 km/h zones around shops, health and services used by seniors\n"
              "- regular audits of walking routes with older residents"
        )
    st.caption("Figures not shown when fewer than 10 deaths are involved. The measures are examples drawn from road "
               "safety practice; this data shows where deaths happen, not which measure would work best locally.")


def render(data: dict, f: Filters) -> None:
    kicker("What to do")
    st.header("Where to act first" + ("" if f.is_national else f" in {f.territory}"))
    render_stand_out(data, f)
    render_priorities(data, f)

    st.subheader("Limits of this analysis")
    st.markdown(
        "- **Correlations, not causes**: the figures show where and for whom deaths happen, not why.\n"
        "- **No exposure data**: traffic volumes (kilometres driven, walked or cycled) are not available, so a group "
        "with many deaths may simply travel more.\n"
        "- **Injuries are under-reported** (police not always called to non-fatal accidents): deaths are complete, "
        "lethality is probably somewhat overstated.\n"
        "- **Population for 2024 is provisional** (INSEE estimates), which affects the 2024 rates per inhabitant."
    )
