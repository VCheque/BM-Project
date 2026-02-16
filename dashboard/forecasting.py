"""Forecasting helpers used by the dashboard."""

from __future__ import annotations

import numpy as np
import pandas as pd

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

    t = monthly_series["t"].to_numpy()
    y = monthly_series["Value"].values

    coeffs = np.polyfit(t, y, degree)
    y_pred_hist = np.polyval(coeffs, t)
    r2 = _r2_score(y, y_pred_hist)
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
    future_t = np.array(future_ts)
    future_vals = np.polyval(coeffs, future_t).clip(min=0)

    pred_df = pd.DataFrame(
        {
            "t": future_t.flatten(),
            "Value": future_vals,
            "Tipo": "forecast",
            "Year_Label": [int(x) for x in future_t],
        }
    )

    combined = pd.concat([hist_df, pred_df], ignore_index=True)
    combined["Upper"] = (combined["Value"] + 1.96 * residual_std).clip(lower=0)
    combined["Lower"] = (combined["Value"] - 1.96 * residual_std).clip(lower=0)

    return combined, r2, residual_std, {"degree": degree, "coefficients": coeffs.tolist()}


def _future_t(last_t: float, n_future_years: int) -> np.ndarray:
    last_year = int(last_t)
    future_ts = []
    for yr_offset in range(1, n_future_years + 1):
        for m in range(12):
            future_ts.append(last_year + yr_offset + m / 12)
    return np.array(future_ts)


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    eps = 1e-9
    denom = np.maximum(np.abs(y_true), eps)
    return float(np.mean(np.abs((y_true - y_pred) / denom)) * 100)


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_mean = float(np.mean(y_true))
    ss_tot = float(np.sum((y_true - y_mean) ** 2))
    if ss_tot == 0:
        return 0.0
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    return 1.0 - (ss_res / ss_tot)


def _poly_predict(train_t: np.ndarray, train_y: np.ndarray, test_t: np.ndarray, degree: int) -> np.ndarray:
    coeffs = np.polyfit(train_t, train_y, degree)
    pred = np.polyval(coeffs, test_t)
    return np.clip(pred, a_min=0, a_max=None)


def _naive_predict(train_y: np.ndarray, horizon: int) -> np.ndarray:
    return np.repeat(train_y[-1], horizon)


def _seasonal_naive_predict(train_y: np.ndarray, horizon: int, season: int = 12) -> np.ndarray:
    if len(train_y) < season:
        return _naive_predict(train_y, horizon)
    out = []
    for i in range(horizon):
        out.append(train_y[-season + (i % season)])
    return np.array(out)


def _fit_predict_full(monthly_series: pd.DataFrame, model_name: str, n_future_years: int):
    t = monthly_series["t"].to_numpy()
    y = monthly_series["Value"].to_numpy()

    if model_name == "poly2":
        pred_hist = _poly_predict(t, y, t, degree=2)
        r2 = _r2_score(y, pred_hist)
    elif model_name == "poly1":
        pred_hist = _poly_predict(t, y, t, degree=1)
        r2 = _r2_score(y, pred_hist)
    elif model_name == "seasonal_naive":
        season = 12 if len(y) >= 12 else max(1, len(y) // 2)
        pred_hist = y.copy()
        if len(y) > season:
            pred_hist[season:] = y[:-season]
        r2 = None
    else:  # naive
        pred_hist = y.copy()
        if len(y) > 1:
            pred_hist[1:] = y[:-1]
        r2 = None

    residual = y - pred_hist
    residual_std = float(np.nanstd(residual))

    future_t = _future_t(float(t.max()), n_future_years)
    if model_name == "poly2":
        future_vals = _poly_predict(t, y, future_t, degree=2)
    elif model_name == "poly1":
        future_vals = _poly_predict(t, y, future_t, degree=1)
    elif model_name == "seasonal_naive":
        future_vals = _seasonal_naive_predict(y, len(future_t), season=12)
    else:
        future_vals = _naive_predict(y, len(future_t))
    future_vals = np.clip(future_vals, a_min=0, a_max=None)

    hist_df = monthly_series[["t", "Value"]].copy()
    hist_df["Tipo"] = "historic"
    hist_df["Year_Label"] = hist_df["t"].astype(int)
    pred_df = pd.DataFrame(
        {
            "t": future_t,
            "Value": future_vals,
            "Tipo": "forecast",
            "Year_Label": future_t.astype(int),
        }
    )
    combined = pd.concat([hist_df, pred_df], ignore_index=True)
    combined["Upper"] = (combined["Value"] + 1.96 * residual_std).clip(lower=0)
    combined["Lower"] = (combined["Value"] - 1.96 * residual_std).clip(lower=0)
    return combined, r2, residual_std


def select_best_forecast_model(monthly_series: pd.DataFrame, n_future_years: int, indicator_name: str):
    """Select the best forecasting model using holdout MAPE and return forecast output.

    Candidate set:
    - `naive`: last observed value
    - `seasonal_naive`: repeats last seasonal pattern (12)
    - `poly1`: linear trend
    - `poly2`: quadratic trend
    """
    n = len(monthly_series)
    if n < 3:
        return None, None, None, None

    # Conservative guardrail for stock indicators with sparse annual points.
    if indicator_name in STOCK_INDICATORS and n <= 6:
        combined, r2, residual_std = _fit_predict_full(monthly_series, "poly1", n_future_years)
        meta = {
            "model": "poly1",
            "model_label": "Linear trend (poly1)",
            "holdout_mape": None,
            "candidates": {},
            "reason": "sparse_stock_series",
        }
        return combined, r2, residual_std, meta

    holdout = 12 if n >= 24 else max(3, min(6, n // 3))
    split = n - holdout
    train = monthly_series.iloc[:split].copy()
    test = monthly_series.iloc[split:].copy()

    t_train = train["t"].to_numpy()
    y_train = train["Value"].to_numpy()
    t_test = test["t"].to_numpy()
    y_test = test["Value"].to_numpy()

    candidates: dict[str, float] = {}
    candidates["naive"] = _mape(y_test, _naive_predict(y_train, len(y_test)))
    if len(y_train) >= 12:
        candidates["seasonal_naive"] = _mape(y_test, _seasonal_naive_predict(y_train, len(y_test), season=12))
    if len(y_train) >= 6:
        candidates["poly1"] = _mape(y_test, _poly_predict(t_train, y_train, t_test, degree=1))
    if len(y_train) >= 8:
        candidates["poly2"] = _mape(y_test, _poly_predict(t_train, y_train, t_test, degree=2))

    best_model = min(candidates, key=candidates.get)
    combined, r2, residual_std = _fit_predict_full(monthly_series, best_model, n_future_years)
    labels = {
        "naive": "Naive (last value)",
        "seasonal_naive": "Seasonal Naive (12)",
        "poly1": "Linear trend (poly1)",
        "poly2": "Quadratic trend (poly2)",
    }
    meta = {
        "model": best_model,
        "model_label": labels[best_model],
        "holdout_mape": float(candidates[best_model]),
        "candidates": {k: float(v) for k, v in candidates.items()},
        "reason": "holdout_selection",
    }
    return combined, r2, residual_std, meta


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
