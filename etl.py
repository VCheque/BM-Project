"""ETL entrypoint for census export and post-processing of extracted CSVs.

This script complements `ETL.ipynb` by providing repeatable, code-reviewed
steps that should live outside the dashboard runtime.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

CENSUS_OUTPUT = Path("census_2017_provinces.csv")
IME_SOURCE = Path("instituições-de-moeda-electrónica-2025.xlsx")
IME_SUBSCRIBERS_OUTPUT = Path("IME_Subscribers_District_2025.csv")
IME_SUBSCRIBERS_DEMO_OUTPUT = Path("IME_Subscribers_District_Demographics_2025.csv")
IME_AGENTS_OUTPUT = Path("IME_Agents_District_2025.csv")
IME_TRANSACTIONS_OUTPUT = Path("IME_Transactions_District_2025.csv")
ACCESS_POINTS_SOURCE = Path("distribuição-dos-pontos-de-acesso-pelos-154-distritos-de-moçambique-iii-trimestre-2025.xlsx")
ACCESS_POINTS_OUTPUT = Path("Access_Points_District_2025Q3.csv")
INCLUSION_INDICATORS_SOURCE = Path("indicadores-estatisticos-de-inclusão-financeira-iii-trimestre-de-2025.xlsx")
INCLUSION_INDICATORS_OUTPUT = Path("Financial_Inclusion_Indicators_2020_2025Q3.csv")
SECTOR_GROWTH_SOURCE = Path("taxas-de-crescimento-produto-sectorial.xls")
SECTOR_GROWTH_OUTPUT = Path("Sectoral_Growth_Rates_2020_2025.csv")
GDP_EXPENDITURE_SOURCE = Path("variação-anual-do-pib_óptica-da-despesa.xls")
GDP_EXPENDITURE_OUTPUT = Path("GDP_Expenditure_Annual_Variation_2020_2025.csv")

MONTH_PT_FULL = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]

MONTH_ALIASES = {
    "Jan": "Janeiro",
    "Janeiro": "Janeiro",
    "Fev": "Fevereiro",
    "Fevereiro": "Fevereiro",
    "Mar": "Março",
    "Março": "Março",
    "Abr": "Abril",
    "Abril": "Abril",
    "Mai": "Maio",
    "Maio": "Maio",
    "Jun": "Junho",
    "Junho": "Junho",
    "Jul": "Julho",
    "Julho": "Julho",
    "Ago": "Agosto",
    "Agosto": "Agosto",
    "Set": "Setembro",
    "Setembro": "Setembro",
    "Out": "Outubro",
    "Outubro": "Outubro",
    "Nov": "Novembro",
    "Novembro": "Novembro",
    "Dez": "Dezembro",
    "Dezembro": "Dezembro",
}

PROVINCE_NAMES = {
    "Niassa",
    "Cabo Delgado",
    "Nampula",
    "Zambézia",
    "Tete",
    "Manica",
    "Sofala",
    "Inhambane",
    "Gaza",
    "Província de Maputo",
    "Cidade de Maputo",
}

# Province-level census aggregates aligned to the banking geography used by the app.
# Source: INE 2017 Census (IV Recenseamento Geral da Populacao e Habitacao).
CENSUS_2017_ROWS = [
    {
        "Province": "Niassa",
        "Population_Total": 1713751,
        "Population_Male": 833704,
        "Population_Female": 880047,
        "Population_Urban": 268480,
        "Population_Rural": 1444271,
        "Population_15plus_2017": 843662,
        "Population_10_14_2017": 217447,
        "Population_15_19_2017": 176040,
        "Pop_0_16": 900000,
        "Pop_17_21": 180000,
        "Pop_22_60": 510000,
        "Pop_60_plus": 123751,
        "Growth_Rate_Pct": 2.3,
        "Phone_Ownership_Pct": 28.4,
        "Internet_Usage_Pct": 3.1,
    },
    {
        "Province": "Cabo Delgado",
        "Population_Total": 2267715,
        "Population_Male": 1098070,
        "Population_Female": 1169645,
        "Population_Urban": 399843,
        "Population_Rural": 1867872,
        "Population_15plus_2017": 1207493,
        "Population_10_14_2017": 266788,
        "Population_15_19_2017": 217256,
        "Pop_0_16": 1190000,
        "Pop_17_21": 238000,
        "Pop_22_60": 680000,
        "Pop_60_plus": 159715,
        "Growth_Rate_Pct": 2.3,
        "Phone_Ownership_Pct": 26.8,
        "Internet_Usage_Pct": 2.8,
    },
    {
        "Province": "Nampula",
        "Population_Total": 5483382,
        "Population_Male": 2659702,
        "Population_Female": 2823680,
        "Population_Urban": 1041743,
        "Population_Rural": 4441639,
        "Population_15plus_2017": 2790747,
        "Population_10_14_2017": 653620,
        "Population_15_19_2017": 541958,
        "Pop_0_16": 2880000,
        "Pop_17_21": 576000,
        "Pop_22_60": 1640000,
        "Pop_60_plus": 387382,
        "Growth_Rate_Pct": 5.0,
        "Phone_Ownership_Pct": 32.1,
        "Internet_Usage_Pct": 4.2,
    },
    {
        "Province": "Zambézia",
        "Population_Total": 5002457,
        "Population_Male": 2396800,
        "Population_Female": 2605657,
        "Population_Urban": 503824,
        "Population_Rural": 4498633,
        "Population_15plus_2017": 2508459,
        "Population_10_14_2017": 654005,
        "Population_15_19_2017": 530024,
        "Pop_0_16": 2626000,
        "Pop_17_21": 525000,
        "Pop_22_60": 1500000,
        "Pop_60_plus": 351457,
        "Growth_Rate_Pct": 3.2,
        "Phone_Ownership_Pct": 22.5,
        "Internet_Usage_Pct": 2.1,
    },
    {
        "Province": "Tete",
        "Population_Total": 2551826,
        "Population_Male": 1245815,
        "Population_Female": 1306011,
        "Population_Urban": 305900,
        "Population_Rural": 2245926,
        "Population_15plus_2017": 1332291,
        "Population_10_14_2017": 336841,
        "Population_15_19_2017": 275474,
        "Pop_0_16": 1339000,
        "Pop_17_21": 268000,
        "Pop_22_60": 765000,
        "Pop_60_plus": 179826,
        "Growth_Rate_Pct": 3.8,
        "Phone_Ownership_Pct": 29.7,
        "Internet_Usage_Pct": 3.4,
    },
    {
        "Province": "Manica",
        "Population_Total": 1851931,
        "Population_Male": 886515,
        "Population_Female": 965416,
        "Population_Urban": 486674,
        "Population_Rural": 1365257,
        "Population_15plus_2017": 960672,
        "Population_10_14_2017": 255360,
        "Population_15_19_2017": 215864,
        "Pop_0_16": 972000,
        "Pop_17_21": 194000,
        "Pop_22_60": 555000,
        "Pop_60_plus": 130931,
        "Growth_Rate_Pct": 5.1,
        "Phone_Ownership_Pct": 35.2,
        "Internet_Usage_Pct": 4.8,
    },
    {
        "Province": "Sofala",
        "Population_Total": 2196845,
        "Population_Male": 1062113,
        "Population_Female": 1134732,
        "Population_Urban": 941284,
        "Population_Rural": 1255561,
        "Population_15plus_2017": 1187456,
        "Population_10_14_2017": 294800,
        "Population_15_19_2017": 262217,
        "Pop_0_16": 1153000,
        "Pop_17_21": 231000,
        "Pop_22_60": 659000,
        "Pop_60_plus": 153845,
        "Growth_Rate_Pct": 2.8,
        "Phone_Ownership_Pct": 38.6,
        "Internet_Usage_Pct": 6.2,
    },
    {
        "Province": "Inhambane",
        "Population_Total": 1454804,
        "Population_Male": 665240,
        "Population_Female": 789564,
        "Population_Urban": 308384,
        "Population_Rural": 1146420,
        "Population_15plus_2017": 829634,
        "Population_10_14_2017": 209875,
        "Population_15_19_2017": 166411,
        "Pop_0_16": 764000,
        "Pop_17_21": 153000,
        "Pop_22_60": 436000,
        "Pop_60_plus": 101804,
        "Growth_Rate_Pct": 2.3,
        "Phone_Ownership_Pct": 37.4,
        "Internet_Usage_Pct": 5.1,
    },
    {
        "Province": "Gaza",
        "Population_Total": 1388039,
        "Population_Male": 627949,
        "Population_Female": 760090,
        "Population_Urban": 397957,
        "Population_Rural": 990082,
        "Population_15plus_2017": 775603,
        "Population_10_14_2017": 198999,
        "Population_15_19_2017": 160683,
        "Pop_0_16": 728000,
        "Pop_17_21": 146000,
        "Pop_22_60": 416000,
        "Pop_60_plus": 98039,
        "Growth_Rate_Pct": 2.5,
        "Phone_Ownership_Pct": 36.8,
        "Internet_Usage_Pct": 4.6,
    },
    {
        "Province": "Província de Maputo",
        "Population_Total": 1908078,
        "Population_Male": 912935,
        "Population_Female": 995143,
        "Population_Urban": 1908078,
        "Population_Rural": 0,
        "Population_15plus_2017": 1185594,
        "Population_10_14_2017": 232945,
        "Population_15_19_2017": 206186,
        "Pop_0_16": 1569000,
        "Pop_17_21": 313000,
        "Pop_22_60": 896000,
        "Pop_60_plus": 210355,
        "Growth_Rate_Pct": 3.4,
        "Phone_Ownership_Pct": 58.2,
        "Internet_Usage_Pct": 17.4,
    },
    {
        "Province": "Cidade de Maputo",
        "Population_Total": 1080277,
        "Population_Male": 521356,
        "Population_Female": 558921,
        "Population_Urban": 1080277,
        "Population_Rural": 0,
        "Population_15plus_2017": 739081,
        "Population_10_14_2017": 111354,
        "Population_15_19_2017": 122838,
        "Pop_0_16": 0,
        "Pop_17_21": 0,
        "Pop_22_60": 0,
        "Pop_60_plus": 0,
        "Growth_Rate_Pct": 3.4,
        "Phone_Ownership_Pct": 58.2,
        "Internet_Usage_Pct": 17.4,
    },
]

CSV_FIX_TARGETS = [
    Path("accounts_2020_2025.csv"),
    Path("cards_2020_2025.csv"),
    Path("ATM_Infrastructure_2020_2025.csv"),
    Path("POS_Infrastructure_2020_2025.csv"),
    Path("transactions_vol_2020_2025.csv"),
    Path("transactions_val_2020_2025.csv"),
    Path("POS_Transactions_2020_2025.csv"),
    Path("Mobile_Banking_2020_2025.csv"),
    Path("Internet_Banking_2020_2025.csv"),
    IME_SUBSCRIBERS_OUTPUT,
    IME_SUBSCRIBERS_DEMO_OUTPUT,
    IME_AGENTS_OUTPUT,
    IME_TRANSACTIONS_OUTPUT,
    ACCESS_POINTS_OUTPUT,
]


def export_census_csv(path: Path = CENSUS_OUTPUT) -> pd.DataFrame:
    df = pd.DataFrame(CENSUS_2017_ROWS)

    # Guardrails for consistency.
    df["Population_Urban"] = df[["Population_Urban", "Population_Total"]].min(axis=1)
    df["Population_Rural"] = (df["Population_Total"] - df["Population_Urban"]).clip(lower=0)

    path.write_text(df.to_csv(index=False))
    return df


def _normalize_month(month_token: str) -> str | None:
    token = str(month_token).strip()
    if token in MONTH_ALIASES:
        return MONTH_ALIASES[token]
    return None


def _extract_ime_volume_value_sheet(
    source_path: Path,
    sheet_name: str,
    txn_type: str,
    year: int = 2025,
) -> pd.DataFrame:
    df = pd.read_excel(source_path, sheet_name=sheet_name, header=None)
    year_row_candidates = df.index[df[0].astype(str).str.contains("Ano:", case=False, na=False)]
    if year_row_candidates.empty:
        return pd.DataFrame(columns=["Year", "Month", "Province", "District", "Transaction_Type", "Volume", "Value"])

    year_row = int(year_row_candidates[0])
    data_start = year_row + 2

    month_pairs: list[tuple[int, str]] = []
    for col in range(1, df.shape[1] - 1, 2):
        month_name = _normalize_month(df.iat[year_row, col])
        if month_name is None:
            continue
        month_pairs.append((col, month_name))

    end = None
    for i in range(data_start + 1, len(df)):
        name = str(df.at[i, 0]).strip()
        if name.lower() == "total":
            end = i
            break
    if end is None:
        end = len(df)

    table = df.iloc[data_start:end, :].copy()
    records: list[dict] = []
    current_province: str | None = None

    for pos, row in table.iterrows():
        raw_name = row.iloc[0]
        if pd.isna(raw_name):
            continue
        name = str(raw_name).strip()
        if not name or name.lower() == "nan":
            continue

        prev_blank = True
        if pos > table.index.min():
            prev_raw = table.at[pos - 1, 0]
            prev_blank = pd.isna(prev_raw) or str(prev_raw).strip() in {"", "0"}

        is_province_header = name in PROVINCE_NAMES and (pos == table.index.min() or prev_blank)
        if is_province_header:
            current_province = name
            continue
        if current_province is None:
            continue

        for col, month_name in month_pairs:
            volume = pd.to_numeric(row.iloc[col], errors="coerce")
            value = pd.to_numeric(row.iloc[col + 1], errors="coerce")
            if pd.isna(volume) and pd.isna(value):
                continue
            records.append(
                {
                    "Year": year,
                    "Month": month_name,
                    "Province": current_province,
                    "District": name,
                    "Transaction_Type": txn_type,
                    "Volume": float(max(volume, 0)) if not pd.isna(volume) else 0.0,
                    "Value": float(max(value, 0)) if not pd.isna(value) else 0.0,
                }
            )

    return pd.DataFrame(records)


def _extract_ime_agents_sheet(source_path: Path, year: int = 2025) -> pd.DataFrame:
    df = pd.read_excel(source_path, sheet_name="Agentes 2025", header=None)
    month_row = 1
    data_start = 2

    end = None
    for i in range(data_start + 1, len(df)):
        name = str(df.at[i, 0]).strip()
        if name.lower() == "total":
            end = i
            break
    if end is None:
        end = len(df)

    table = df.iloc[data_start:end, :13].copy()
    records: list[dict] = []
    current_province: str | None = None

    for pos, row in table.iterrows():
        raw_name = row.iloc[0]
        if pd.isna(raw_name):
            continue
        name = str(raw_name).strip()
        if not name or name.lower() == "nan":
            continue

        prev_blank = True
        if pos > table.index.min():
            prev_raw = table.at[pos - 1, 0]
            prev_blank = pd.isna(prev_raw) or str(prev_raw).strip() in {"", "0"}

        is_province_header = name in PROVINCE_NAMES and (pos == table.index.min() or prev_blank)
        if is_province_header:
            current_province = name
            continue
        if current_province is None:
            continue

        for col in range(1, 13):
            month = _normalize_month(df.iat[month_row, col])
            if month is None:
                continue
            val = pd.to_numeric(row.iloc[col], errors="coerce")
            if pd.isna(val):
                continue
            records.append(
                {
                    "Year": year,
                    "Month": month,
                    "Province": current_province,
                    "District": name,
                    "Agents": float(max(val, 0)),
                }
            )

    return pd.DataFrame(records)


def _extract_ime_subscribers_demographics(source_path: Path, year: int = 2025) -> pd.DataFrame:
    df = pd.read_excel(source_path, sheet_name="subscritores das IME 2025", header=None)
    month_row = 2
    data_start = 5

    end = None
    for i in range(data_start + 1, len(df)):
        name = str(df.at[i, 0]).strip()
        if name.lower() == "total":
            end = i
            break
    if end is None:
        end = len(df)

    table = df.iloc[data_start:end, :109].copy()
    records: list[dict] = []
    current_province: str | None = None
    age_labels = ["0 a 16", "17 a 21", "22 a 60", "Mais de 60"]

    for pos, row in table.iterrows():
        raw_name = row.iloc[0]
        if pd.isna(raw_name):
            continue
        name = str(raw_name).strip()
        if not name or name.lower() == "nan":
            continue

        prev_blank = True
        if pos > table.index.min():
            prev_raw = table.at[pos - 1, 0]
            prev_blank = pd.isna(prev_raw) or str(prev_raw).strip() in {"", "0"}

        is_province_header = name in PROVINCE_NAMES and (pos == table.index.min() or prev_blank)
        if is_province_header:
            current_province = name
            continue
        if current_province is None:
            continue

        for start_col in range(1, 109, 9):
            month = _normalize_month(df.iat[month_row, start_col])
            if month is None:
                continue

            for offset, age in enumerate(age_labels):
                male_val = pd.to_numeric(row.iloc[start_col + offset], errors="coerce")
                if not pd.isna(male_val):
                    records.append(
                        {
                            "Year": year,
                            "Month": month,
                            "Province": current_province,
                            "District": name,
                            "Gender": "Homens",
                            "Age": age,
                            "Subscribers": float(max(male_val, 0)),
                        }
                    )
                female_val = pd.to_numeric(row.iloc[start_col + 4 + offset], errors="coerce")
                if not pd.isna(female_val):
                    records.append(
                        {
                            "Year": year,
                            "Month": month,
                            "Province": current_province,
                            "District": name,
                            "Gender": "Mulheres",
                            "Age": age,
                            "Subscribers": float(max(female_val, 0)),
                        }
                    )

            other_val = pd.to_numeric(row.iloc[start_col + 8], errors="coerce")
            if not pd.isna(other_val):
                records.append(
                    {
                        "Year": year,
                        "Month": month,
                        "Province": current_province,
                        "District": name,
                        "Gender": "Outros",
                        "Age": "N/A",
                        "Subscribers": float(max(other_val, 0)),
                    }
                )

    return pd.DataFrame(records)


def export_ime_2025_csvs(
    source_path: Path = IME_SOURCE,
    subscribers_path: Path = IME_SUBSCRIBERS_OUTPUT,
    subscribers_demo_path: Path = IME_SUBSCRIBERS_DEMO_OUTPUT,
    agents_path: Path = IME_AGENTS_OUTPUT,
    transactions_path: Path = IME_TRANSACTIONS_OUTPUT,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Extract district-level IME datasets from workbook (2025)."""
    if not source_path.exists():
        raise FileNotFoundError(f"IME source file not found: {source_path}")

    subscribers_demo = _extract_ime_subscribers_demographics(source_path, year=2025)
    subscribers = (
        subscribers_demo.groupby(["Year", "Month", "Province", "District"], as_index=False)["Subscribers"]
        .sum()
    )
    agents = _extract_ime_agents_sheet(source_path, year=2025)
    transactions = pd.concat(
        [
            _extract_ime_volume_value_sheet(source_path, "Depósitos IME 2025", "Depósitos", year=2025),
            _extract_ime_volume_value_sheet(source_path, "Levantamentos IME 2025", "Levantamentos", year=2025),
            _extract_ime_volume_value_sheet(source_path, "Transferências IME 2025", "Transferências", year=2025),
            _extract_ime_volume_value_sheet(source_path, "Pagamentos IME 2025", "Pagamentos", year=2025),
        ],
        ignore_index=True,
    )

    subscribers.to_csv(subscribers_path, index=False)
    subscribers_demo.to_csv(subscribers_demo_path, index=False)
    agents.to_csv(agents_path, index=False)
    transactions.to_csv(transactions_path, index=False)
    return subscribers, subscribers_demo, agents, transactions


def _parse_period_label(raw_period) -> tuple[str | None, int | None, str | None]:
    if pd.isna(raw_period):
        return None, None, None
    if isinstance(raw_period, (int, float)) and not pd.isna(raw_period):
        year = int(raw_period)
        return str(year), year, None
    token = str(raw_period).strip()
    if not token or token.lower() == "nan":
        return None, None, None
    if len(token) == 6 and token[:4].isdigit() and token[4].upper() == "Q" and token[5].isdigit():
        year = int(token[:4])
        quarter = f"Q{token[5]}"
        return token, year, quarter
    if token.isdigit() and len(token) == 4:
        year = int(token)
        return token, year, None
    return token, None, None


def export_access_points_2025q3_csv(
    source_path: Path = ACCESS_POINTS_SOURCE,
    output_path: Path = ACCESS_POINTS_OUTPUT,
) -> pd.DataFrame:
    """Extract district/province access points table from BoM 2025Q3 workbook."""
    if not source_path.exists():
        raise FileNotFoundError(f"Access points source not found: {source_path}")

    df = pd.read_excel(source_path, sheet_name="MAPA PDA", header=None)
    block_start, block_end = 65, 74
    metric_cols = list(range(block_start + 1, block_end + 1))
    metric_names = [str(df.iat[1, c]).strip() for c in metric_cols]

    end_idx_candidates = df.index[df[0].astype(str).str.contains("Total de Pontos de Acesso", case=False, na=False)]
    end_idx = int(end_idx_candidates[0]) if not end_idx_candidates.empty else len(df)
    table = df.iloc[2:end_idx, :].copy()

    records: list[dict] = []
    current_province: str | None = None
    for pos, row in table.iterrows():
        raw_name = row.iloc[0]
        if pd.isna(raw_name):
            continue
        name = str(raw_name).strip()
        if not name or name.lower() == "nan":
            continue

        prev_blank = True
        if pos > table.index.min():
            prev_raw = table.at[pos - 1, 0]
            prev_blank = pd.isna(prev_raw) or str(prev_raw).strip() == ""

        is_province_header = name in PROVINCE_NAMES and (pos == table.index.min() or prev_blank)
        if is_province_header:
            current_province = name
            level = "Province"
            district_val = None
        else:
            level = "District"
            district_val = name

        if current_province is None:
            current_province = name if is_province_header else None
        if current_province is None:
            continue

        for col, metric in zip(metric_cols, metric_names):
            val = pd.to_numeric(row.iloc[col], errors="coerce")
            if pd.isna(val):
                continue
            records.append(
                {
                    "Year": 2025,
                    "Quarter": "Q3",
                    "Level": level,
                    "Province": current_province,
                    "District": district_val,
                    "Metric": metric,
                    "Value": float(max(val, 0)),
                }
            )

    out = pd.DataFrame(records)
    out.to_csv(output_path, index=False)
    return out


def export_inclusion_indicators_csv(
    source_path: Path = INCLUSION_INDICATORS_SOURCE,
    output_path: Path = INCLUSION_INDICATORS_OUTPUT,
) -> pd.DataFrame:
    """Extract BoM inclusion indicators into long format (2020-2025 period-level)."""
    if not source_path.exists():
        raise FileNotFoundError(f"Inclusion indicators source not found: {source_path}")

    df = pd.read_excel(source_path, sheet_name="Tabs Relatorio", header=None)
    table_starts = df.index[df[0].astype(str).str.contains("TABELA", case=False, na=False)].tolist()
    table_starts.append(len(df))

    records: list[dict] = []
    for i in range(len(table_starts) - 1):
        start = table_starts[i]
        end = table_starts[i + 1]
        table_name = str(df.iat[start, 0]).strip()
        header_row = start + 1
        period_labels = {c: df.iat[header_row, c] for c in range(1, df.shape[1])}

        for r in range(header_row + 1, end):
            indicator_raw = df.iat[r, 0]
            if pd.isna(indicator_raw):
                continue
            indicator = str(indicator_raw).strip()
            if not indicator or indicator.lower() == "nan":
                continue

            for c, raw_period in period_labels.items():
                period_label, year, quarter = _parse_period_label(raw_period)
                if period_label is None:
                    continue
                val = pd.to_numeric(df.iat[r, c], errors="coerce")
                if pd.isna(val):
                    continue
                records.append(
                    {
                        "Table": table_name,
                        "Indicator": indicator,
                        "Period": period_label,
                        "Year": year,
                        "Quarter": quarter,
                        "Value": float(val),
                    }
                )

    out = pd.DataFrame(records)
    if not out.empty:
        out = out[out["Year"].notna()].copy()
        out["Year"] = out["Year"].astype(int)
        out = out[(out["Year"] >= 2020) & (out["Year"] <= 2025)]
    out.to_csv(output_path, index=False)
    return out


def _read_xls_or_raise(path: Path) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=0, header=None, engine="xlrd")
    except ImportError as exc:
        raise ImportError(
            "xlrd is required to parse .xls files. Install with: pip install 'xlrd>=2.0.1'"
        ) from exc


def export_xls_indicator_long_csv(
    source_path: Path,
    output_path: Path,
    dataset_name: str,
    year_min: int = 2020,
    year_max: int = 2025,
) -> pd.DataFrame:
    """Extract legacy .xls workbook to long format (indicator, year, value)."""
    if not source_path.exists():
        raise FileNotFoundError(f"XLS source not found: {source_path}")
    df = _read_xls_or_raise(source_path)
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df = df.reset_index(drop=True)
    df.columns = range(df.shape[1])

    header_candidates = df.index[df.iloc[:, 0].astype(str).str.contains("Descrição|Description", case=False, na=False)]
    if header_candidates.empty:
        raise ValueError(f"Could not find indicator header row in {source_path.name}")
    header_row = int(header_candidates[0])

    year_cols: list[tuple[int, int]] = []
    for c in range(1, df.shape[1]):
        y = pd.to_numeric(df.iat[header_row, c], errors="coerce")
        if pd.notna(y):
            yi = int(y)
            if year_min <= yi <= year_max:
                year_cols.append((c, yi))

    records: list[dict] = []
    for r in range(header_row + 1, len(df)):
        indicator_raw = df.iat[r, 0]
        if pd.isna(indicator_raw):
            continue
        indicator = str(indicator_raw).strip()
        if not indicator or indicator.lower() == "nan":
            continue
        for c, year in year_cols:
            val = pd.to_numeric(df.iat[r, c], errors="coerce")
            if pd.isna(val):
                continue
            records.append(
                {
                    "Dataset": dataset_name,
                    "Indicator": indicator,
                    "Year": year,
                    "Value": float(val),
                }
            )

    out = pd.DataFrame(records)
    out.to_csv(output_path, index=False)
    return out


def export_bom_context_csvs() -> dict[str, int]:
    """Export additional BoM context datasets used for extended analysis."""
    counts: dict[str, int] = {}
    access_df = export_access_points_2025q3_csv()
    counts[str(ACCESS_POINTS_OUTPUT)] = len(access_df)
    ind_df = export_inclusion_indicators_csv()
    counts[str(INCLUSION_INDICATORS_OUTPUT)] = len(ind_df)

    try:
        sec_df = export_xls_indicator_long_csv(
            SECTOR_GROWTH_SOURCE,
            SECTOR_GROWTH_OUTPUT,
            dataset_name="Sectoral Growth Rates",
        )
        counts[str(SECTOR_GROWTH_OUTPUT)] = len(sec_df)
    except (ImportError, ValueError):
        counts[str(SECTOR_GROWTH_OUTPUT)] = -1

    try:
        gdp_df = export_xls_indicator_long_csv(
            GDP_EXPENDITURE_SOURCE,
            GDP_EXPENDITURE_OUTPUT,
            dataset_name="GDP Expenditure Annual Variation",
        )
        counts[str(GDP_EXPENDITURE_OUTPUT)] = len(gdp_df)
    except (ImportError, ValueError):
        counts[str(GDP_EXPENDITURE_OUTPUT)] = -1

    return counts


def postprocess_csv(path: Path) -> None:
    if not path.exists():
        return

    df = pd.read_csv(path)

    # Drop notebook index artifacts.
    keep_cols = [c for c in df.columns if not str(c).startswith("Unnamed:")]
    df = df[keep_cols].copy()

    if "District" in df.columns:
        df["District"] = df["District"].astype(str).str.strip().replace(
            {
                "Cidade de de Maputo": "Cidade de Maputo",
                "Cabo-Delgado": "Cabo Delgado",
            }
        )
        if "Province" in df.columns:
            maputo_city_mask = (df["Province"] == "Província de Maputo") & (df["District"] == "Maputo")
            df.loc[maputo_city_mask, "District"] = "Cidade de Maputo"

    # Keep numeric columns non-negative for stock/flow counts.
    num_cols = df.select_dtypes(include=["number"]).columns
    df[num_cols] = df[num_cols].clip(lower=0)

    df.to_csv(path, index=False)


def run_postprocess() -> None:
    for path in CSV_FIX_TARGETS:
        postprocess_csv(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ETL post-processing tasks.")
    parser.add_argument(
        "--export-census",
        action="store_true",
        help="Generate census_2017_provinces.csv from maintained ETL source rows.",
    )
    parser.add_argument(
        "--postprocess-csvs",
        action="store_true",
        help="Apply naming/index cleanup to generated CSV outputs.",
    )
    parser.add_argument(
        "--export-ime",
        action="store_true",
        help="Extract IME 2025 district datasets (subscribers, agents, transactions).",
    )
    parser.add_argument(
        "--export-bom-context",
        action="store_true",
        help="Extract additional BoM context datasets (access points, inclusion indicators, macro xls raw).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all ETL maintenance tasks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_all = args.all or (
        not args.export_census
        and not args.postprocess_csvs
        and not args.export_ime
        and not args.export_bom_context
    )

    if args.export_census or run_all:
        df = export_census_csv()
        print(f"Exported {CENSUS_OUTPUT} ({len(df)} provinces)")

    if args.postprocess_csvs or run_all:
        run_postprocess()
        print("Post-processed CSV outputs")

    if args.export_ime or run_all:
        subs, subs_demo, agents, txns = export_ime_2025_csvs()
        print(f"Exported {IME_SUBSCRIBERS_OUTPUT} ({len(subs)} rows)")
        print(f"Exported {IME_SUBSCRIBERS_DEMO_OUTPUT} ({len(subs_demo)} rows)")
        print(f"Exported {IME_AGENTS_OUTPUT} ({len(agents)} rows)")
        print(f"Exported {IME_TRANSACTIONS_OUTPUT} ({len(txns)} rows)")

    if args.export_bom_context or run_all:
        counts = export_bom_context_csvs()
        for output, nrows in counts.items():
            if nrows >= 0:
                print(f"Exported {output} ({nrows} rows)")
            else:
                print(
                    f"Skipped {output} (requires xlrd for .xls parsing; install with: pip install 'xlrd>=2.0.1')"
                )


if __name__ == "__main__":
    main()
