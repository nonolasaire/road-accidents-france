"""Download BAAC road accident files (ONISR, data.gouv.fr) with local caching."""
import re
from pathlib import Path
import requests

DATASET_ID = "53698f4ca3a729239d2036df"   # "Bases de données annuelles des accidents corporels..."
API_URL = f"https://www.data.gouv.fr/api/1/datasets/{DATASET_ID}/"
YEARS = range(2019, 2026)
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# File titles vary between years (e.g. "caract-2023", "caracteristiques-2019"), so match by keyword
TABLES = {
    "caract": r"^(caract|carct)",      # 2021-2022 titles are misspelled "carcteristiques"
    "lieux": r"lieux",
    "vehicules": r"^vehicules",        # excludes "vehicules-immatricules-baac"
    "usagers": r"usagers",
}

# Second source: INSEE population estimates on 1 January, by département, sex and broad age group,
# one sheet per year 1975-2026 (January 2026 edition, the most revised figures for 2019-2024).
# Page: https://www.insee.fr/fr/statistiques/8721456 . The same file also gives the département names.
INSEE_POP_URL = "https://www.insee.fr/fr/statistiques/fichier/8721456/estim-pop-dep-sexe-gca-1975-2026.xlsx"
INSEE_POP_FILE = RAW_DIR / "insee-population-dep.xlsx"

# Third source: outlines of the 96 metropolitan départements (properties: code, nom) for the choropleth.
# github.com/gregoiredavid/france-geojson: IGN Admin Express boundaries + INSEE codes, simplified,
# Licence Ouverte. URL pinned to a commit so the file cannot change under us.
GEOJSON_URL = ("https://raw.githubusercontent.com/gregoiredavid/france-geojson/"
               "45daa2d069a8da3ec4efb6672388fc3dc02e36e2/departements-version-simplifiee.geojson")
GEOJSON_FILE = RAW_DIR / "departements.geojson"

def download_file(url, target):
    """Download one file unless it is already cached."""
    if target.exists():
        print(f"[cache] {target.name}")
        return
    print(f"[download] {url.rsplit('/', 1)[-1]} -> {target.name}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    target.write_bytes(resp.content)

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    download_file(INSEE_POP_URL, INSEE_POP_FILE)
    download_file(GEOJSON_URL, GEOJSON_FILE)
    resources = requests.get(API_URL, timeout=30).json()["resources"]

    for year in YEARS:
        for table, pattern in TABLES.items():
            target = RAW_DIR / f"{table}-{year}.csv"
            if target.exists():
                print(f"[cache] {target.name}")
                continue
            match = [r for r in resources
                     if str(year) in r["title"] and re.search(pattern, r["title"].lower())
                     and "immatricul" not in r["title"].lower()]
            if not match:
                print(f"[missing] no resource found for {table} {year}")
                continue
            print(f"[download] {match[0]['title']} -> {target.name}")
            resp = requests.get(match[0]["url"], timeout=120)
            resp.raise_for_status()
            target.write_bytes(resp.content)

if __name__ == "__main__":
    main()