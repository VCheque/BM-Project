"""Opportunity scoring utilities for province-level prioritization."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


MONTH_ORDER = {
    "Janeiro": 1,
    "Fevereiro": 2,
    "Marco": 3,
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


@dataclass(frozen=True)
class OpportunityWeights:
    demand_potential: float = 35.0
    digital_momentum: float = 25.0
    monetization_signal: float = 25.0
    infrastructure_gap: float = 15.0


def _to_month_number(month_value: object) -> int | None:
    if month_value is None:
        return None
    text = str(month_value).strip()
    if text.isdigit():
        value = int(text)
        return value if 1 <= value <= 12 else None
    return MONTH_ORDER.get(text)


def _safe_minmax_to_100(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.dropna().empty:
        return pd.Series([50.0] * len(s), index=s.index, dtype=float)
    lo, hi = float(s.min()), float(s.max())
    if hi <= lo:
        return pd.Series([50.0] * len(s), index=s.index, dtype=float)
    return ((s - lo) / (hi - lo) * 100.0).clip(lower=0, upper=100)


def build_opportunity_scores(
    *,
    population_by_province: pd.DataFrame,
    accounts_snapshot: pd.DataFrame,
    atm_snapshot: pd.DataFrame,
    pos_snapshot: pd.DataFrame,
    ime_subscribers: pd.DataFrame | None,
    ime_agents: pd.DataFrame | None,
    ime_transactions: pd.DataFrame | None,
    year: int,
    weights: OpportunityWeights = OpportunityWeights(),
) -> pd.DataFrame:
    """Build a weighted province opportunity score (0-100)."""
    pop = population_by_province.groupby("Province", as_index=False)["Population"].sum()
    acc = accounts_snapshot.groupby("Province", as_index=False)["Total_Accounts"].sum()
    atm = atm_snapshot.groupby("Province", as_index=False)["ATMs_Number"].sum()
    pos = pos_snapshot.groupby("Province", as_index=False)["POSs_Number"].sum()

    base = (
        pop.merge(acc, on="Province", how="left")
        .merge(atm, on="Province", how="left")
        .merge(pos, on="Province", how="left")
    )
    for col in ["Total_Accounts", "ATMs_Number", "POSs_Number"]:
        base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0)
    base["Population"] = pd.to_numeric(base["Population"], errors="coerce").fillna(0)

    base["Accounts_Per_Capita"] = base.apply(
        lambda r: (r["Total_Accounts"] / r["Population"]) if r["Population"] > 0 else 0,
        axis=1,
    )
    base["Demand_Potential_Raw"] = (1 - base["Accounts_Per_Capita"]).clip(lower=0)

    base["Infra_per_100k"] = base.apply(
        lambda r: ((r["ATMs_Number"] + r["POSs_Number"]) / r["Population"] * 100_000)
        if r["Population"] > 0
        else 0,
        axis=1,
    )
    # Lower infrastructure density implies larger opportunity gap.
    base["Infrastructure_Gap_Raw"] = -base["Infra_per_100k"]

    # IME signals (if unavailable, neutral score is applied later by min-max helper).
    base["Digital_Momentum_Raw"] = pd.NA
    base["Monetization_Signal_Raw"] = pd.NA
    base["Agents"] = 0.0
    base["Subscribers"] = 0.0
    base["IME_Value"] = 0.0

    if ime_subscribers is not None and not ime_subscribers.empty:
        sub = ime_subscribers[ime_subscribers["Year"] == year].copy()
        if not sub.empty:
            sub["Month_Num"] = sub["Month"].map(_to_month_number)
            sub = sub.dropna(subset=["Month_Num"])
            sub_g = sub.groupby(["Province", "Month_Num"], as_index=False, observed=False)["Subscribers"].sum()
            month_first = sub_g.sort_values("Month_Num").groupby("Province", as_index=False).first()
            month_last = sub_g.sort_values("Month_Num").groupby("Province", as_index=False).last()
            momentum = month_first[["Province", "Subscribers"]].merge(
                month_last[["Province", "Subscribers"]],
                on="Province",
                suffixes=("_start", "_end"),
            )
            momentum["Digital_Momentum_Raw"] = momentum.apply(
                lambda r: ((r["Subscribers_end"] - r["Subscribers_start"]) / r["Subscribers_start"])
                if r["Subscribers_start"] > 0
                else 0,
                axis=1,
            )
            avg_sub = sub_g.groupby("Province", as_index=False)["Subscribers"].mean().rename(
                columns={"Subscribers": "Subscribers"}
            )
            momentum_map = momentum.set_index("Province")["Digital_Momentum_Raw"]
            subs_map = avg_sub.set_index("Province")["Subscribers"]
            base["Digital_Momentum_Raw"] = base["Province"].map(momentum_map)
            base["Subscribers"] = pd.to_numeric(base["Province"].map(subs_map), errors="coerce").fillna(0)

    if ime_agents is not None and not ime_agents.empty:
        ag = ime_agents[ime_agents["Year"] == year].copy()
        if not ag.empty:
            ag_sum = ag.groupby("Province", as_index=False)["Agents"].sum()
            ag_map = ag_sum.set_index("Province")["Agents"]
            base["Agents"] = pd.to_numeric(base["Province"].map(ag_map), errors="coerce").fillna(0)

    if ime_transactions is not None and not ime_transactions.empty:
        tx = ime_transactions[ime_transactions["Year"] == year].copy()
        if not tx.empty:
            tx_sum = tx.groupby("Province", as_index=False)["Value"].sum().rename(columns={"Value": "IME_Value"})
            tx_map = tx_sum.set_index("Province")["IME_Value"]
            base["IME_Value"] = pd.to_numeric(base["Province"].map(tx_map), errors="coerce").fillna(0)

    if "IME_Value" in base.columns:
        base["Monetization_Signal_Raw"] = base.apply(
            lambda r: (r["IME_Value"] / r["Subscribers"]) if r["Subscribers"] > 0 else pd.NA,
            axis=1,
        )

    base["Demand_Potential_Score"] = _safe_minmax_to_100(base["Demand_Potential_Raw"])
    base["Digital_Momentum_Score"] = _safe_minmax_to_100(base["Digital_Momentum_Raw"])
    base["Monetization_Signal_Score"] = _safe_minmax_to_100(base["Monetization_Signal_Raw"])
    base["Infrastructure_Gap_Score"] = _safe_minmax_to_100(base["Infrastructure_Gap_Raw"])

    total_weight = (
        weights.demand_potential
        + weights.digital_momentum
        + weights.monetization_signal
        + weights.infrastructure_gap
    )
    base["Opportunity_Score"] = (
        base["Demand_Potential_Score"] * weights.demand_potential
        + base["Digital_Momentum_Score"] * weights.digital_momentum
        + base["Monetization_Signal_Score"] * weights.monetization_signal
        + base["Infrastructure_Gap_Score"] * weights.infrastructure_gap
    ) / total_weight
    return base.sort_values("Opportunity_Score", ascending=False).reset_index(drop=True)


def build_opportunity_reason(df_row: pd.Series, lang: str = "PT") -> str:
    """Generate a short deterministic reason for a province rank."""
    score_cols = (
        {
            "Demand_Potential_Score": "potencial de procura (baixa penetração de contas por população elegível)",
            "Digital_Momentum_Score": "momento digital (crescimento de subscritores IME ao longo do ano)",
            "Monetization_Signal_Score": "sinal de monetização (valor transaccionado por subscritor IME)",
            "Infrastructure_Gap_Score": "lacuna de infraestrutura (menor densidade de ATM+POS por 100 mil habitantes)",
        }
        if lang == "PT"
        else {
            "Demand_Potential_Score": "demand potential (lower account penetration vs eligible population)",
            "Digital_Momentum_Score": "digital momentum (IME subscriber growth over the year)",
            "Monetization_Signal_Score": "monetization signal (transaction value per IME subscriber)",
            "Infrastructure_Gap_Score": "infrastructure gap (lower ATM+POS density per 100k population)",
        }
    )
    ranked = sorted(score_cols.items(), key=lambda kv: float(df_row.get(kv[0], 0)), reverse=True)
    top1 = ranked[0][1]
    top2 = ranked[1][1]
    if lang == "PT":
        return f"Pontuação suportada sobretudo por {top1} e {top2}."
    return f"Score mainly supported by {top1} and {top2}."
