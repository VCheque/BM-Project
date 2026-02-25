"""Data loading and normalization helpers for the dashboard."""

from __future__ import annotations

import pandas as pd


FILE_PATHS = {
    "accounts": "accounts_2020_2025.csv",
    "cards": "cards_2020_2025.csv",
    "atm": "ATM_Infrastructure_2020_2025.csv",
    "transactions_vol": "transactions_vol_2020_2025.csv",
    "pos": "POS_Infrastructure_2020_2025.csv",
    "transactions_val": "transactions_val_2020_2025.csv",
    "mobile_banking": "Mobile_Banking_2020_2025.csv",
    "internet_banking": "Internet_Banking_2020_2025.csv",
    "pos_transactions": "POS_Transactions_2020_2025.csv",
}

OPTIONAL_FILE_PATHS = {
    "ime_subscribers_district": [
        "IME_Subscribers_District_2023_2025.csv",
        "IME_Subscribers_District_2025.csv",
    ],
    "ime_subscribers_district_demo": [
        "IME_Subscribers_District_Demographics_2023_2025.csv",
        "IME_Subscribers_District_Demographics_2025.csv",
    ],
    "ime_agents_district": [
        "IME_Agents_District_2023_2025.csv",
        "IME_Agents_District_2025.csv",
    ],
    "ime_transactions_district": [
        "IME_Transactions_District_2023_2025.csv",
        "IME_Transactions_District_2025.csv",
    ],
    "access_points_district": "Access_Points_District_2025Q3.csv",
    "fi_indicators_2020_2025q3": "Financial_Inclusion_Indicators_2020_2025Q3.csv",
    "sectoral_growth_2020_2025": "Sectoral_Growth_Rates_2020_2025.csv",
    "gdp_expenditure_variation_2020_2025": "GDP_Expenditure_Annual_Variation_2020_2025.csv",
}

REGIONS = {
    "Zona Norte": ["Cabo Delgado", "Niassa", "Nampula"],
    "Zona Centro": ["Zambézia", "Sofala", "Tete", "Manica"],
    "Zona Sul": ["Inhambane", "Gaza", "Província de Maputo"],
}

AGE_ORDER = ["0-16", "17-21", "22-60", "+60"]
MONTH_ORDER = [
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
DECEMBER_LABEL = "Dezembro"
GENDER_ORDER = ["Mulheres", "Homens", "Outros"]


def _drop_unnamed_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if not str(c).startswith("Unnamed:")]
    return df[cols].copy()


def process_df(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize each DataFrame for consistent filtering and plotting."""
    df = _drop_unnamed_columns(df)
    num_cols = df.select_dtypes(include=["number"]).columns
    df[num_cols] = df[num_cols].clip(lower=0)

    if "Province" in df.columns:
        df["Province"] = df["Province"].fillna("Não Definido").astype(str)
        df["Province"] = df["Province"].replace({"Cidade de Maputo": "Província de Maputo"})
        df["Region"] = df["Province"].map({p: r for r, ps in REGIONS.items() for p in ps})

    if "District" in df.columns:
        df["District"] = df["District"].fillna("Não Definido").astype(str).str.strip()
        df["District"] = df["District"].replace(
            {
                "Cidade de de Maputo": "Cidade de Maputo",
                "Cabo-Delgado": "Cabo Delgado",
            }
        )
        if "Province" in df.columns:
            maputo_city_mask = (df["Province"] == "Província de Maputo") & (df["District"] == "Maputo")
            df.loc[maputo_city_mask, "District"] = "Cidade de Maputo"

    if "Age" in df.columns:
        age_raw = df["Age"].astype(str).str.strip()
        age_norm = age_raw.replace(
            {
                "0 a 16": "0-16",
                "17 a 21": "17-21",
                "22 a 60": "22-60",
                "60+": "+60",
                "Mais de 60": "+60",
                "mais de 60": "+60",
            }
        )
        df["Age"] = pd.Categorical(age_norm, categories=AGE_ORDER, ordered=True)
    if "Month" in df.columns:
        df["Month"] = pd.Categorical(df["Month"], categories=MONTH_ORDER, ordered=True)
    if "Gender" in df.columns:
        df["Gender"] = pd.Categorical(df["Gender"].astype(str), categories=GENDER_ORDER, ordered=True)
    return df


def load_dataframes() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Load all dashboard datasets and return normalized dataframes plus census."""
    missing = [path for path in FILE_PATHS.values() if not pd.io.common.file_exists(path)]
    if not pd.io.common.file_exists("census_2017_provinces.csv"):
        missing.append("census_2017_provinces.csv")
    if missing:
        raise FileNotFoundError(
            "Missing required data file(s): "
            + ", ".join(sorted(missing))
            + ". Ensure these CSV files are committed and deployed with the app."
        )
    dataframes = {name: process_df(pd.read_csv(path)) for name, path in FILE_PATHS.items()}
    for name, path in OPTIONAL_FILE_PATHS.items():
        if isinstance(path, list):
            selected = next((p for p in path if pd.io.common.file_exists(p)), None)
            if selected is not None:
                dataframes[name] = process_df(pd.read_csv(selected))
        elif pd.io.common.file_exists(path):
            dataframes[name] = process_df(pd.read_csv(path))
    census_df = sanitize_census_df(process_df(pd.read_csv("census_2017_provinces.csv")))
    return dataframes, census_df


def last_month_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Return strict December snapshot for stock indicators."""
    if "Month" not in df.columns or df.empty:
        return df
    return df[df["Month"].astype(str) == DECEMBER_LABEL].copy()


def last_month_snapshot_all_years(df: pd.DataFrame) -> pd.DataFrame:
    """Return strict December rows across years for stock indicator trends."""
    if "Month" not in df.columns or df.empty:
        return df
    return df[df["Month"].astype(str) == DECEMBER_LABEL].copy()


def normalize_atm_txn(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize ATM transaction naming to a consistent taxonomy across years."""
    df = df.copy()
    if not {"Metric", "Sub_Metric"}.issubset(df.columns):
        return df

    metric_raw = df["Metric"].fillna("").astype(str).str.strip()
    sub_raw = df["Sub_Metric"].fillna("").astype(str).str.strip()
    metric_cf = metric_raw.str.casefold()
    sub_cf = sub_raw.str.casefold()
    combined = metric_cf + " " + sub_cf
    mobile_mask = combined.str.contains(r"telemov|telemóv", na=False)

    transfer_mask = (
        combined.str.contains("transfer", na=False)
        | metric_cf.isin(["telemóveis", "telemoveis", "para telemóveis", "para telemoveis"])
    )
    levant_mask = combined.str.contains("levant", na=False)
    payment_mask = combined.str.contains("pagament", na=False)

    transfer_to_mobile = transfer_mask & mobile_mask
    transfer_to_account = transfer_mask & combined.str.contains("conta", na=False)
    levant_from_mobile = levant_mask & mobile_mask & combined.str.contains("fundo", na=False)
    levant_cards = levant_mask & combined.str.contains("cart", na=False)

    df.loc[transfer_mask, "Metric"] = "Transferências"
    df.loc[transfer_to_mobile, "Sub_Metric"] = "para telemóveis"
    df.loc[transfer_to_account, "Sub_Metric"] = "para Contas Bancárias"

    df.loc[levant_mask, "Metric"] = "Levantamentos"
    df.loc[levant_from_mobile, "Sub_Metric"] = "de fundos depositados em telemóveis"
    df.loc[levant_cards, "Sub_Metric"] = "com cartões bancários"

    df.loc[payment_mask, "Metric"] = "Pagamentos de Serviços"
    df.loc[payment_mask, "Sub_Metric"] = pd.NA

    df["Metric"] = df["Metric"].astype(str).str.strip()
    df["Sub_Metric"] = df["Sub_Metric"].replace("", pd.NA)
    return df


def missing_years(years: list[int]) -> list[int]:
    if not years:
        return []
    return [y for y in range(min(years), max(years) + 1) if y not in years]


def sanitize_census_df(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce basic internal consistency in census aggregates."""
    df = df.copy()
    if "Province" in df.columns and df["Province"].duplicated().any():
        weighted_pct_cols = [c for c in ["Growth_Rate_Pct", "Phone_Ownership_Pct", "Internet_Usage_Pct"] if c in df.columns]
        sum_cols = [
            c
            for c in [
                "Population_Total",
                "Population_Male",
                "Population_Female",
                "Population_Urban",
                "Population_Rural",
                "Population_15plus_2017",
                "Population_10_14_2017",
                "Population_15_19_2017",
                "Pop_0_16",
                "Pop_17_21",
                "Pop_22_60",
                "Pop_60_plus",
            ]
            if c in df.columns
        ]

        def _agg_group(g: pd.DataFrame) -> pd.Series:
            out: dict[str, float | str] = {"Province": g["Province"].iloc[0]}
            pop = pd.to_numeric(g.get("Population_Total", 0), errors="coerce").fillna(0)
            pop_sum = float(pop.sum())
            for col in sum_cols:
                out[col] = float(pd.to_numeric(g[col], errors="coerce").fillna(0).sum())
            for col in weighted_pct_cols:
                vals = pd.to_numeric(g[col], errors="coerce").fillna(0)
                if pop_sum > 0:
                    out[col] = float((vals * pop).sum() / pop_sum)
                else:
                    out[col] = float(vals.mean()) if not vals.empty else 0.0
            return pd.Series(out)

        df = df.groupby("Province", as_index=False).apply(_agg_group).reset_index(drop=True)

    if {"Population_Total", "Population_Urban", "Population_Rural"}.issubset(df.columns):
        over_urban = df["Population_Urban"] > df["Population_Total"]
        # Keep demographic shares valid even when source merges have inconsistencies.
        df.loc[over_urban, "Population_Urban"] = df.loc[over_urban, "Population_Total"]
        df["Population_Rural"] = (df["Population_Total"] - df["Population_Urban"]).clip(lower=0)
    for col in ["Population_15plus_2017", "Population_10_14_2017", "Population_15_19_2017"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).clip(lower=0)
    return df
