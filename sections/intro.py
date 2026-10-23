"""Section 0 - Hook (two key numbers) and KPI row; section 1 - context."""
import math

import pandas as pd
import streamlit as st

from utils.filters import Filters, filter_people, population
from utils.viz import COLORS, MIN_KILLED, MODE_ORDER, NATIONAL_LABEL, enough_data, fmt_int

FIRST_YEAR = 2019


# ---------- Indicators ----------

def kpis(people: pd.DataFrame, pop: int | None = None) -> dict:
    """Headline indicators for one subset of people (rates are NaN under the small-number rule)."""
    killed = people[people["killed"]]
    n_people, n_killed = len(people), len(killed)
    ok = enough_data(n_people, n_killed)
    return {
        "killed": n_killed,
        # pop is summed over the selected years (person-years), so this is already "per year"
        "per_million": n_killed / pop * 1e6 if pop else math.nan,
        "lethality": n_killed / n_people * 100 if ok else math.nan,
        "dep_road": (killed["road"] == "Departmental road").mean() * 100 if ok else math.nan,
        # mean() skips unknown ages: share among the killed whose age is known
        "aged_65": (killed["age"] >= 65).mean() * 100 if ok else math.nan,
    }


def hook_figures(people: pd.DataFrame) -> dict:
    """The two numbers of the hook (all road users): share of deaths on departmental roads,
    and share of pedestrians killed aged 65+."""
    killed = people[people["killed"]]
    ped = killed[killed["mode"] == "Pedestrian"]
    return {
        "dep_road": (killed["road"] == "Departmental road").mean() * 100 if len(killed) >= 10 else math.nan,
        "ped_65": (ped["age"] >= 65).mean() * 100 if len(ped) >= 10 else math.nan,
        "n_killed": len(killed),
        "n_ped": len(ped),
    }


# ---------- Hook ----------

def in_ten(share: float) -> tuple[str, str]:
    """61 -> ('6 in 10', ''); under 1 in 10 (e.g. Paris, no departmental roads), '0 in 10' would read
    oddly, so use a percentage: ('3%', 'of ')."""
    n = round(share / 10)
    return (f"{n} in 10", "") if n >= 1 else (f"{share:.0f}%", "of ")


def one_in(share: float) -> tuple[str, str]:
    """52 -> ('1 in 2', 'is'); above 2 in 3, '1 in 1' would be wrong, so use a percentage instead."""
    n = round(100 / share)
    return (f"1 in {n}", "is") if n >= 2 else (f"{share:.0f}%", "are")


def hook_card(big: str, text: str, note: str) -> None:
    """One hook number: big red figure, one line of text, grey note."""
    st.markdown(
        f"""<div style="background:{COLORS['surface']};border-radius:8px;padding:1rem 1.2rem;height:100%">
        <div style="font-size:2.6rem;font-weight:700;line-height:1.1;color:{COLORS['killed']}">{big}</div>
        <div style="color:{COLORS['text']};font-size:1.1rem;margin:.3rem 0">{text}</div>
        <div style="color:{COLORS['text_secondary']};font-size:.9rem">{note}</div></div>""",
        unsafe_allow_html=True,
    )


def render_hook(people: pd.DataFrame, f: Filters) -> None:
    """Two numbers every local authority should know (territory and years filters, all road users)."""
    here = hook_figures(filter_people(people, f, modes=False))
    nat = hook_figures(filter_people(people, f, national=True, modes=False)) if not f.is_national else None

    def note(key: str, n: int, what: str) -> str:
        if math.isnan(here[key]):
            return f"Not enough data ({what}: {n})"
        base = f"{here[key]:.0f}% · {f.territory}, {f.period}"
        return base if nat is None else f"{base} · {NATIONAL_LABEL}: {nat[key]:.0f}%"

    st.subheader("Two numbers every local authority should know")
    left, right = st.columns(2)
    with left:
        big, of = ("n/a", "") if math.isnan(here["dep_road"]) else in_ten(here["dep_road"])
        hook_card(big, f"{of}road deaths happen on departmental roads",
                  note("dep_road", here["n_killed"], "people killed"))
    with right:
        big, verb = ("n/a", "are") if math.isnan(here["ped_65"]) else one_in(here["ped_65"])
        hook_card(big, f"pedestrians killed {verb} aged 65 or over",
                  note("ped_65", here["n_ped"], "pedestrians killed"))


# ---------- KPI row ----------

def deltas_previous_year(people: pd.DataFrame, f: Filters) -> dict | None:
    """National mode: last selected year compared with the year before (None if that is 2019)."""
    last = f.years[1]
    if last == FIRST_YEAR:
        return None
    cur = kpis(filter_people(people, f, years=(last, last)))
    prev = kpis(filter_people(people, f, years=(last - 1, last - 1)))
    return {key: cur[key] - prev[key] for key in ["killed", "lethality", "dep_road", "aged_65"]}


def deltas_national(cur: dict, nat: dict) -> dict:
    """Département mode: gap with France (metro.) for the same years and road users.
    Deaths are compared per million inhabitants per year, since raw counts are not comparable."""
    gaps = {key: cur[key] - nat[key] for key in ["lethality", "dep_road", "aged_65"]}
    # The deaths gap is a rate too: not shown under the small-number rule (e.g. 1 death in a small département)
    per_million = cur["per_million"] - nat["per_million"] if cur["killed"] >= MIN_KILLED else math.nan
    return {"killed": per_million, **gaps}


def fmt_delta(key: str, value: float, national: bool) -> str:
    """Short delta text so that it fits in a narrow KPI card; the comparison goes in delta_description.
    A gap that rounds to zero is shown without a sign ("0.0", not "-0.0" or "+0.0")."""
    digits = 0 if key == "killed" else 1
    value = round(value, digits) + 0.0                         # "+ 0.0" turns -0.0 into 0.0
    number = f"{value:+,.{digits}f}" if value else f"{value:.{digits}f}"
    if key == "killed":
        return number if national else f"{number} per million"
    return number + (" pts" if key in ("dep_road", "aged_65") else "")


def render_kpis(data: dict, f: Filters) -> None:
    people, pop = data["people"], data["population"]
    cur = kpis(filter_people(people, f), population(pop, f))
    if f.is_national:
        nat = None
        deltas = deltas_previous_year(people, f) or {}
    else:
        nat = kpis(filter_people(people, f, national=True), population(pop, f, national=True))
        deltas = deltas_national(cur, nat)

    def help_text(key: str, definition: str, unit: str = "") -> str:
        if nat is None:
            return definition
        return f"{definition} {NATIONAL_LABEL}: {nat[key]:.1f}{unit}."

    # Labels are short to fit 4 cards in a row; the full definition is in the "?" tooltip
    metrics = [  # (key, label, formatted value, delta colour, help)
        ("killed", "People killed", fmt_int(cur["killed"]), "inverse",
         "Killed within 30 days of the accident." if nat is None else
         f"Killed within 30 days. Fewer than {MIN_KILLED} deaths: no rate per inhabitant shown."
         if cur["killed"] < MIN_KILLED else
         f"Killed within 30 days. Per million inhabitants per year: {cur['per_million']:.0f} here, "
         f"{nat['per_million']:.0f} in {NATIONAL_LABEL} (INSEE population estimates)."),
        ("lethality", "Killed per 100", f"{cur['lethality']:.1f}", "inverse",
         help_text("lethality", "People killed per 100 people involved in an injury accident.")),
        ("dep_road", "Dept. roads", f"{cur['dep_road']:.0f}%", "off",
         help_text("dep_road", "Share of people killed who died on departmental roads.", "%")),
        ("aged_65", "Aged 65+", f"{cur['aged_65']:.0f}%", "off",
         help_text("aged_65", "Share of people killed aged 65 or over (known ages only).", "%")),
    ]
    vs = f"vs {f.years[1] - 1}" if f.is_national else "vs France"
    for col, (key, label, value, color, help_) in zip(st.columns(4), metrics):
        if key != "killed" and math.isnan(cur[key]):          # small-number rule
            col.metric(label, "n/a", help="Not enough data (fewer than 10 deaths or 30 people involved).",
                       border=True)
            continue
        delta = deltas.get(key)
        if delta is None or math.isnan(delta):
            col.metric(label, value, delta_color=color, help=help_, border=True)
            continue
        rounds_to_zero = round(delta, 0 if key == "killed" else 1) == 0   # e.g. "+0.0": no misleading arrow
        col.metric(label, value, delta=fmt_delta(key, delta, f.is_national),
                   delta_color="off" if rounds_to_zero else color,
                   delta_description=vs, delta_arrow="off" if rounds_to_zero else "auto",
                   help=help_, border=True)

    users = "all road users" if set(f.modes) == set(MODE_ORDER) else ", ".join(f.modes)
    if f.is_national:
        compare = f"Changes: {f.years[1]} compared with {f.years[1] - 1}." if deltas else ""
    else:
        compare = (f"Changes: gap with {NATIONAL_LABEL} for the same years and road users "
                   "(deaths per million inhabitants per year).")
    st.caption(f"{f.territory}, {f.period}, {users}. {compare} Red = more deaths or higher lethality.")


# ---------- Section ----------

def render(data: dict, f: Filters) -> None:
    st.title("Where roads kill")
    st.markdown("**A guide for local authorities** · road accidents in metropolitan France, 2019–2024")
    render_hook(data["people"], f)
    st.write("")
    render_kpis(data, f)

    render_context(data)


# ---------- Context ----------

def render_context(data: dict) -> None:
    """What the data covers: source, scope, unit, how to read lethality, main bias."""
    people = data["people"]
    n_people, n_killed = len(people), int(people["killed"].sum())
    st.header("Every injury accident, as recorded by the police")
    st.markdown(
        f"""
- **Source**: the national road accident files (BAAC) of the French road safety observatory (ONISR),
  published on data.gouv.fr. Every road accident in which at least one person was injured is recorded
  by the police or gendarmerie.
- **Scope**: metropolitan France (96 départements), 2019–2024. **One row = one person involved**
  (driver, passenger or pedestrian): {fmt_int(n_people)} people, of whom {fmt_int(n_killed)} were killed.
- **Killed** means died within 30 days of the accident.
- **Lethality = people killed per 100 people involved.** It measures how serious accidents are, not how
  frequent they are. For example, 4.3 on departmental roads (France, 2019–2024) means about 4 deaths for
  every 100 people involved in an injury accident there.
- **Main bias**: the police are not always called to non-fatal accidents, so injuries are under-reported,
  while deaths are recorded completely. Deaths are therefore the most reliable indicator; lethality is
  probably somewhat overstated, as its denominator misses part of the injured.
"""
    )
    st.caption("Deaths in these files match the official ONISR figures exactly for every year: "
               "see Data quality & methodology at the end of the page.")
