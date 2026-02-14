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
- **Current (intentional):** `Cidade de Maputo` and `Província de Maputo` are treated as one aggregate geography (`Província de Maputo`) for dashboard comparability.
- **Why now:** splitting them immediately would require a full ETL/schema redesign, historical revalidation, and chart/KPI remapping across all pages.
- **Tradeoff:** this keeps the app stable now, but province-level results for Maputo represent a combined area.
- **Planned later:** introduce a canonical geo dimension (`geo_id`, level, aliases) and rebuild ETL outputs to support separate city/province reporting where source files allow it.

## Caveats You Should Keep in Mind

- Year coverage is non-contiguous (2023 missing in current CSVs).
- Per-capita metrics combine recent banking data with Census 2017 denominators.
- Forecasting is polynomial (degree 2), useful for scenarios but not causal inference.
- Maputo is currently shown as a combined geography (city + province) to preserve consistency in the current pipeline.

## Run

Install dependencies:

```bash
pip install streamlit pandas numpy plotly scikit-learn openpyxl
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
