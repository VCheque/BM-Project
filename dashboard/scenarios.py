"""Scenario utilities for lightweight planning ranges."""

from __future__ import annotations

import pandas as pd

from dashboard.forecasting import (
    aggregate_forecast_yearly,
    build_monthly_series,
    select_best_forecast_model,
)


SCENARIO_MULTIPLIERS = {
    "conservative": 0.75,
    "base": 1.00,
    "accelerated": 1.25,
}


def build_indicator_monthly_series(
    indicator_id: str,
    *,
    accounts_df: pd.DataFrame,
    mobile_df: pd.DataFrame,
    internet_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return monthly series with columns Year, Month, Value, t."""
    if indicator_id == "accounts":
        return build_monthly_series(accounts_df, "Total_Accounts")

    if indicator_id == "mobile_tx_value":
        src = mobile_df[mobile_df["Metric"].astype(str).str.contains("Valor", case=False, na=False)]
        return build_monthly_series(src, "Value")

    # digital_tx_volume = mobile volume + internet volume
    m = mobile_df[mobile_df["Metric"].astype(str).str.contains("Volume", case=False, na=False)]
    n = internet_df[internet_df["Metric"].astype(str).str.contains("Volume", case=False, na=False)]
    both = pd.concat([m[["Year", "Month", "Value"]], n[["Year", "Month", "Value"]]], ignore_index=True)
    return build_monthly_series(both, "Value")


def build_baseline_forecast_yearly(
    monthly_series: pd.DataFrame,
    *,
    indicator_name: str,
    horizon_years: int,
    hist_label: str,
    pred_label: str,
) -> tuple[pd.DataFrame, dict]:
    if len(monthly_series) < 3:
        return pd.DataFrame(), {}
    combined, r2, _, meta = select_best_forecast_model(
        monthly_series, n_future_years=horizon_years, indicator_name=indicator_name
    )
    if combined is None:
        return pd.DataFrame(), {}
    yearly = aggregate_forecast_yearly(combined, indicator_name, hist_label, pred_label)
    if yearly.empty:
        return pd.DataFrame(), {}
    model_meta = {
        "r2": r2,
        "model_label": meta.get("model_label"),
        "holdout_smape": meta.get("holdout_smape"),
        "holdout_mae": meta.get("holdout_mae"),
        "holdout_mape": meta.get("holdout_mape"),
    }
    return yearly, model_meta


def scenario_from_baseline(
    yearly_fc: pd.DataFrame,
    *,
    hist_label: str,
    pred_label: str,
    multiplier: float,
    scenario_name: str,
) -> pd.DataFrame:
    """Convert baseline growth path into a scenario path by scaling annual growth."""
    hist = yearly_fc[yearly_fc["Tipo"] == hist_label].sort_values("Ano")
    pred = yearly_fc[yearly_fc["Tipo"] == pred_label].sort_values("Ano")
    if hist.empty or pred.empty:
        return pd.DataFrame(columns=["Ano", "Cenario", "Valor"])

    current = float(hist.iloc[-1]["Valor"])
    out_rows: list[dict] = []
    last = current
    for _, row in pred.iterrows():
        baseline = float(row["Valor"])
        growth = ((baseline - last) / last) if last > 0 else 0.0
        adjusted_growth = growth * multiplier
        scen_value = max(0.0, last * (1.0 + adjusted_growth))
        out_rows.append({"Ano": int(row["Ano"]), "Cenario": scenario_name, "Valor": scen_value})
        last = baseline
    return pd.DataFrame(out_rows)


def summarize_scenario(df: pd.DataFrame, start_value: float) -> tuple[float, float]:
    """Return end value and average annual % change."""
    if df.empty:
        return 0.0, 0.0
    end_value = float(df.sort_values("Ano").iloc[-1]["Valor"])
    years = len(df)
    if start_value > 0 and years > 0:
        avg_annual_pct = ((end_value / start_value) ** (1 / years) - 1) * 100
    else:
        avg_annual_pct = 0.0
    return end_value, avg_annual_pct
