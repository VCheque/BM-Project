"""Forecasting helpers used by the dashboard."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

STOCK_INDICATORS = {"Contas Bancárias", "Cartões Bancários", "ATMs", "POS"}
FLOW_INDICATORS = {
    "Mobile Banking",
    "Internet Banking",
    "Transações ATM (Volume)",
    "Transações ATM (Valor)",
    "Transações POS (Volume)",
    "Transações POS (Valor)",
    "Transações Mobile Banking (Volume)",
    "Transações Mobile Banking (Valor)",
    "Transações Internet Banking (Volume)",
    "Transações Internet Banking (Valor)",
}

MONTH_NUM = {
    "Janeiro": 1,
    "Fevereiro": 2,
    "Março": 3,
    "Abril": 4,
    "Maio": 5,
    "Junho": 6,
    "Julho": 7,
    "Agosto": 8,
    "Setembro": 9,
    "Outubro": 10,
    "Novembro": 11,
    "Dezembro": 12,
}


def build_monthly_series(df: pd.DataFrame, metric_col: str) -> pd.DataFrame:
    if "Month" not in df.columns:
        yearly = df.groupby("Year")[metric_col].sum().reset_index()
        yearly.columns = ["Year", "Value"]
        yearly["t"] = yearly["Year"].astype(float)
        yearly["Month_Num"] = 6
        return yearly.sort_values("t").reset_index(drop=True)

    monthly = df.groupby(["Year", "Month"], observed=False)[metric_col].sum().reset_index()
    monthly.columns = ["Year", "Month", "Value"]
    monthly["Month_Num"] = monthly["Month"].map(MONTH_NUM).astype(float)
    monthly = monthly.dropna(subset=["Month_Num", "Value"])
    monthly = monthly[monthly["Value"] > 0]
    monthly["t"] = monthly["Year"].astype(float) + (monthly["Month_Num"] - 1) / 12
    return monthly.sort_values("t").reset_index(drop=True)


def poly_forecast(monthly_series: pd.DataFrame, n_future_years: int = 5, degree: int = 2):
    if len(monthly_series) < 3:
        return None, None, None, None

    t = monthly_series[["t"]].values
    y = monthly_series["Value"].values

    poly = PolynomialFeatures(degree=degree, include_bias=False)
    t_poly = poly.fit_transform(t)

    model = LinearRegression()
    model.fit(t_poly, y)

    r2 = model.score(t_poly, y)
    y_pred_hist = model.predict(t_poly)
    residual_std = np.std(y - y_pred_hist)

    hist_df = monthly_series[["t", "Value"]].copy()
    hist_df["Tipo"] = "historic"
    hist_df["Year_Label"] = monthly_series["t"].apply(lambda x: int(x))

    last_t = monthly_series["t"].max()
    last_year = int(last_t)
    future_ts = []
    for yr_offset in range(1, n_future_years + 1):
        for m in range(12):
            future_ts.append(last_year + yr_offset + m / 12)
    future_t = np.array(future_ts).reshape(-1, 1)
    future_poly = poly.transform(future_t)
    future_vals = model.predict(future_poly).clip(min=0)

    pred_df = pd.DataFrame(
        {
            "t": future_t.flatten(),
            "Value": future_vals,
            "Tipo": "forecast",
            "Year_Label": [int(x) for x in future_t.flatten()],
        }
    )

    combined = pd.concat([hist_df, pred_df], ignore_index=True)
    combined["Upper"] = (combined["Value"] + 1.96 * residual_std).clip(lower=0)
    combined["Lower"] = (combined["Value"] - 1.96 * residual_std).clip(lower=0)

    return combined, r2, residual_std, (poly, model)


def aggregate_forecast_yearly(combined_df: pd.DataFrame, indicator_name: str, hist_label: str, pred_label: str) -> pd.DataFrame:
    if combined_df is None or combined_df.empty:
        return pd.DataFrame()

    tmp = combined_df.copy()
    tmp["Tipo"] = tmp["Tipo"].replace({"historic": hist_label, "forecast": pred_label})

    if indicator_name in STOCK_INDICATORS:
        idx = tmp.groupby("Year_Label")["t"].idxmax()
        yearly = tmp.loc[idx, ["Year_Label", "Value", "Tipo", "Upper", "Lower"]].copy()
    else:
        yearly = (
            tmp.groupby(["Year_Label", "Tipo"])
            .agg(Value=("Value", "sum"), Upper=("Upper", "sum"), Lower=("Lower", "sum"))
            .reset_index()
        )

    yearly = yearly.rename(columns={"Year_Label": "Ano", "Value": "Valor"})
    return yearly.sort_values("Ano")
