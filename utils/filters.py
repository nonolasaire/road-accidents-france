"""Sidebar filter values, the functions that apply them, and the cached aggregation shared by sections."""
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from utils.viz import MIN_KILLED, MIN_PEOPLE

NATIONAL = "Metropolitan France"


@dataclass(frozen=True)
class Filters:
    dep: str | None              # None = Metropolitan France
    dep_name: str | None
    years: tuple[int, int]       # inclusive range
    modes: tuple[str, ...]       # road users kept

    @property
    def is_national(self) -> bool:
        return self.dep is None

    @property
    def territory(self) -> str:
        """Label used in texts, e.g. "Ain (01)" or "Metropolitan France"."""
        return NATIONAL if self.is_national else f"{self.dep_name} ({self.dep})"

    @property
    def period(self) -> str:
        first, last = self.years
        return str(first) if first == last else f"{first}–{last}"


def filter_people(people: pd.DataFrame, f: Filters, national: bool = False,
                  years: tuple[int, int] | None = None, modes: bool = True) -> pd.DataFrame:
    """Apply the filters. national=True ignores the département (for the grey reference);
    years overrides the selected range; modes=False keeps every road user."""
    first, last = years or f.years
    mask = people["year"].between(first, last)
    if modes:
        mask &= people["mode"].isin(f.modes)
    if not (national or f.is_national):
        mask &= people["dep"] == f.dep
    return people[mask]


@st.cache_data
def group_table(_people: pd.DataFrame, f: Filters, by: str | list[str], national: bool = False,
                years: tuple[int, int] | None = None) -> pd.DataFrame:
    """People involved and killed per group, with shares and lethality (NaN under the small-number rule).
    Cached on the filters and the grouping; the leading underscore stops Streamlit hashing the big table."""
    p = filter_people(_people, f, national=national, years=years)
    t = p.groupby(by, observed=False).agg(people=("killed", "size"), killed=("killed", "sum"))
    t["involved_pct"] = t["people"] / max(t["people"].sum(), 1) * 100
    t["deaths_pct"] = t["killed"] / max(t["killed"].sum(), 1) * 100
    enough = (t["people"] >= MIN_PEOPLE) & (t["killed"] >= MIN_KILLED)
    t["lethality"] = (t["killed"] / t["people"] * 100).where(enough)
    return t


def population(pop: pd.DataFrame, f: Filters, national: bool = False) -> int:
    """Population summed over the selected years (person-years), to compute rates per inhabitant per year."""
    mask = pop["year"].between(*f.years)
    if not (national or f.is_national):
        mask &= pop["dep"] == f.dep
    return int(pop.loc[mask, "population"].sum())
