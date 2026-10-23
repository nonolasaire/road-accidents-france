# Storyboard — "Where roads kill: a guide for local authorities"

*Draft v1 — French road accidents 2019–2024 (ONISR / BAAC, data.gouv.fr)*

## 1. Framing

| | |
|---|---|
| **Audience** | Local authorities and decision-makers: départements (manage departmental roads), communes (municipal roads, urban streets), régions. |
| **Central question** | *In my territory, where, when and for whom are roads most dangerous, and where should we act first?* |
| **Key indicators** | **People killed** (complete, matches official ONISR figures) and **lethality** = killed per 100 people involved. |
| **Main takeaways** | (1) 6 deaths out of 10 happen on departmental roads. (2) About 1 pedestrian killed out of 2 is aged 65+, and the share of seniors among deaths keeps rising. (3) Priorities differ by authority: départements → rural roads, powered two-wheelers, cyclists; communes → pedestrians, especially seniors. |
| **Format** | One scrolling page read top to bottom like an article. A **"My department"** selector updates the whole story and compares it with the national figures. |

## 2. Global controls (sidebar)

| Control | Default | Effect |
|---|---|---|
| **Territory**: "Metropolitan France" or one département | Metropolitan France | All KPIs, charts and text update; when a département is selected, each chart shows the national value as a reference |
| **Years** (range slider) | 2019–2024 | Filters every section except the trend section, which always shows the full period |
| **Road user** (multiselect) | All | Pedestrian, bicycle, e-scooter, powered two-wheeler, car/van, heavy vehicle |
| **Light conditions / weekend** (optional toggles) | All | Secondary filters (moderate effects, ×1.2) |

## 3. Narrative, section by section

### 0. Hook — "Two numbers every local authority should know"
- **Headline duo**: *"6 in 10 road deaths happen on departmental roads"* · *"1 pedestrian killed in 2 is aged 65 or over"*
- **KPI row** (`st.metric`, reacts to filters): people killed · lethality (per 100 involved) · share on departmental roads · share aged 65+. Each with the change vs. the previous year, or vs. the national value when a département is selected.

### 1. Context — "What the data covers"
- Short text: source (ONISR, every injury accident recorded by police), 2019–2024, metropolitan France, 1 row = 1 person involved.
- How to read lethality, and the known bias (non-fatal accidents are under-reported → deaths are the most reliable indicator).

### 2. Where? — "Departmental roads concentrate the deaths"
| Visual | Message | Interaction |
|---|---|---|
| **Choropleth of départements**: killed per million inhabitants | Rural départements are the most dangerous per inhabitant, not the densest ones | Hover: deaths, rate, rank. Clicking/selecting a département = same as the sidebar selector |
| **Point map of fatal accidents** (shown when a département is selected) | Where exactly people die in my territory | Hover: date, road, mode, age group |
| **Bar chart by road type**: share of people involved vs. share of deaths | Departmental roads: ~38% of people involved but ~61% of deaths | Hover: counts and lethality |

### 3. Who? — "Vulnerable users and seniors pay the highest price"
| Visual | Message | Interaction |
|---|---|---|
| **Bar chart by road user**: share of people involved vs. share of deaths | Pedestrians, cyclists and powered two-wheelers are over-represented among deaths | Hover: counts, lethality |
| **Heatmap age group × road user** (lethality, with counts) | Senior pedestrians and cyclists: lethality up to ×4.5 the average | Hover: deaths and people involved; cells with too few cases are greyed out |
| **Annotation** | Frailty explains part of the senior effect: same accident, higher risk of dying | — |

### 4. When? — "Risk is spread over the week, with deadlier nights"
| Visual | Message | Interaction |
|---|---|---|
| **Heatmap hour × day of week** (deaths) | Peaks at commuting hours and weekend nights; night accidents are more lethal | Hover: deaths and lethality |

### 5. Trend — "No real improvement since 2019, and an ageing toll"
| Visual | Message | Interaction |
|---|---|---|
| **Line chart 2019–2024**: people killed | Back to the pre-COVID level after the 2020 drop | Annotation on 2020: "COVID lockdowns" |
| **Line chart**: share of seniors (65+) and cyclists among deaths | Seniors: 26.5% → 28.7%; cyclists up after 2020 | Hover per year |

### 6. Implications — "Where to act first"
- **Départements**: departmental roads, powered two-wheelers, cyclists outside urban areas (e.g. speed management, separated cycle lanes, junction design).
- **Communes**: pedestrians in urban areas, especially seniors (crossings, lighting, 30 km/h zones).
- **Dynamic block**: when a département is selected, the 3 indicators where it is furthest above the national average.
- **Next steps / limitations**: correlations, not causes; exposure data (traffic volume) is not available; injuries under-reported.

### 7. Data quality & methodology
- Sources and licence, years covered, rows per table.
- Validation: deaths match ONISR official figures every year (table).
- Cleaning decisions: whitespace and missing markers, `lieux` intersections rule, département codes padded, dropped columns, "Unknown" categories, small-number rule.
- Missing values chart per variable.

## 4. Design principles
- Every section opens with a **one-sentence insight as the title**, then the chart, then 1–2 sentences of explanation.
- Consistent colours: one colour per road user across all charts; national reference always in grey.
- Labelled axes with units, readable contrast, alt text under each chart.
- Small-number rule: no rate shown below ~30 people involved or ~10 deaths.

## 5. Decisions
- ✅ Population data: **INSEE population estimates by département** (second source), used only to compute
  "killed per million inhabitants" for fair comparisons between territories. Justified in the README and Data quality section.
- Open: exact wording of the headlines once final numbers are computed on the selected period.
