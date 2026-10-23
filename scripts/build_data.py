"""Build the small files used by the app (data/processed/) from data/raw/.

Run scripts/download_data.py first. Usage: python scripts/build_data.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make utils/ importable when run as a script
from utils.io import PROCESSED_DIR, RAW_DIR
from utils.prep import ONISR_KILLED_METRO, YEARS, load_population, prepare_year

POP_FILE = RAW_DIR / "insee-population-dep.xlsx"   # written by scripts/download_data.py
GEOJSON_FILE = RAW_DIR / "departements.geojson"     # idem


def build_geojson(population: pd.DataFrame) -> dict:
    """Département outlines for the app (data/raw/ is not in the repo, so the app needs its own copy).
    Checks that the codes are exactly the 96 metropolitan codes used everywhere else."""
    geo = json.loads(GEOJSON_FILE.read_text(encoding="utf-8"))
    codes = {f["properties"]["code"] for f in geo["features"]}
    assert codes == set(population["dep"]), "GeoJSON and INSEE département codes differ"
    return geo


def build_tables():
    """Prepare every year and stack the results; quality stats are kept per year."""
    people, fatal, stats = [], [], {}
    for year in YEARS:
        p, f, s = prepare_year(year)
        people.append(p)
        fatal.append(f)
        stats[str(year)] = s                                     # JSON keys must be strings
        print(f"{year}: {len(p):,} people, {int(p['killed'].sum()):,} killed, {len(f):,} fatal accidents")
    people = pd.concat(people, ignore_index=True)
    fatal = pd.concat(fatal, ignore_index=True)
    # dep as category after stacking (same codes every year): much lighter than text
    people["dep"] = people["dep"].astype("category")
    fatal["dep"] = fatal["dep"].astype("category")
    return people, fatal, stats


def quality_report(people: pd.DataFrame, fatal: pd.DataFrame, stats: dict) -> dict:
    """Everything the Data quality section needs, in one JSON-serialisable dict."""
    killed = people.groupby("year")["killed"].sum()
    n = len(people)
    missing = pd.DataFrame([s["missing"] for s in stats.values()]).sum()
    return {
        "years": list(YEARS),
        "per_year": stats,                                       # raw rows, integrity checks, rows removed, missing
        "missing_total": {col: {"count": int(v), "share_pct": round(v / n * 100, 2)} for col, v in missing.items()},
        "unknown_categories_pct": {col: round((people[col] == "Unknown").mean() * 100, 2)
                                   for col in ["age_group", "area", "road", "mode"]},
        "night_unknown_pct": round(people["night"].isna().mean() * 100, 2),
        "killed_vs_onisr": {str(y): {"data": int(killed[y]), "onisr": ONISR_KILLED_METRO[y],
                                     "match": int(killed[y]) == ONISR_KILLED_METRO[y]} for y in YEARS},
        "final_rows": {"people": n, "fatal_accidents": len(fatal)},
    }


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    people, fatal, stats = build_tables()
    population = load_population(POP_FILE)
    quality = quality_report(people, fatal, stats)

    # zstd compression: smaller files than the default (snappy), still fast to read
    people.to_parquet(PROCESSED_DIR / "people.parquet", index=False, compression="zstd")
    fatal.to_parquet(PROCESSED_DIR / "fatal_accidents.parquet", index=False, compression="zstd")
    population.to_parquet(PROCESSED_DIR / "population.parquet", index=False, compression="zstd")
    (PROCESSED_DIR / "quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    (PROCESSED_DIR / "departements.geojson").write_text(json.dumps(build_geojson(population)), encoding="utf-8")

    print("\nKilled in metropolitan France vs ONISR:")
    for year, row in quality["killed_vs_onisr"].items():
        print(f"  {year}: {row['data']:,} vs {row['onisr']:,}  {'OK' if row['match'] else 'MISMATCH'}")
    assert all(row["match"] for row in quality["killed_vs_onisr"].values()), "Killed differ from ONISR figures!"

    print("\nFiles written:")
    for path in sorted(PROCESSED_DIR.iterdir()):
        print(f"  {path.name:<25} {path.stat().st_size / 1024:>8,.0f} KB")


if __name__ == "__main__":
    main()
