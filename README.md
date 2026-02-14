# Mozambique Electronic Banking Dashboard

Streamlit dashboard for analyzing Banco de Moçambique electronic banking statistics with demographic context from INE Census 2017.

## What This Project Does

- Consolidates banking indicators (2020, 2021, 2022, 2024, 2025) into analysis-ready CSVs.
- Explores:
  - Accounts and cards adoption.
  - ATM/POS physical infrastructure.
  - Mobile/Internet banking usage.
  - ATM/POS/Mobile/Internet transaction volume and value.
- Adds demographic context (population, urban/rural, connectivity) for inclusion KPIs.
- Provides historical trend and forecast views.

## Data Sources

- Banco de Moçambique workbooks: `banca-electronica-YYYY.xlsx`
- INE Census 2017 provincial aggregates (maintained in ETL and exported to `census_2017_provinces.csv`)

## Architecture

```text
Raw Excel (BoM) + Census constants (INE)
  -> ETL.ipynb (main extraction from complex sheets)
  -> etl.py (repeatable post-processing + census export)
  -> CSV layer
  -> Streamlit app
```

### Refactor (this version)

`app.py` was reduced to orchestration/UI logic and helper code moved into reusable modules:

- `dashboard/translations.py`
  - Translation catalog and translation helper.
- `dashboard/data_utils.py`
  - Data loading, cleanup, normalization, snapshots, year-gap detection.
- `dashboard/forecasting.py`
  - Time-series preparation and polynomial forecasting utilities.
- `etl.py`
  - ETL maintenance tasks:
    - Export census CSV.
    - Post-process CSV outputs (drop `Unnamed:*`, district normalization, non-negative numeric clipping).

## Key Decisions

1. Stock vs Flow separation
- Stock indicators (`Accounts`, `Cards`, `ATMs`, `POS`) are interpreted with end-of-period snapshots (last month in year).
- Flow indicators (transactions) are aggregated as sums.
- This prevents overcounting stock metrics by summing 12 monthly points.

2. Geography normalization
- District names are normalized across files:
  - `Cidade de de Maputo` -> `Cidade de Maputo`
  - `Maputo` district under `Província de Maputo` -> `Cidade de Maputo`
  - `Cabo-Delgado` -> `Cabo Delgado`
- This avoids false zeros when filtering by district.

3. Census ownership in ETL
- Census export moved to ETL (`etl.py`) instead of app-side assumptions.
- Census output now has consistency guardrails (`Urban <= Total`, `Rural = Total - Urban`).

4. Time-series caveat signaling
- App now warns about missing years in the selected series (e.g., 2023 gap).

5. Maputo modeling decision (current vs future)
- `Cidade de Maputo` and `Província de Maputo` are now modeled separately in census denominators.
- This aligns demographic denominators with the banking geography used in filters and avoids artificial per-capita inflation.

6. Financial inclusion denominator policy (v1)
- Financial inclusion ratios now support denominator scenarios in the sidebar:
  - `15+` (recommended)
  - `18+`
  - `21+` (conservative)
  - `Total population (legacy)`
- Legal rationale (Mozambique banking regulation): simplified accounts can be opened by:
  - people `>=18` autonomously;
  - people `15-17` with legal representative authorization.
- Business implication: a strict adult-only denominator (`18+`) can be useful for conservative benchmarking, but `15+` is better aligned with regulated access potential.

7. Cohort extrapolation from Census 2017 to dashboard years
- The denominator for years 2020-2025 is estimated via cohort progression from Census 2017 age buckets (Table 3):
  - `Population_15plus_2017`
  - `Population_10_14_2017`
  - `Population_15_19_2017`
- Rule: for a selected year `Y` and minimum age `A`, the equivalent census threshold is `A - (Y - 2017)`.
- Example with exact dates:
  - For year 2025 and `18+`, threshold maps to age `10+` in 2017.
  - For year 2025 and `21+`, threshold maps to age `13+` in 2017.
- v1 caveat: this is a static-cohort approximation (no births, deaths, migration, or province-level reweighting).
8. Forecast model selection (v1.1)
- Forecasting no longer forces one model for all indicators.
- Candidate models are evaluated on holdout error (MAPE): `naive`, `seasonal naive (12)`, `poly1`, `poly2`.
- The app automatically selects the best-performing candidate per indicator.
- For sparse stock series (very few annual end-of-period points), the app defaults to a conservative linear trend (`poly1`).
- Forecast visuals display selected model and holdout MAPE so users can interpret confidence.

## Caveats You Should Keep in Mind

- Year coverage is non-contiguous (2023 missing in current CSVs).
- Per-capita metrics use Census 2017-based denominator scenarios with cohort progression (static approximation).
- Forecasting uses model selection across naive/seasonal/linear/quadratic candidates and remains scenario-oriented.
- Forecasts are statistical projections, not causal estimates. Missing 2023 may affect trend continuity.

## Regulatory and Statistical References

- Banco de Moçambique, Aviso n.º 10/GBM/2024 (contas simplificadas): [boletim da República PDF](https://www.bancomoc.mz/fm_pgLink.aspx?id=768)
- INE, Censo 2017, Brochura de Resultados Definitivos: local project file `Censo 2017 Brochura dos Resultados Definitivos do _260111_221900.pdf`

## Run

Install dependencies:

```bash
pip install streamlit pandas numpy plotly openpyxl
```

Optional ETL maintenance (recommended after notebook extraction):

```bash
python etl.py --all
```

Run dashboard:

```bash
streamlit run app.py
```

### Optional: Province Choropleth Map (GeoJSON)

The demographic tab auto-detects a local Mozambique ADM1 GeoJSON and switches from marker map to true province choropleth.

Supported local filenames:

- `geoBoundaries-MOZ-ADM1_simplified.geojson`
- `geoBoundaries-MOZ-ADM1.geojson`
- `mozambique_adm1.geojson`
- `moz_adm1.geojson`

If none is found, the dashboard falls back to a marker-based province map.

## Project Structure

```text
BM Project/
├── app.py
├── etl.py
├── ETL.ipynb
├── dashboard/
│   ├── __init__.py
│   ├── translations.py
│   ├── data_utils.py
│   └── forecasting.py
├── census_2017_provinces.csv
├── accounts_2020_2025.csv
├── cards_2020_2025.csv
├── ATM_Infrastructure_2020_2025.csv
├── POS_Infrastructure_2020_2025.csv
├── transactions_vol_2020_2025.csv
├── transactions_val_2020_2025.csv
├── POS_Transactions_2020_2025.csv
├── Mobile_Banking_2020_2025.csv
└── Internet_Banking_2020_2025.csv
```

## Author

Valter Cheque
