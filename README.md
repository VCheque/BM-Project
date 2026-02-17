# Mozambique Electronic Banking Dashboard

Interactive Streamlit dashboard for analysing electronic banking and mobile wallet usage in Mozambique using official public data.

## Scope

The app combines banking system indicators, mobile wallet district data, and demographic context to support:

- descriptive monitoring,
- inclusion analysis,
- territorial prioritisation,
- short-term flow forecasting.

## Data Sources

- Banco de Moçambique (electronic banking statistics):
  - https://www.bancomoc.mz/pt/areas-de-actuacao/estatisticas/dominios-e-indicadores-estatisticos/
- INE Census 2017 (demographic baseline)
- INCM Acervo telecom (mobile subscribers benchmark):
  - https://acervo.incm.gov.mz/#/public/telecom

## Current Dashboard Structure

1. `📊 Overview + Q&A`
2. `📱 Carteiras Móveis`
3. `🎯 Insights Estratégicos / Oportunidades`
4. `🗺️ Contexto Demográfico`
5. `📱 Canais Digitais + 💸 Transações`
6. `🏦 Contas + 💳 Cartões`
7. `📡 Infraestrutura`
8. `📈 Tendências Históricas`
9. `🔮 Previsões`

## Methodology (Current)

- Stock indicators (`accounts`, `cards`, `ATMs`, `POS`) use December reported values.
- Flow indicators (transactions) use period aggregation appropriate to each visual.
- In `Banca Electrónica`, the `Mobile Banking` indicator refers only to commercial bank mobile apps (e.g., NetPlus, IZI, Daki); it is not the same as IME wallet data.
- The overview includes a bridge reading between `Mobile Banking → telemóveis` flows and `ATM levantamentos de fundos depositados em telemóveis`.
- Financial inclusion cards prioritise official BoM inclusion indicators when available.
- If official indicator is unavailable for a period, fallback uses Census 2017 denominator extrapolation by age cohort progression.
- `Cidade de Maputo` is harmonised under `Província de Maputo` for geographic consistency in this dashboard.
- IME/INCM comparison is treated as a relative index (not unique-person penetration).
- Forecasts are statistical projections (not causal inference), focused on flow indicators and short-term interpretation.

## Main Caveats

- Mobile Wallet district detail currently includes years 2023 and 2025.
- District-level Mobile Wallet reading covers only districts present in the official 2025 file reported by Banco de Moçambique.
- The 2024 IME source file is rights-protected and is not included in the current data extraction.
- Official and fallback denominator logic can produce different inclusion levels.
- Subscriber-based metrics can include multi-SIM/multi-service effects.

## Run

Install dependencies:

```bash
pip install streamlit pandas numpy plotly openpyxl xlrd
```

Optional ETL refresh:

```bash
python etl.py --all
```

Run app:

```bash
streamlit run app.py
```

## Optional GeoJSON (Province Choropleth)

If one of the following files exists in project root, the demographic map can use true ADM1 polygons:

- `geoBoundaries-MOZ-ADM1_simplified.geojson`
- `geoBoundaries-MOZ-ADM1.geojson`
- `mozambique_adm1.geojson`
- `moz_adm1.geojson`

Otherwise, the app uses marker-based fallback.

## Author

Valter Cheque
