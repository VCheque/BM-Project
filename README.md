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
- Provides historical trend and flow-focused forecast views.
- Adds a decision layer with province opportunity scoring, scenario ranges, and district-vs-district comparison.
- Adds a dedicated Mobile Wallets page (`📱 Carteiras Móveis`) as an early navigation step.

## Data Sources

- Banco de Moçambique workbooks: `banca-electronica-YYYY.xlsx`
- INE Census 2017 provincial aggregates (maintained in ETL and exported to `census_2017_provinces.csv`)
- Banco de Moçambique IME workbook (district depth): `instituições-de-moeda-electrónica-2025.xlsx`
- INCM Acervo telecom benchmark (Q2 2025): total mobile subscribers by province (`https://acervo.incm.gov.mz/#/public/telecom`)

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
- `dashboard/opportunity.py`
  - Province opportunity score engine (weighted decomposition and rank rationale).
- `dashboard/scenarios.py`
  - Scenario ranges (`Conservative`, `Base`, `Accelerated`) from baseline forecast paths.
- `dashboard/audience.py`
  - Rule-based interpretation paragraph and KPI labels by audience lens.
- `etl.py`
  - ETL maintenance tasks:
    - Export census CSV.
    - Post-process CSV outputs (drop `Unnamed:*`, district normalization, non-negative numeric clipping).
    - Extract IME district datasets for 2025:
      - Subscribers by district.
      - Subscribers by district, gender, and age.
      - Agents by district.
      - Transactions by district with both `Volume` and `Value` preserved for each sheet (`Depósitos`, `Levantamentos`, `Transferências`, `Pagamentos`).
    - Export context datasets from BoM 2025 releases:
      - `Access_Points_District_2025Q3.csv`
      - `Financial_Inclusion_Indicators_2020_2025Q3.csv`
      - `Sectoral_Growth_Rates_2020_2025.csv`
      - `GDP_Expenditure_Annual_Variation_2020_2025.csv`

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
- Forecast scope is intentionally limited to **flow indicators**:
  - ATM/POS/Mobile/Internet transactions (volume and value)
  - IME transactions by type (`Depósitos`, `Levantamentos`, `Transferências`, `Pagamentos`; volume and value)
- Forecast visuals display selected model and holdout MAPE so users can interpret confidence.

9. Decision layer design
- Opportunity scoring ranks provinces using transparent weights:
  - Demand potential: `35`
  - Digital momentum: `25`
  - Monetization signal: `25`
  - Infrastructure gap: `15`
- Scenario comparison is shown as planning ranges (`Conservative`, `Base`, `Accelerated`) by scaling baseline annual growth paths.
- District comparator adds direct side-by-side analysis (default: `Cidade de Maputo` vs `Cidade da Beira`) across:
  - IME subscribers and agents
  - IME transactions by type (volume and value)
  - accounts, cards, ATM, POS
  - inclusion context (shown at province level for each district)
- A freshness panel exposes latest periods detected in core banking, IME district, access-points, and inclusion releases.

10. Presentation flow decision
- Mobile wallet analysis was moved to its own page (`📱 Carteiras Móveis`) near the start of the app.
- Rationale: IME/mobile wallet is a primary focus and should not be hidden inside expandable content.
- The former standalone heatmap page was condensed into an optional section inside `📈 Tendências Históricas` to reduce navigation and scroll overhead.
- The final page was reframed to `Insights Estratégicos / Oportunidades` as a synthesis page:
  - where opportunities are concentrated,
  - how indicators behave under scenario ranges,
  - how two districts compare directly for prioritization.

## Caveats You Should Keep in Mind

- Year coverage is non-contiguous (2023 missing in current CSVs).
- Per-capita metrics use Census 2017-based denominator scenarios with cohort progression (static approximation).
- The financial-inclusion denominator selector is global (sidebar) and applies across pages.
- Forecasting uses model selection across naive/seasonal/linear/quadratic candidates and remains scenario-oriented.
- Forecasts are statistical projections, not causal estimates. Missing 2023 may affect trend continuity.
- Mobile Wallet forecasts currently rely on 12 monthly observations (2025); interpretation is short-term oriented. Default IME forecast horizon is 3 months.
- INCM subscriber totals are used as market baseline context (penetration/capacity/usage intensity), and represent service subscriptions rather than unique individuals.
- District-level inclusion is not directly observed; in district comparator, inclusion is displayed as province-level context.
- IME district-level detail is currently available from the official 2025 workbook; 2020-2025 continuity remains national/provincial in base BoM electronic-banking series.
- Opportunity score is a prioritization heuristic, not a causal impact model.
- Scenario ranges are sensitivity views around baseline trend, not policy targets.

## Regulatory and Statistical References

- Banco de Moçambique, Aviso n.º 10/GBM/2024 (contas simplificadas): [boletim da República PDF](https://www.bancomoc.mz/fm_pgLink.aspx?id=768)
- INE, Censo 2017, Brochura de Resultados Definitivos: local project file `Censo 2017 Brochura dos Resultados Definitivos do _260111_221900.pdf`

## Run

Install dependencies:

```bash
pip install streamlit pandas numpy plotly openpyxl xlrd
```

Optional ETL maintenance (recommended after notebook extraction):

```bash
python etl.py --all
```

IME-only extraction:

```bash
python etl.py --export-ime
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
│   ├── forecasting.py
│   ├── opportunity.py
│   ├── scenarios.py
│   └── audience.py
├── census_2017_provinces.csv
├── accounts_2020_2025.csv
├── cards_2020_2025.csv
├── ATM_Infrastructure_2020_2025.csv
├── POS_Infrastructure_2020_2025.csv
├── transactions_vol_2020_2025.csv
├── transactions_val_2020_2025.csv
├── POS_Transactions_2020_2025.csv
├── Mobile_Banking_2020_2025.csv
├── Internet_Banking_2020_2025.csv
├── IME_Subscribers_District_2025.csv
├── IME_Subscribers_District_Demographics_2025.csv
├── IME_Agents_District_2025.csv
├── IME_Transactions_District_2025.csv
├── Access_Points_District_2025Q3.csv
├── Financial_Inclusion_Indicators_2020_2025Q3.csv
├── Sectoral_Growth_Rates_2020_2025.csv
└── GDP_Expenditure_Annual_Variation_2020_2025.csv
```

## Author

Valter Cheque
