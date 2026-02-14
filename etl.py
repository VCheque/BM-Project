"""ETL entrypoint for census export and post-processing of extracted CSVs.

This script complements `ETL.ipynb` by providing repeatable, code-reviewed
steps that should live outside the dashboard runtime.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

CENSUS_OUTPUT = Path("census_2017_provinces.csv")

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
        "Population_Total": 2988355,
        "Population_Male": 1434291,
        "Population_Female": 1554064,
        "Population_Urban": 2988355,
        "Population_Rural": 0,
        "Pop_0_16": 1569000,
        "Pop_17_21": 313000,
        "Pop_22_60": 896000,
        "Pop_60_plus": 210355,
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
]


def export_census_csv(path: Path = CENSUS_OUTPUT) -> pd.DataFrame:
    df = pd.DataFrame(CENSUS_2017_ROWS)

    # Guardrails for consistency.
    df["Population_Urban"] = df[["Population_Urban", "Population_Total"]].min(axis=1)
    df["Population_Rural"] = (df["Population_Total"] - df["Population_Urban"]).clip(lower=0)

    path.write_text(df.to_csv(index=False))
    return df


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
        "--all",
        action="store_true",
        help="Run all ETL maintenance tasks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_all = args.all or (not args.export_census and not args.postprocess_csvs)

    if args.export_census or run_all:
        df = export_census_csv()
        print(f"Exported {CENSUS_OUTPUT} ({len(df)} provinces)")

    if args.postprocess_csvs or run_all:
        run_postprocess()
        print("Post-processed CSV outputs")


if __name__ == "__main__":
    main()
