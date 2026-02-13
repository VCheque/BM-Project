# Mozambique Electronic Banking Dashboard

Interactive dashboard built with **Streamlit** and **Plotly** for analysing electronic banking data from the **Banco de Moçambique** (Central Bank of Mozambique).

## Data Source

All data files are publicly available from the Banco de Moçambique's statistics portal:

> **[Banco de Moçambique - Electronic Banking Statistics](https://www.bancomoc.mz/pt/areas-de-actuacao/estatisticas/dominios-e-indicadores-estatisticos/)**

The raw data is distributed as multi-sheet Excel workbooks (`banca-electronica-YYYY.xlsx`) covering **2020 to 2025**, with each sheet representing a month and containing 4-level merged-cell headers (Month / Currency or Card Type / Gender / Age Group).

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA SOURCE                             │
│  Banco de Moçambique (.xlsx files, 2020-2025)               │
│  Multi-sheet Excel: 12 months × 4-level merged headers      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     ETL PIPELINE                            │
│  ETL.ipynb (Jupyter Notebook)                               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Read Excel sheets (openpyxl engine)              │    │
│  │ 2. Parse merged headers with positional assignment  │    │
│  │    (fixes December NaN bug in currency/card_type)   │    │
│  │ 3. Normalise metric names across years              │    │
│  │ 4. Output 9 clean CSV files                         │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     CSV DATA LAYER                          │
│                                                             │
│  accounts_2020_2024.csv        ~145K rows                   │
│  cards_2020_2024.csv           ~218K rows                   │
│  ATM_Infrastructure_2020_2024.csv                           │
│  POS_Infrastructure_2020_2024.csv                           │
│  transactions_vol_2020_2024.csv                             │
│  transactions_val_2020_2024.csv                             │
│  Mobile_Banking_2020_2024.csv                               │
│  Internet_Banking_2020_2024.csv                             │
│  POS_Transactions_2020_2024.csv                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  STREAMLIT DASHBOARD                        │
│  app.py (~1200 lines)                                       │
│                                                             │
│  ┌───────────────────┐  ┌─────────────────────────────┐     │
│  │  Sidebar Filters  │  │  9 Interactive Tabs          │    │
│  │  • Year           │  │                              │    │
│  │  • Zone           │  │  1. Overview (KPIs + deltas) │    │
│  │  • Province       │  │  2. Accounts (monthly, age)  │    │
│  │  • District       │  │  3. Cards (type, age)        │    │
│  │                   │  │  4. Infrastructure (ATM/POS) │    │
│  │  ℹ️ Info tooltips  │  │  5. Digital Channels         │    │
│  │  on every filter  │  │  6. Transactions (unified)   │    │
│  │  and visual       │  │  7. Historical Trends        │    │
│  │                   │  │  8. Heatmap                  │    │
│  │  🇲🇿/🇬🇧 Language  │  │  9. Forecast (Poly Reg)     │    │
│  │  toggle (PT/EN)  │  │     + Growth Simulator       │    │
│  └───────────────────┘  │                              │    │
│                         └─────────────────────────────┘     │
│                                                             │
│  Libraries: Plotly Express, Plotly GO, scikit-learn          │
└─────────────────────────────────────────────────────────────┘
```

## Dashboard Pages

| # | Tab | Description |
|---|-----|-------------|
| 1 | **Visao Geral** | KPI cards with YoY deltas, gender distribution, geographic breakdown |
| 2 | **Contas** | Monthly account trends, age distribution, currency split |
| 3 | **Cartoes** | Card trends by month, age group, and card type (credit/debit/prepaid) |
| 4 | **Infraestrutura** | ATM and POS distribution by province/district |
| 5 | **Canais Digitais** | Mobile vs Internet Banking comparison, subscriber growth, transfer analysis |
| 6 | **Transacoes** | Unified dropdown for ATM/POS/Mobile/Internet transactions with volume and value charts |
| 7 | **Tendencias Historicas** | Multi-year evolution with indicator selector and YoY growth rates |
| 8 | **Mapa de Calor** | Province x Year heatmaps for absolute values and growth rates |
| 9 | **Previsoes** | Polynomial regression forecasting (degree 2) with confidence bands, province-level forecasts, and CAGR-seeded manual growth simulator |

## Language Toggle

The dashboard supports **Portuguese (PT)** and **English (EN)**. The default language is Portuguese. Use the 🇲🇿 PT / 🇬🇧 EN toggle buttons in the sidebar to switch. Titles, tab names, labels, and methodology text are all translated. Data labels from the source (province names, metric names) remain in Portuguese.

## Forecasting Methodology

The previous approach (simple linear regression on ~5 yearly aggregates) produced poor R² values (e.g. 0.003 for Mobile Banking) because:
- Only 5 data points (2020-2025, with 2023 missing)
- Non-linear patterns (growth → plateau → decline in some indicators)
- Stock metrics (accounts, cards) were incorrectly summed across 12 monthly snapshots

The new approach addresses all three issues:

| Improvement | Detail |
|-------------|--------|
| **Monthly data** | Uses ~60 monthly observations instead of 5 yearly aggregates |
| **Polynomial (degree 2)** | `PolynomialFeatures(degree=2)` + `LinearRegression` captures acceleration/deceleration |
| **Stock vs Flow** | Stock indicators (accounts, cards, ATMs, POS) use December snapshot; flow indicators (transactions) use annual sum |
| **Confidence bands** | 95% interval (±1.96σ) displayed around forecasts |
| **CAGR default** | Manual simulator slider defaults to the historical Compound Annual Growth Rate |

## Contextual Data

The dashboard is designed to be used alongside **demographic data** from the 2017 Mozambique Census (IV Recenseamento Geral da População e Habitação). Key census indicators relevant to banking analysis include population by province, mobile phone ownership, computer/internet usage, and durable goods ownership — providing the denominator needed to calculate banking penetration rates.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Dashboard | [Streamlit](https://streamlit.io/) |
| Visualisations | [Plotly](https://plotly.com/python/) (Express + Graph Objects) |
| ETL | [Pandas](https://pandas.pydata.org/) + [openpyxl](https://openpyxl.readthedocs.io/) |
| Forecasting | [scikit-learn](https://scikit-learn.org/) (Polynomial Regression) |
| Language | Python 3 |

## Getting Started

### Prerequisites

```bash
pip install streamlit pandas numpy plotly scikit-learn openpyxl
```

### Running the Dashboard

```bash
streamlit run app.py
```

### Regenerating the Data (Optional)

If you have the original `.xlsx` files from Banco de Moçambique, you can re-run the ETL pipeline:

1. Open `ETL.ipynb` in Jupyter
2. Run all cells — this will parse the Excel files and output the 9 CSV files
3. Then run `streamlit run app.py`

## Project Structure

```
BM Project/
├── app.py                              # Streamlit dashboard (main application)
├── ETL.ipynb                           # Jupyter notebook for data extraction & transformation
├── README.md                           # This file
├── banca-electronica-{YYYY}.xlsx       # Raw source files from Banco de Moçambique
├── accounts_2020_2024.csv              # Processed: bank accounts by province/district/month
├── cards_2020_2024.csv                 # Processed: bank cards by province/district/month
├── ATM_Infrastructure_2020_2024.csv    # Processed: ATM counts by location
├── POS_Infrastructure_2020_2024.csv    # Processed: POS terminal counts by location
├── transactions_vol_2020_2024.csv      # Processed: ATM transaction volumes
├── transactions_val_2020_2024.csv      # Processed: ATM transaction values (MZN)
├── POS_Transactions_2020_2024.csv      # Processed: POS transaction volumes & values
├── Mobile_Banking_2020_2024.csv        # Processed: Mobile Banking metrics
├── Internet_Banking_2020_2024.csv      # Processed: Internet Banking metrics
└── .venv/                              # Python virtual environment (not tracked)
```

## Key ETL Decisions

- **December header bug**: The Excel files use merged cells for month/currency/card_type headers. In December columns, the currency and card_type cells are often `NaN`. The ETL uses **positional assignment** (based on column index within each month block) instead of `ffill()` to correctly assign headers.
- **2020 vs 2021+ naming**: The 2020 file uses slightly different metric hierarchies (e.g., `"Transferencias para"` → `"contas bancarias"`). A normalisation function (`normalize_atm_txn`) unifies these across all years.
- **Province ordering**: Provinces are ordered geographically North → South: Cabo Delgado, Niassa, Nampula, Zambezia, Sofala, Tete, Manica, Inhambane, Gaza, Provincia de Maputo.

## Author

**Valter Cheque** - [valtercheque@gmail.com](mailto:valtercheque@gmail.com)
