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
        df["Age"] = pd.Categorical(df["Age"].astype(str), categories=AGE_ORDER, ordered=True)
    if "Month" in df.columns:
        df["Month"] = pd.Categorical(df["Month"], categories=MONTH_ORDER, ordered=True)
    if "Gender" in df.columns:
        df["Gender"] = pd.Categorical(df["Gender"].astype(str), categories=GENDER_ORDER, ordered=True)
    return df


def load_dataframes() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Load all dashboard datasets and return normalized dataframes plus census."""
    dataframes = {name: process_df(pd.read_csv(path)) for name, path in FILE_PATHS.items()}
    census_df = sanitize_census_df(process_df(pd.read_csv("census_2017_provinces.csv")))
    return dataframes, census_df


def last_month_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if "Month" not in df.columns or df.empty:
        return df
    return df[df["Month"] == df["Month"].max()]


def last_month_snapshot_all_years(df: pd.DataFrame) -> pd.DataFrame:
    if "Month" not in df.columns or df.empty:
        return df
    idx = df.groupby("Year")["Month"].transform("max")
    return df[df["Month"] == idx]


def normalize_atm_txn(df: pd.DataFrame) -> pd.DataFrame:
    """Fix naming inconsistencies in ATM transaction data between years."""
    df = df.copy()
    df.loc[df["Metric"] == "Transferências para", "Metric"] = "Transferências"
    df.loc[df["Sub_Metric"] == "contas bancárias", "Sub_Metric"] = "para Contas Bancárias"
    mask_tel = df["Metric"].isin(["telemóveis", "para telemóveis"])
    df.loc[mask_tel, "Sub_Metric"] = "para telemóveis"
    df.loc[mask_tel, "Metric"] = "Transferências"
    return df


def missing_years(years: list[int]) -> list[int]:
    if not years:
        return []
    return [y for y in range(min(years), max(years) + 1) if y not in years]


def sanitize_census_df(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce basic internal consistency in census aggregates."""
    df = df.copy()
    if {"Population_Total", "Population_Urban", "Population_Rural"}.issubset(df.columns):
        over_urban = df["Population_Urban"] > df["Population_Total"]
        # Keep demographic shares valid even when source merges have inconsistencies.
        df.loc[over_urban, "Population_Urban"] = df.loc[over_urban, "Population_Total"]
        df["Population_Rural"] = (df["Population_Total"] - df["Population_Urban"]).clip(lower=0)
    return df
