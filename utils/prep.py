"""Data preparation: the rules validated in notebooks 01-02, applied to each year 2019-2024."""
from pathlib import Path

import numpy as np
import pandas as pd

from utils.io import load_year

YEARS = range(2019, 2025)

# People killed (within 30 days) in metropolitan France, final ONISR figures
# (ONISR annual road safety reports, "Bilan de l'accidentalité routière"). Used as an external check.
ONISR_KILLED_METRO = {2019: 3244, 2020: 2541, 2021: 2944, 2022: 3267, 2023: 3167, 2024: 3193}

# BAAC code columns used below: "-1" means "not specified" in every year where it appears
CODE_COLS = ["lum", "agg", "catr", "catu", "grav", "catv", "an_nais"]

# English labels. Category lists are fixed so that every year has the same categories, in a meaningful order.
ROAD_LABELS = {"1": "Motorway", "2": "National road", "3": "Departmental road", "4": "Municipal road",
               "7": "Metropolitan road", "5": "Other", "6": "Other", "9": "Other"}  # 5 off-network, 6 car park
ROADS = ["Motorway", "National road", "Departmental road", "Municipal road", "Metropolitan road", "Other", "Unknown"]
AREA_LABELS = {"1": "Outside urban area", "2": "Urban area"}
AREAS = ["Outside urban area", "Urban area", "Unknown"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
AGE_BINS = [-1, 17, 24, 34, 44, 54, 64, 74, 120]
AGE_GROUPS = ["0-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
MODE_CATV = {  # vehicle category codes (catv) for each road user type; pedestrians come from catu
    "Bicycle": [1, 80],
    "E-scooter / PMD": [50, 60],
    "Powered two-wheeler": [2, 30, 31, 32, 33, 34, 41, 42, 43],
    "Car / van": [7, 10],
    "Heavy vehicle / bus": [13, 14, 15, 16, 17, 37, 38],
}
MODES = ["Pedestrian", *MODE_CATV, "Other", "Unknown"]

# Bounding box of metropolitan France incl. Corsica, to drop wrong coordinates from the point map
LAT_RANGE, LONG_RANGE = (41.3, 51.1), (-5.2, 9.6)

PEOPLE_COLS = ["Num_Acc", "year", "month", "dep", "killed", "hour", "night", "weekend", "day_of_week",
               "age", "age_group", "area", "road", "mode"]


# ---------- Joins ----------

def main_road(lieux: pd.DataFrame) -> pd.DataFrame:
    """Keep one road per accident: at intersections, the main road = lowest numeric catr (1 = motorway)."""
    return (lieux.assign(catr_num=pd.to_numeric(lieux["catr"], errors="coerce"))
            .sort_values(["Num_Acc", "catr_num"])
            .drop_duplicates(subset="Num_Acc")
            .drop(columns="catr_num"))


def join_people(t: dict[str, pd.DataFrame], lieux: pd.DataFrame) -> pd.DataFrame:
    """1 row = 1 person involved, with accident, road and vehicle attributes."""
    people = (t["usagers"][["Num_Acc", "id_vehicule", "catu", "grav", "an_nais"]]
              .merge(t["caract"], on="Num_Acc", how="left")
              .merge(lieux[["Num_Acc", "catr"]], on="Num_Acc", how="left")
              .merge(t["vehicules"][["Num_Acc", "id_vehicule", "catv"]], on=["Num_Acc", "id_vehicule"], how="left"))
    assert len(people) == len(t["usagers"]), "Join created duplicates!"
    return people


def integrity_checks(t: dict[str, pd.DataFrame]) -> dict:
    """Duplicates and orphans in the raw tables (all expected to be 0)."""
    acc = set(t["caract"]["Num_Acc"])
    checks = {f"identical_rows_{name}": int(df.duplicated().sum()) for name, df in t.items()}
    checks["duplicate_accidents_caract"] = int(t["caract"]["Num_Acc"].duplicated().sum())
    checks["duplicate_vehicles"] = int(t["vehicules"].duplicated(["Num_Acc", "id_vehicule"]).sum())
    if "id_usager" in t["usagers"].columns:                    # column absent in 2019-2020
        checks["duplicate_people"] = int(t["usagers"].duplicated(["Num_Acc", "id_usager"]).sum())
    for name in ["lieux", "vehicules", "usagers"]:
        checks[f"orphans_{name}"] = int((~t[name]["Num_Acc"].isin(acc)).sum())
    return checks


# ---------- Features ----------

def normalise_dep(dep: pd.Series) -> pd.Series:
    """Pad département codes to 2 characters ("1" -> "01" in 2019); "2A"/"2B" and overseas "971" unchanged."""
    return dep.str.zfill(2)


def road_user(people: pd.DataFrame) -> np.ndarray:
    """Road user type from catu (pedestrian) and catv (vehicle category)."""
    catv = pd.to_numeric(people["catv"], errors="coerce")
    conditions = [people["catu"] == "3"] + [catv.isin(codes) for codes in MODE_CATV.values()]
    conditions.append(catv.isna() | (catv == 0))               # 0 = vehicle type undetermined
    return np.select(conditions, ["Pedestrian", *MODE_CATV, "Unknown"], default="Other")


def add_features(p: pd.DataFrame) -> pd.DataFrame:
    """Analysis variables with English labels; missing values become "Unknown" / NA, never imputed."""
    date = pd.to_datetime(dict(year=p["an"].astype(int), month=p["mois"].astype(int), day=p["jour"].astype(int)))
    age = p["an"].astype(int) - pd.to_numeric(p["an_nais"], errors="coerce")
    age = age.where(age.between(0, 110))                       # implausible birth years -> unknown

    night = p["lum"].isin(["3", "4", "5"]).astype("boolean")   # nullable boolean: NA when light is unknown
    night[p["lum"].isna()] = pd.NA

    return pd.DataFrame({
        "Num_Acc": p["Num_Acc"].astype("int64"),               # 12-digit number: int is much lighter than text
        "year": date.dt.year.astype("int16"),
        "month": date.dt.month.astype("int8"),
        "date": date,
        "dep": p["dep"],
        "lat": p["lat"],
        "long": p["long"],
        "killed": p["grav"] == "2",
        "hour": p["hrmn"].str[:2].astype("int8"),              # hrmn is "HH:MM" in every year
        "night": night,
        "weekend": date.dt.dayofweek >= 5,
        "day_of_week": pd.Categorical(date.dt.day_name(), categories=DAYS, ordered=True),
        "age": age.astype("Int16"),
        "age_group": pd.cut(age, AGE_BINS, labels=AGE_GROUPS).cat.add_categories("Unknown").fillna("Unknown"),
        "area": pd.Categorical(p["agg"].map(AREA_LABELS).fillna("Unknown"), categories=AREAS),
        "road": pd.Categorical(p["catr"].map(ROAD_LABELS).fillna("Unknown"), categories=ROADS),
        "mode": pd.Categorical(road_user(p), categories=MODES),
    })


def fatal_accidents(f: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """1 row = 1 fatal accident with valid coordinates, for the point map (hover: date, road, victims).
    Also returns the number of fatal accidents dropped because of wrong coordinates."""
    killed = f[f["killed"]].assign(victim=lambda d: d["mode"].astype(str) + " (" + d["age_group"].astype(str) + ")")
    acc = killed.groupby("Num_Acc").agg(
        date=("date", "first"), year=("year", "first"), hour=("hour", "first"), dep=("dep", "first"),
        lat=("lat", "first"), long=("long", "first"), road=("road", "first"), area=("area", "first"),
        killed=("killed", "size"), victims=("victim", ", ".join),
    ).reset_index()
    valid = acc["lat"].between(*LAT_RANGE) & acc["long"].between(*LONG_RANGE)
    return acc[valid], int((~valid).sum())


# ---------- One year ----------

def prepare_year(year: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (people, fatal accidents, quality stats) for one year, metropolitan France only."""
    t = load_year(year)
    stats = {"rows_raw": {name: len(df) for name, df in t.items()}, "integrity": integrity_checks(t)}

    lieux = main_road(t["lieux"])
    p = join_people(t, lieux)
    p[CODE_COLS] = p[CODE_COLS].replace("-1", np.nan)
    p["dep"] = normalise_dep(p["dep"])

    metro = p["dep"].str.len() == 2                            # overseas codes have 3 characters
    known = p["grav"].notna()
    stats["rows_removed"] = {
        "lieux_extra_roads_at_intersections": len(t["lieux"]) - len(lieux),
        "people_overseas": int((~metro).sum()),
        "people_unknown_severity": int((metro & ~known).sum()),
    }
    p = p[metro & known]
    stats["missing"] = p[CODE_COLS + ["lat", "long"]].isna().sum().astype(int).to_dict()

    f = add_features(p)
    stats["implausible_age_set_unknown"] = int((f["age"].isna() & p["an_nais"].notna()).sum())
    fatal, bad_coords = fatal_accidents(f)
    stats["rows_removed"]["fatal_accidents_invalid_coords"] = bad_coords
    return f[PEOPLE_COLS].reset_index(drop=True), fatal, stats


# ---------- Population (INSEE) ----------

def load_population(path: Path, years=YEARS) -> pd.DataFrame:
    """INSEE population on 1 January by metropolitan département (one sheet per year in the xlsx)."""
    frames = []
    for year in years:
        sheet = pd.read_excel(path, sheet_name=str(year), header=None, usecols=[0, 1, 7],
                              names=["dep", "dep_name", "population"], dtype={0: str})
        sheet = sheet[sheet["dep"].str.fullmatch(r"\d{2}|2A|2B", na=False)]  # drops headers, totals, overseas
        frames.append(sheet.assign(year=year))
    pop = pd.concat(frames, ignore_index=True)
    assert (pop.groupby("year").size() == 96).all(), "Expected 96 metropolitan départements per year"
    return pop.astype({"population": "int64", "year": "int16"})[["dep", "dep_name", "year", "population"]]
