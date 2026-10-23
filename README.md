# Where roads kill — a guide for local authorities

A Streamlit data story on French road accidents, 2019–2024, built for **local authorities and decision-makers**
(départements, communes, régions). It answers one question:

> *In my territory, where, when and for whom are roads most dangerous, and where should we act first?*

Choose a département in the sidebar and the whole story updates, with the national value as a grey reference.

**Live app:** _URL to add after deployment on Streamlit Community Cloud_ ·
**Author:** Noam Slézack, EFREI Paris, Data & AI major — #EFREIDataStories2026

---

## Key findings (metropolitan France, 2019–2024)

- **6 deaths in 10 happen on departmental roads**, which carry only 38% of the people involved in injury accidents:
  an injury accident there is more often fatal (4.3 killed per 100 people involved, against 1.6 on all other roads).
- **Rural départements are the deadliest per inhabitant** (up to 97 killed per million inhabitants per year,
  against 14 in the inner Paris suburbs; rank correlation with population density −0.87).
- **Vulnerable users and seniors pay the highest price**: pedestrians, cyclists and powered two-wheeler riders are
  over-represented among deaths; about **1 pedestrian killed in 2 is aged 65+**, and at 75+ an injury accident is
  3.2× as likely to be fatal as on average.
- **No real improvement since 2019**: 3,244 deaths in 2019, 3,193 in 2024; the share of people aged 65+ among
  deaths rose from 26.5% to 28.7%.

All figures are correlations, not causes (see *Limitations*).

## Data sources

| Source | Content | Licence |
|---|---|---|
| [ONISR / Ministère de l'Intérieur — BAAC](https://www.data.gouv.fr/fr/datasets/53698f4ca3a729239d2036df/) (data.gouv.fr) | Every injury road accident recorded by the police: 4 tables per year (`caract`, `lieux`, `vehicules`, `usagers`), 2019–2024 | Licence Ouverte 2.0 |
| [INSEE — population estimates by département](https://www.insee.fr/fr/statistiques/8721456) (January 2026 edition) | Population on 1 January per département and year, used for "killed per million inhabitants" (2024 is provisional) | Licence Ouverte |
| [france-geojson](https://github.com/gregoiredavid/france-geojson) (IGN Admin Express, INSEE codes, simplified) | Outlines of the 96 metropolitan départements for the map | Licence Ouverte |

2019 is the first year of the current BAAC format; 2025 is not published yet.
**Validation:** the number of people killed in metropolitan France matches the official ONISR figures exactly
for every year (3,244 / 2,541 / 2,944 / 3,267 / 3,167 / 3,193); `scripts/build_data.py` stops if it does not.

## Run it locally

Requires Python 3.13 (other recent versions should work). From the project folder:

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The processed data (`data/processed/`, ~4.5 MB) is in the repository, so the app runs straight from a clean
checkout. To rebuild it from the raw sources:

```bash
python scripts/download_data.py   # BAAC CSVs, INSEE population, GeoJSON -> data/raw/ (cached, skipped if present)
python scripts/build_data.py      # cleaning, joins, features, quality report -> data/processed/
```

`download_data.py` finds the files through the data.gouv.fr API and never downloads a file twice.
Raw files (~180 MB) are not committed (`data/raw/` is git-ignored).

Smoke test (runs the whole page headless for 11 filter combinations, exit code 1 on failure):

```bash
python tests/smoke_test.py
```

## Project structure

```
app.py                  entry point: cached data loading, sidebar filters, sections in story order
sections/               one file per part of the story, each with render(data, filters)
  intro.py              hook (two key numbers), KPI row, what the data covers
  where.py              map of killed per million inhabitants, map of fatal accidents, road types
  who.py                road users (share involved vs share of deaths), age group × road user lethality
  when.py               hour × day of week heatmap, night vs day lethality
  trend.py              2019–2024 trend, share of seniors and cyclists among deaths
  implications.py       where the territory stands out, priorities for départements and communes, limits
  quality.py            sources, ONISR validation, cleaning decisions, missing values
utils/
  io.py                 raw loading of the BAAC CSVs (whitespace, missing markers, IDs, coordinates)
  prep.py               cleaning rules and features, validated in the notebooks
  filters.py            sidebar filters and the cached aggregation shared by the sections
  viz.py                colours, Plotly template "roadsafety", chart helpers
scripts/
  download_data.py      downloads and caches all raw sources
  build_data.py         builds data/processed/ and checks deaths against ONISR
data/processed/         people.parquet (1 row = 1 person involved), fatal_accidents.parquet,
                        population.parquet, departements.geojson, quality.json
notebooks/              01_exploration (data audit), 02_insight_scan (choice of angles, multi-year check)
docs/storyboard.md      audience, questions, narrative and visual plan
tests/smoke_test.py     headless AppTest of the app
.streamlit/config.toml  dark theme
```

## Main data decisions

- **One row = one person involved** (driver, passenger or pedestrian), joined with the accident, road and vehicle.
  The join is checked to create no duplicate.
- **One road per accident**: at junctions the `lieux` table has one row per road; the main road (lowest road
  category) is kept. These multi-road rows only exist from 2023.
- **Metropolitan France only** (96 départements); département codes padded to 2 characters (`1` → `01` in 2019).
- **No imputation**: missing values (`-1`, `N/A`, empty) stay in an *Unknown* category; implausible birth years
  (1900–1901 placeholders) become unknown ages.
- **Small-number rule**: no rate is shown below 30 people involved or 10 deaths.
- **Deaths are the key indicator**: injuries are under-reported (police not always called), deaths are complete.

Every decision is documented in the notebooks and in the app's *Data quality & methodology* section.

## How the app meets the brief

| Requirement | Where |
|---|---|
| Narrative for a defined audience, central question, insights → implications | `docs/storyboard.md`; one scrolling page: hook → where → who → when → trend → what to do → data quality; each headline is the insight, computed for the selected territory |
| Streamlit ≥ 1.33, sidebar filters (date range, region, variable selection) | Streamlit 1.66; sidebar: territory (France or one département), year range, road users |
| ≥ 3 interactive Plotly visuals with tooltips, at least one map | 2 maps (choropleth, fatal accidents), paired bars ×2, heatmaps ×2, line charts ×2, all with tooltips |
| KPI header reacting to filters | 4 `st.metric` cards (killed, lethality, departmental roads, aged 65+) with change vs previous year or gap vs France |
| Data quality section | Missing values chart, duplicates and orphans per table and year, ONISR validation, cleaning decisions |
| Caching, pre-aggregation, efficient merges | `st.cache_data` on loading and on every aggregation; small pre-built Parquet files; joins asserted 1:1 |
| Accessibility | Axis titles with units, values written in heatmap cells, alt text under every chart, contrast-checked dark palette, "See the data" tables |
| Reproducibility | Pinned `requirements.txt`, download script with caching, build script with assertions, no raw data in the repo, smoke test |

## Limitations

- **Correlations, not causes**: the data show where and for whom deaths happen, not why.
- **No exposure data**: traffic volumes are not available, so a group with many deaths may simply travel more.
- **Injuries are under-reported**, so lethality is probably somewhat overstated; deaths are complete.
- **Rates per inhabitant** relate deaths to residents, but victims are not always residents (transit, tourism);
  INSEE population for 2024 is provisional.
