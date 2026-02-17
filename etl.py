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
BANKING_SOURCE_2023 = Path("banca-electronica-2023.xlsx")
IME_SOURCE_TEMPLATE = "instituições-de-moeda-electrónica-{year}.xlsx"

IME_SUBSCRIBERS_2023_2025_OUTPUT = Path("IME_Subscribers_District_2023_2025.csv")
IME_SUBSCRIBERS_DEMO_2023_2025_OUTPUT = Path("IME_Subscribers_District_Demographics_2023_2025.csv")
IME_AGENTS_2023_2025_OUTPUT = Path("IME_Agents_District_2023_2025.csv")
IME_TRANSACTIONS_2023_2025_OUTPUT = Path("IME_Transactions_District_2023_2025.csv")

MONTHS_12 = [
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
}

GEO_NAME_ALIASES = {
    "Maputo": "Província de Maputo",
    "Cabo-Delgado": "Cabo Delgado",
    "Cidade de de Maputo": "Cidade de Maputo",
    "Zambezia": "Zambézia",
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
    IME_SUBSCRIBERS_2023_2025_OUTPUT,
    IME_SUBSCRIBERS_DEMO_2023_2025_OUTPUT,
    IME_AGENTS_2023_2025_OUTPUT,
    IME_TRANSACTIONS_2023_2025_OUTPUT,
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


def _normalize_geo_label(raw_label) -> str | None:
    if pd.isna(raw_label):
        return None
    token = str(raw_label).strip()
    if not token or token.lower() == "nan":
        return None
    return GEO_NAME_ALIASES.get(token, token)


def _is_province_header(name: str, current_province: str | None) -> bool:
    # Note to self: header spacing in source sheets is unreliable, so I trust label transitions instead.
    return name in PROVINCE_NAMES and name != current_province


def _clean_numeric(value) -> float:
    if pd.isna(value):
        return 0.0
    token = str(value).strip().replace(" ", "")
    if token in {"", "-", "..", "nan", "NaN"}:
        return 0.0
    token = token.replace(",", ".").replace("(", "-").replace(")", "")
    try:
        out = float(token)
    except ValueError:
        return 0.0
    return float(max(out, 0.0))


def _read_excel_sheet(source_path: Path, sheet_name: str) -> pd.DataFrame:
    """Read worksheet with engine fallback for mixed xlsx/xls-in-xlsx files."""
    errors: list[str] = []
    for engine in ("openpyxl", "xlrd", None):
        try:
            kwargs = {"sheet_name": sheet_name, "header": None}
            if engine is not None:
                kwargs["engine"] = engine
            return pd.read_excel(source_path, **kwargs)
        except Exception as exc:  # noqa: BLE001
            label = engine or "auto"
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
    raise ValueError(f"Could not read '{sheet_name}' in {source_path.name}. " + " | ".join(errors))


def _list_sheet_names(source_path: Path) -> list[str]:
    errors: list[str] = []
    for engine in ("openpyxl", "xlrd", None):
        try:
            if engine is None:
                return pd.ExcelFile(source_path).sheet_names
            return pd.ExcelFile(source_path, engine=engine).sheet_names
        except Exception as exc:  # noqa: BLE001
            label = engine or "auto"
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
    raise ValueError(f"Could not list sheets in {source_path.name}. " + " | ".join(errors))


def _pick_sheet_name(source_path: Path, contains_tokens: list[str]) -> str:
    tokens = [t.casefold() for t in contains_tokens]
    for sheet in _list_sheet_names(source_path):
        s = sheet.casefold()
        if all(tok in s for tok in tokens):
            return sheet
    raise ValueError(f"No sheet found in {source_path.name} with tokens {contains_tokens}")


def _month_cols_from_header(row: pd.Series) -> list[tuple[int, str]]:
    cols: list[tuple[int, str]] = []
    for c in range(1, len(row)):
        m = _normalize_month(row.iloc[c])
        if m is None:
            continue
        cols.append((c, m))
        if len(cols) == 12:
            break
    return cols


def _find_label_row(df: pd.DataFrame, label: str, start_at: int = 0, exact: bool = True) -> int:
    target = label.casefold().strip()
    col = df[0].astype(str).fillna("").str.strip().str.casefold()
    if exact:
        candidates = col.index[(col == target) & (col.index >= start_at)]
    else:
        candidates = col.index[(col.str.contains(target, na=False)) & (col.index >= start_at)]
    if len(candidates) == 0:
        raise ValueError(f"Label '{label}' not found")
    return int(candidates[0])


def _extract_geo_stock_section(
    df: pd.DataFrame,
    start_row: int,
    end_row: int,
    month_cols: list[tuple[int, str]],
    value_col: str,
    year: int,
) -> pd.DataFrame:
    table = df.iloc[start_row:end_row, :].copy()
    records: list[dict] = []
    current_province: str | None = None
    for _, row in table.iterrows():
        name = _normalize_geo_label(row.iloc[0])
        if name is None:
            continue
        if _is_province_header(name, current_province):
            current_province = name
            continue
        if current_province is None:
            continue
        for col, month in month_cols:
            records.append(
                {
                    "Year": year,
                    "Province": current_province,
                    "District": name,
                    "Month": month,
                    value_col: _clean_numeric(row.iloc[col]),
                }
            )
    return pd.DataFrame(records)


def _extract_atm_transaction_block(
    df: pd.DataFrame,
    start_row: int,
    end_row: int,
    month_cols: list[tuple[int, str]],
    category: str,
    value_col: str,
    year: int,
) -> pd.DataFrame:
    table = df.iloc[start_row:end_row, :].copy().reset_index(drop=True)
    sub_keywords = [
        "com cartões",
        "com cartoes",
        "de fundos",
        "contas bancárias",
        "contas bancarias",
        "telemóveis",
        "telemoveis",
    ]
    records: list[dict] = []
    current_parent: str | None = None
    for i in range(len(table)):
        label_raw = table.at[i, 0]
        if pd.isna(label_raw):
            continue
        label = str(label_raw).strip()
        if not label or label.lower() == "nan":
            continue
        lbl = label.casefold()
        is_sub = any(k in lbl for k in sub_keywords)
        has_sub_next = False
        if i + 1 < len(table):
            nxt_raw = table.at[i + 1, 0]
            if pd.notna(nxt_raw):
                nxt = str(nxt_raw).strip().casefold()
                has_sub_next = any(k in nxt for k in sub_keywords)
        if not is_sub:
            current_parent = label
            if has_sub_next:
                continue
            metric, sub_metric = label, None
        else:
            if current_parent is None:
                continue
            metric, sub_metric = current_parent, label
        for col, month in month_cols:
            records.append(
                {
                    "Year": year,
                    "Month": month,
                    "Category": category,
                    "Metric": metric,
                    "Sub_Metric": sub_metric,
                    value_col: _clean_numeric(table.at[i, col]),
                }
            )
    return pd.DataFrame(records)


def _extract_flat_metric_block(
    df: pd.DataFrame,
    start_row: int,
    end_row: int,
    month_cols: list[tuple[int, str]],
    category: str,
    value_col: str,
    year: int,
) -> pd.DataFrame:
    table = df.iloc[start_row:end_row, :].copy()
    records: list[dict] = []
    for _, row in table.iterrows():
        metric_raw = row.iloc[0]
        if pd.isna(metric_raw):
            continue
        metric = str(metric_raw).strip()
        if not metric or metric.lower() == "nan":
            continue
        for col, month in month_cols:
            records.append(
                {
                    "Year": year,
                    "Month": month,
                    "Category": category,
                    "Metric": metric,
                    "Sub_Metric": None,
                    value_col: _clean_numeric(row.iloc[col]),
                }
            )
    return pd.DataFrame(records)


def _extract_banca_sheet_2023(source_path: Path, year: int = 2023) -> dict[str, pd.DataFrame]:
    sheet_name = _pick_sheet_name(source_path, ["banca", str(year)])
    df = _read_excel_sheet(source_path, sheet_name)
    month_cols = _month_cols_from_header(df.iloc[1])
    if len(month_cols) != 12:
        raise ValueError(f"Could not resolve 12 months in sheet '{sheet_name}'")

    atm_header = _find_label_row(df, "ATM´s")
    pos_headers = [
        int(i)
        for i in df.index[df[0].astype(str).fillna("").str.strip().str.casefold() == "pos´s".casefold()]
    ]
    if len(pos_headers) < 2:
        raise ValueError("Expected two 'POS´s' section headers in banca sheet")
    pos_infra_header = pos_headers[0]
    pos_txn_header = pos_headers[1]
    atm_txn_vol_header = _find_label_row(df, "Volume de transacções efectuadas em ATM", exact=False)
    atm_txn_val_header = _find_label_row(df, "Valor de transacções efectuadas em ATM", exact=False)
    mobile_header = _find_label_row(df, "Mobile Banking")
    internet_header = _find_label_row(df, "Internet Banking")

    out: dict[str, pd.DataFrame] = {}
    out["atm"] = _extract_geo_stock_section(
        df, atm_header + 1, pos_infra_header, month_cols, "ATMs_Number", year
    )
    out["pos"] = _extract_geo_stock_section(
        df, pos_infra_header + 1, atm_txn_vol_header, month_cols, "POSs_Number", year
    )
    out["transactions_vol"] = _extract_atm_transaction_block(
        df,
        atm_txn_vol_header + 1,
        atm_txn_val_header,
        month_cols,
        "ATM_Transactions_Vol",
        "Total_Transactions",
        year,
    )
    out["transactions_val"] = _extract_atm_transaction_block(
        df,
        atm_txn_val_header + 1,
        pos_txn_header,
        month_cols,
        "ATM_Transactions_Val",
        "Transactions_Amount",
        year,
    )
    out["pos_transactions"] = _extract_flat_metric_block(
        df, pos_txn_header + 1, mobile_header, month_cols, "POS_Transactions", "Value", year
    )
    out["mobile_banking"] = _extract_flat_metric_block(
        df, mobile_header + 1, internet_header, month_cols, "Mobile_Banking", "Value", year
    )
    out["internet_banking"] = _extract_flat_metric_block(
        df, internet_header + 1, len(df), month_cols, "Internet_Banking", "Value", year
    )
    return out


def _extract_accounts_sheet(source_path: Path, year: int) -> pd.DataFrame:
    sheet_name = _pick_sheet_name(source_path, ["contas bancárias", str(year)])
    df_raw = _read_excel_sheet(source_path, sheet_name)
    year_row_candidates = df_raw.index[df_raw[0].astype(str).str.contains("Ano:", case=False, na=False)]
    if len(year_row_candidates) == 0:
        raise ValueError(f"Could not find year header row in {sheet_name}")
    year_row = int(year_row_candidates[0])
    months_raw = df_raw.iloc[year_row].copy()
    data_start = year_row + 4

    month_starts = [i for i in range(1, len(months_raw)) if _normalize_month(months_raw.iloc[i]) is not None]
    cols_per_month = month_starts[1] - month_starts[0] if len(month_starts) >= 2 else 18
    expected_cols = min(df_raw.shape[1], 1 + 12 * cols_per_month)
    df_raw = df_raw.iloc[:, :expected_cols].copy()
    months = df_raw.iloc[year_row].ffill()
    genders = df_raw.iloc[year_row + 2].ffill()
    ages = df_raw.iloc[year_row + 3]

    end = None
    for i in range(data_start + 1, len(df_raw)):
        if str(df_raw.iat[i, 0]).strip().lower() == "total":
            end = i
            break
    if end is None:
        end = len(df_raw)

    currency_half = cols_per_month // 2
    currency_labels = ["Em Meticais"] * currency_half + ["Em Moeda Estrangeira"] * (cols_per_month - currency_half)
    records: list[dict] = []
    current_province: str | None = None
    for _, row in df_raw.iloc[data_start:end, :].iterrows():
        name = _normalize_geo_label(row.iloc[0])
        if name is None:
            continue
        if _is_province_header(name, current_province):
            current_province = name
            continue
        if current_province is None:
            continue
        for c in range(1, expected_cols):
            month = _normalize_month(months.iloc[c])
            if month is None:
                continue
            offset = (c - 1) % cols_per_month
            records.append(
                {
                    "Province": current_province,
                    "District": name,
                    "Month": month,
                    "Account_Currency": currency_labels[offset],
                    "Gender": str(genders.iloc[c]).strip(),
                    "Total_Accounts": _clean_numeric(row.iloc[c]),
                    "Year": year,
                    "Age": str(ages.iloc[c]).strip() if pd.notna(ages.iloc[c]) else None,
                }
            )
    out = pd.DataFrame(records)
    out = out[~out["District"].isin(["Total", "nan"])].copy()
    return out


def _extract_cards_sheet(source_path: Path, year: int) -> pd.DataFrame:
    sheet_name = _pick_sheet_name(source_path, ["cartões bancários", str(year)])
    df_raw = _read_excel_sheet(source_path, sheet_name)
    year_row_candidates = df_raw.index[df_raw[0].astype(str).str.contains("ANO:", case=False, na=False)]
    if len(year_row_candidates) == 0:
        raise ValueError(f"Could not find year header row in {sheet_name}")
    year_row = int(year_row_candidates[0])
    months_raw = df_raw.iloc[year_row].copy()
    data_start = year_row + 4

    month_starts = [i for i in range(1, len(months_raw)) if _normalize_month(months_raw.iloc[i]) is not None]
    cols_per_month = month_starts[1] - month_starts[0] if len(month_starts) >= 2 else 27
    expected_cols = min(df_raw.shape[1], 1 + 12 * cols_per_month)
    df_raw = df_raw.iloc[:, :expected_cols].copy()
    months = df_raw.iloc[year_row].ffill()
    genders = df_raw.iloc[year_row + 2].ffill()
    ages = df_raw.iloc[year_row + 3]

    end = None
    for i in range(data_start + 1, len(df_raw)):
        if str(df_raw.iat[i, 0]).strip().lower() == "total":
            end = i
            break
    if end is None:
        end = len(df_raw)

    group_size = max(1, cols_per_month // 3)
    card_type_labels = (
        ["Cartões de Crédito"] * group_size
        + ["Cartões de Débito"] * group_size
        + ["Cartões pré-pagos"] * (cols_per_month - 2 * group_size)
    )
    records: list[dict] = []
    current_province: str | None = None
    for _, row in df_raw.iloc[data_start:end, :].iterrows():
        name = _normalize_geo_label(row.iloc[0])
        if name is None:
            continue
        if _is_province_header(name, current_province):
            current_province = name
            continue
        if current_province is None:
            continue
        for c in range(1, expected_cols):
            month = _normalize_month(months.iloc[c])
            if month is None:
                continue
            offset = (c - 1) % cols_per_month
            records.append(
                {
                    "Year": year,
                    "Province": current_province,
                    "District": name,
                    "Month": month,
                    "Card_Type": card_type_labels[offset],
                    "Gender": str(genders.iloc[c]).strip(),
                    "Age": str(ages.iloc[c]).strip() if pd.notna(ages.iloc[c]) else None,
                    "Total_Cards": _clean_numeric(row.iloc[c]),
                }
            )
    out = pd.DataFrame(records)
    out = out[~out["District"].isin(["Total", "nan"])].copy()
    return out


def _upsert_year(csv_path: Path, year: int, new_df: pd.DataFrame) -> pd.DataFrame:
    if csv_path.exists():
        existing = pd.read_csv(csv_path)
        existing = existing[pd.to_numeric(existing["Year"], errors="coerce") != year].copy()
        merged = pd.concat([existing, new_df], ignore_index=True)
    else:
        merged = new_df.copy()
    merged = merged.sort_values(["Year"]).reset_index(drop=True)
    merged.to_csv(csv_path, index=False)
    return merged


def export_banking_year_into_core_csvs(source_path: Path = BANKING_SOURCE_2023, year: int = 2023) -> dict[str, int]:
    """Extract a banking year workbook and upsert rows into core 2020_2025 CSV outputs."""
    if not source_path.exists():
        raise FileNotFoundError(f"Banking source file not found: {source_path}")
    accounts_df = _extract_accounts_sheet(source_path, year)
    cards_df = _extract_cards_sheet(source_path, year)
    banca_parts = _extract_banca_sheet_2023(source_path, year)

    outputs = {
        "accounts_2020_2025.csv": accounts_df,
        "cards_2020_2025.csv": cards_df,
        "ATM_Infrastructure_2020_2025.csv": banca_parts["atm"],
        "POS_Infrastructure_2020_2025.csv": banca_parts["pos"],
        "transactions_vol_2020_2025.csv": banca_parts["transactions_vol"],
        "transactions_val_2020_2025.csv": banca_parts["transactions_val"],
        "POS_Transactions_2020_2025.csv": banca_parts["pos_transactions"],
        "Mobile_Banking_2020_2025.csv": banca_parts["mobile_banking"],
        "Internet_Banking_2020_2025.csv": banca_parts["internet_banking"],
    }
    counts: dict[str, int] = {}
    for path_str, df in outputs.items():
        out_df = _upsert_year(Path(path_str), year, df)
        counts[path_str] = len(out_df[out_df["Year"] == year])
    return counts


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

    for _, row in table.iterrows():
        name = _normalize_geo_label(row.iloc[0])
        if name is None:
            continue

        if _is_province_header(name, current_province):
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


def _extract_ime_agents_sheet(source_path: Path, sheet_name: str, year: int = 2025) -> pd.DataFrame:
    df = _read_excel_sheet(source_path, sheet_name)
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

    for _, row in table.iterrows():
        name = _normalize_geo_label(row.iloc[0])
        if name is None:
            continue

        if _is_province_header(name, current_province):
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


def _extract_ime_subscribers_demographics(source_path: Path, sheet_name: str, year: int = 2025) -> pd.DataFrame:
    df = _read_excel_sheet(source_path, sheet_name)
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

    for _, row in table.iterrows():
        name = _normalize_geo_label(row.iloc[0])
        if name is None:
            continue

        if _is_province_header(name, current_province):
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

    subscribers_sheet = _pick_sheet_name(source_path, ["subscritores das ime", "2025"])
    agents_sheet = _pick_sheet_name(source_path, ["agentes", "2025"])
    dep_sheet = _pick_sheet_name(source_path, ["depósitos ime", "2025"])
    lev_sheet = _pick_sheet_name(source_path, ["levantamentos ime", "2025"])
    trf_sheet = _pick_sheet_name(source_path, ["transferências ime", "2025"])
    pay_sheet = _pick_sheet_name(source_path, ["pagamentos ime", "2025"])

    subscribers_demo = _extract_ime_subscribers_demographics(source_path, subscribers_sheet, year=2025)
    subscribers = (
        subscribers_demo.groupby(["Year", "Month", "Province", "District"], as_index=False)["Subscribers"]
        .sum()
    )
    agents = _extract_ime_agents_sheet(source_path, agents_sheet, year=2025)
    transactions = pd.concat(
        [
            _extract_ime_volume_value_sheet(source_path, dep_sheet, "Depósitos", year=2025),
            _extract_ime_volume_value_sheet(source_path, lev_sheet, "Levantamentos", year=2025),
            _extract_ime_volume_value_sheet(source_path, trf_sheet, "Transferências", year=2025),
            _extract_ime_volume_value_sheet(source_path, pay_sheet, "Pagamentos", year=2025),
        ],
        ignore_index=True,
    )

    subscribers.to_csv(subscribers_path, index=False)
    subscribers_demo.to_csv(subscribers_demo_path, index=False)
    agents.to_csv(agents_path, index=False)
    transactions.to_csv(transactions_path, index=False)
    return subscribers, subscribers_demo, agents, transactions


def export_ime_2023_2025_csvs(
    years: tuple[int, ...] = (2023, 2024, 2025),
    subscribers_path: Path = IME_SUBSCRIBERS_2023_2025_OUTPUT,
    subscribers_demo_path: Path = IME_SUBSCRIBERS_DEMO_2023_2025_OUTPUT,
    agents_path: Path = IME_AGENTS_2023_2025_OUTPUT,
    transactions_path: Path = IME_TRANSACTIONS_2023_2025_OUTPUT,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[int, str]]:
    """Aggregate IME district datasets across available years (2023-2025)."""
    subs_parts: list[pd.DataFrame] = []
    subs_demo_parts: list[pd.DataFrame] = []
    agents_parts: list[pd.DataFrame] = []
    txn_parts: list[pd.DataFrame] = []
    skipped: dict[int, str] = {}

    for year in years:
        source_path = Path(IME_SOURCE_TEMPLATE.format(year=year))
        if not source_path.exists():
            skipped[year] = "source file not found"
            continue
        try:
            subscribers_sheet = _pick_sheet_name(source_path, ["subscritores das ime", str(year)])
            agents_sheet = _pick_sheet_name(source_path, ["agentes", str(year)])
            dep_sheet = _pick_sheet_name(source_path, ["depósitos ime", str(year)])
            lev_sheet = _pick_sheet_name(source_path, ["levantamentos ime", str(year)])
            trf_sheet = _pick_sheet_name(source_path, ["transferências ime", str(year)])
            pay_sheet = _pick_sheet_name(source_path, ["pagamentos ime", str(year)])

            subscribers_demo = _extract_ime_subscribers_demographics(source_path, subscribers_sheet, year=year)
            subscribers = (
                subscribers_demo.groupby(["Year", "Month", "Province", "District"], as_index=False)["Subscribers"]
                .sum()
            )
            agents = _extract_ime_agents_sheet(source_path, agents_sheet, year=year)
            transactions = pd.concat(
                [
                    _extract_ime_volume_value_sheet(source_path, dep_sheet, "Depósitos", year=year),
                    _extract_ime_volume_value_sheet(source_path, lev_sheet, "Levantamentos", year=year),
                    _extract_ime_volume_value_sheet(source_path, trf_sheet, "Transferências", year=year),
                    _extract_ime_volume_value_sheet(source_path, pay_sheet, "Pagamentos", year=year),
                ],
                ignore_index=True,
            )
            subs_parts.append(subscribers)
            subs_demo_parts.append(subscribers_demo)
            agents_parts.append(agents)
            txn_parts.append(transactions)
        except Exception as exc:  # noqa: BLE001
            skipped[year] = f"{type(exc).__name__}: {exc}"

    subscribers_out = pd.concat(subs_parts, ignore_index=True) if subs_parts else pd.DataFrame()
    subscribers_demo_out = pd.concat(subs_demo_parts, ignore_index=True) if subs_demo_parts else pd.DataFrame()
    agents_out = pd.concat(agents_parts, ignore_index=True) if agents_parts else pd.DataFrame()
    transactions_out = pd.concat(txn_parts, ignore_index=True) if txn_parts else pd.DataFrame()

    subscribers_out.to_csv(subscribers_path, index=False)
    subscribers_demo_out.to_csv(subscribers_demo_path, index=False)
    agents_out.to_csv(agents_path, index=False)
    transactions_out.to_csv(transactions_path, index=False)
    return subscribers_out, subscribers_demo_out, agents_out, transactions_out, skipped


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
    for _, row in table.iterrows():
        name = _normalize_geo_label(row.iloc[0])
        if name is None:
            continue

        if _is_province_header(name, current_province):
            current_province = name
            level = "Province"
            district_val = None
        else:
            level = "District"
            district_val = name

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
        df["Province"] = df["Province"].astype(str).str.strip().replace(GEO_NAME_ALIASES)
    if "District" in df.columns:
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
        "--export-ime-2023-2025",
        action="store_true",
        help="Aggregate IME district datasets across available 2023-2025 files.",
    )
    parser.add_argument(
        "--export-banking-2023",
        action="store_true",
        help="Extract banca-electronica-2023.xlsx and upsert Year=2023 into core 2020_2025 CSV outputs.",
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
        and not args.export_ime_2023_2025
        and not args.export_banking_2023
        and not args.export_bom_context
    )

    if args.export_census or run_all:
        df = export_census_csv()
        print(f"Exported {CENSUS_OUTPUT} ({len(df)} provinces)")

    if args.export_ime or run_all:
        subs, subs_demo, agents, txns = export_ime_2025_csvs()
        print(f"Exported {IME_SUBSCRIBERS_OUTPUT} ({len(subs)} rows)")
        print(f"Exported {IME_SUBSCRIBERS_DEMO_OUTPUT} ({len(subs_demo)} rows)")
        print(f"Exported {IME_AGENTS_OUTPUT} ({len(agents)} rows)")
        print(f"Exported {IME_TRANSACTIONS_OUTPUT} ({len(txns)} rows)")

    if args.export_ime_2023_2025 or run_all:
        subs, subs_demo, agents, txns, skipped = export_ime_2023_2025_csvs()
        print(f"Exported {IME_SUBSCRIBERS_2023_2025_OUTPUT} ({len(subs)} rows)")
        print(f"Exported {IME_SUBSCRIBERS_DEMO_2023_2025_OUTPUT} ({len(subs_demo)} rows)")
        print(f"Exported {IME_AGENTS_2023_2025_OUTPUT} ({len(agents)} rows)")
        print(f"Exported {IME_TRANSACTIONS_2023_2025_OUTPUT} ({len(txns)} rows)")
        if skipped:
            for year, reason in sorted(skipped.items()):
                print(f"Skipped IME year {year}: {reason}")

    if args.export_banking_2023 or run_all:
        counts = export_banking_year_into_core_csvs(BANKING_SOURCE_2023, year=2023)
        for output, nrows in counts.items():
            print(f"Upserted Year=2023 into {output} ({nrows} rows for 2023)")

    if args.export_bom_context or run_all:
        counts = export_bom_context_csvs()
        for output, nrows in counts.items():
            if nrows >= 0:
                print(f"Exported {output} ({nrows} rows)")
            else:
                print(
                    f"Skipped {output} (requires xlrd for .xls parsing; install with: pip install 'xlrd>=2.0.1')"
                )

    if args.postprocess_csvs or run_all:
        run_postprocess()
        print("Post-processed CSV outputs")


if __name__ == "__main__":
    main()
