"""Raw loading of BAAC files: read and clean the text, no business rules (those are in prep.py)."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
TABLES = ["caract", "lieux", "usagers", "vehicules"]

# Non-breaking and narrow non-breaking spaces found in the files. Written with chr() so they stay

# engine treats \s as ASCII whitespace only.
NBSP, NNBSP = chr(0x00A0), chr(0x202F)


def read_table(path: Path) -> pd.DataFrame:
    """Read one BAAC CSV as text, strip spaces in every cell and turn empty / "N/A" into NaN."""
    df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig")  # utf-8-sig drops a possible BOM
    df.columns = df.columns.str.strip()
    df = df.apply(lambda s: s.str.strip().str.strip(NBSP + NNBSP))
    return df.replace({"": np.nan, "N/A": np.nan})


def clean_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Harmonise the accident key name and remove inner spaces from the person/vehicle IDs."""
    df = df.rename(columns={"Accident_Id": "Num_Acc"})          # name used in the 2022 caract file
    for col in ["id_usager", "id_vehicule"]:
        if col in df.columns:                                   # id_usager does not exist in 2019-2020
            df[col] = df[col].str.replace(f"[\\s{NBSP}{NNBSP}]", "", regex=True)
    return df


def parse_coordinates(caract: pd.DataFrame) -> pd.DataFrame:
    """Convert lat/long from comma-decimal text to float."""
    for col in ["lat", "long"]:
        caract[col] = pd.to_numeric(caract[col].str.replace(",", ".", regex=False), errors="coerce")
    return caract


def load_year(year: int) -> dict[str, pd.DataFrame]:
    """Load the 4 BAAC tables of one year, cleaned but not filtered or joined."""
    tables = {t: clean_ids(read_table(RAW_DIR / f"{t}-{year}.csv")) for t in TABLES}
    tables["caract"] = parse_coordinates(tables["caract"])
    return tables
