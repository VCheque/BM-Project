"""Forecasting helpers used by the dashboard."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.statespace.sarimax import SARIMAX
except Exception:  # pragma: no cover
    ExponentialSmoothing = None
    SARIMAX = None


STOCK_INDICATORS = {"Contas Bancárias", "Cartões Bancários", "ATMs", "POS"}

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
    """Legacy polynomial forecast helper kept for backward compatibility."""
    if len(monthly_series) < 3:
        return None, None, None, None

    t = monthly_series["t"].to_numpy()
    y = monthly_series["Value"].values
    coeffs = np.polyfit(t, y, degree)
    y_pred_hist = np.polyval(coeffs, t).clip(min=0)
    r2 = _r2_score(y, y_pred_hist)
    residual_std = float(np.std(y - y_pred_hist))

    hist_df = monthly_series[["t", "Value"]].copy()
    hist_df["Tipo"] = "historic"
    hist_df["Year_Label"] = monthly_series["t"].astype(int)

    future_t = _future_t(float(monthly_series["t"].max()), n_future_years)
    future_vals = np.polyval(coeffs, future_t).clip(min=0)
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
    return combined, r2, residual_std, {"degree": degree, "coefficients": coeffs.tolist()}


def _future_t(last_t: float, n_future_years: int) -> np.ndarray:
    last_year = int(last_t)
    future_ts = []
    for yr_offset in range(1, n_future_years + 1):
        for m in range(12):
            future_ts.append(last_year + yr_offset + m / 12)
    return np.array(future_ts, dtype=float)


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    eps = 1e-9
    denom = np.maximum(np.abs(y_true), eps)
    return float(np.mean(np.abs((y_true - y_pred) / denom)) * 100)


def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    eps = 1e-9
    denom = np.maximum((np.abs(y_true) + np.abs(y_pred)) / 2.0, eps)
    return float(np.mean(np.abs(y_true - y_pred) / denom) * 100)


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_mean = float(np.mean(y_true))
    ss_tot = float(np.sum((y_true - y_mean) ** 2))
    if ss_tot == 0:
        return 0.0
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    return 1.0 - (ss_res / ss_tot)


def _naive_predict(train_y: np.ndarray, horizon: int) -> np.ndarray:
    return np.repeat(train_y[-1], horizon)


def _seasonal_naive_predict(train_y: np.ndarray, horizon: int, season: int = 12) -> np.ndarray:
    if len(train_y) < season:
        return _naive_predict(train_y, horizon)
    out = []
    for i in range(horizon):
        out.append(train_y[-season + (i % season)])
    return np.array(out, dtype=float)


def _fit_ets(train_y: np.ndarray):
    if ExponentialSmoothing is None:
        raise RuntimeError("statsmodels not available")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if len(train_y) >= 24:
            try:
                model = ExponentialSmoothing(
                    train_y,
                    trend="add",
                    seasonal="add",
                    seasonal_periods=12,
                    initialization_method="estimated",
                )
                return model.fit(optimized=True)
            except Exception:
                pass
        model = ExponentialSmoothing(
            train_y,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        )
        return model.fit(optimized=True)


def _fit_sarima(train_y: np.ndarray):
    if SARIMAX is None:
        raise RuntimeError("statsmodels not available")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if len(train_y) >= 24:
            try:
                model = SARIMAX(
                    train_y,
                    order=(1, 1, 1),
                    seasonal_order=(1, 1, 1, 12),
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                return model.fit(disp=False)
            except Exception:
                pass
        try:
            model = SARIMAX(
                train_y,
                order=(1, 1, 1),
                seasonal_order=(0, 0, 0, 0),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            return model.fit(disp=False)
        except Exception:
            model = SARIMAX(
                train_y,
                order=(1, 0, 0),
                seasonal_order=(0, 0, 0, 0),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            return model.fit(disp=False)


def _predict_one_step(train_y: np.ndarray, model_name: str) -> float | None:
    if len(train_y) == 0:
        return None
    if model_name == "naive":
        return float(train_y[-1])
    if model_name == "seasonal_naive":
        return float(_seasonal_naive_predict(train_y, 1, season=12)[0])
    if model_name == "ets":
        try:
            fit = _fit_ets(train_y)
            return float(np.asarray(fit.forecast(1))[0])
        except Exception:
            return None
    if model_name == "sarima":
        try:
            fit = _fit_sarima(train_y)
            return float(np.asarray(fit.forecast(1))[0])
        except Exception:
            return None
    return None


def _predict_horizon(train_y: np.ndarray, model_name: str, horizon: int) -> np.ndarray:
    if model_name == "naive":
        return _naive_predict(train_y, horizon)
    if model_name == "seasonal_naive":
        return _seasonal_naive_predict(train_y, horizon, season=12)
    if model_name == "ets":
        try:
            fit = _fit_ets(train_y)
            return np.asarray(fit.forecast(horizon), dtype=float)
        except Exception:
            return _naive_predict(train_y, horizon)
    if model_name == "sarima":
        try:
            fit = _fit_sarima(train_y)
            return np.asarray(fit.forecast(horizon), dtype=float)
        except Exception:
            return _seasonal_naive_predict(train_y, horizon, season=12)
    return _naive_predict(train_y, horizon)


def _walk_forward_metrics(y: np.ndarray, model_name: str) -> dict | None:
    n = len(y)
    if n < 8:
        return None

    eval_points = min(12, max(3, n // 4))
    split = n - eval_points
    min_train = 12 if model_name in {"seasonal_naive", "ets", "sarima"} else 6
    if split < min_train:
        split = min_train
    if split >= n - 1:
        return None

    preds = []
    actual = []
    for i in range(split, n):
        p = _predict_one_step(y[:i], model_name)
        if p is None or not np.isfinite(p):
            continue
        preds.append(max(float(p), 0.0))
        actual.append(float(y[i]))

    if len(actual) < 3:
        return None

    y_true = np.array(actual, dtype=float)
    y_pred = np.array(preds, dtype=float)
    return {
        "smape": _smape(y_true, y_pred),
        "mae": _mae(y_true, y_pred),
        "mape": _mape(y_true, y_pred),
        "n_eval": int(len(y_true)),
    }


def _historical_one_step_preds(y: np.ndarray, model_name: str) -> tuple[np.ndarray, np.ndarray]:
    n = len(y)
    pred_hist = np.full(n, np.nan, dtype=float)
    start = 12 if model_name in {"seasonal_naive", "ets", "sarima"} else 1
    start = min(start, max(1, n - 1))
    for i in range(start, n):
        p = _predict_one_step(y[:i], model_name)
        if p is None or not np.isfinite(p):
            continue
        pred_hist[i] = max(float(p), 0.0)
    valid_mask = ~np.isnan(pred_hist)
    pred_filled = np.where(valid_mask, pred_hist, y)
    return pred_filled, valid_mask


def _fit_predict_full(monthly_series: pd.DataFrame, model_name: str, n_future_years: int):
    t = monthly_series["t"].to_numpy(dtype=float)
    y = monthly_series["Value"].to_numpy(dtype=float)

    pred_hist, valid_mask = _historical_one_step_preds(y, model_name)
    if valid_mask.sum() >= 2:
        r2 = _r2_score(y[valid_mask], pred_hist[valid_mask])
        residual_std = float(np.nanstd(y[valid_mask] - pred_hist[valid_mask]))
    else:
        r2 = None
        residual_std = float(np.nanstd(y - pred_hist))

    future_t = _future_t(float(t.max()), n_future_years)
    future_vals = _predict_horizon(y, model_name, len(future_t)).clip(min=0)

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
    """Select best model via walk-forward sMAPE + MAE and return forecast output."""
    n = len(monthly_series)
    if n < 3:
        return None, None, None, None

    candidates: list[str] = ["naive"]
    if n >= 12:
        candidates.append("seasonal_naive")
    if ExponentialSmoothing is not None and n >= 12:
        candidates.append("ets")
    if SARIMAX is not None and n >= 18:
        candidates.append("sarima")

    scored: dict[str, dict] = {}
    for model_name in candidates:
        metrics = _walk_forward_metrics(monthly_series["Value"].to_numpy(dtype=float), model_name)
        if metrics is not None:
            scored[model_name] = metrics

    if not scored:
        scored["naive"] = {"smape": np.nan, "mae": np.nan, "mape": np.nan, "n_eval": 0}

    best_model = min(
        scored.keys(),
        key=lambda m: (
            float(scored[m]["smape"]) if np.isfinite(scored[m]["smape"]) else float("inf"),
            float(scored[m]["mae"]) if np.isfinite(scored[m]["mae"]) else float("inf"),
        ),
    )

    combined, r2, residual_std = _fit_predict_full(monthly_series, best_model, n_future_years)
    labels = {
        "naive": "Naive (last value)",
        "seasonal_naive": "Seasonal Naive (12)",
        "ets": "ETS",
        "sarima": "SARIMA",
    }
    selected_metrics = scored.get(best_model, {})
    meta = {
        "model": best_model,
        "model_label": labels.get(best_model, best_model),
        "holdout_smape": float(selected_metrics["smape"]) if selected_metrics.get("smape") is not None else None,
        "holdout_mae": float(selected_metrics["mae"]) if selected_metrics.get("mae") is not None else None,
        "holdout_mape": float(selected_metrics["mape"]) if selected_metrics.get("mape") is not None else None,
        "n_eval": int(selected_metrics.get("n_eval", 0)),
        "candidates": {
            m: {
                "smape": float(v.get("smape", np.nan)),
                "mae": float(v.get("mae", np.nan)),
                "mape": float(v.get("mape", np.nan)),
                "n_eval": int(v.get("n_eval", 0)),
            }
            for m, v in scored.items()
        },
        "reason": "walk_forward_selection",
        "indicator_name": indicator_name,
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
