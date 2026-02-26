"""
Mozambique Electronic Banking and Mobile Wallet Dashboard
=========================================================
Interactive Streamlit dashboard for visualising electronic banking data
from the Banco de Moçambique (Central Bank of Mozambique).

Data covers 2020-2025 and includes: bank accounts, cards, ATM/POS infrastructure,
ATM/POS/Mobile/Internet transactions, and digital channel subscriptions.

Census 2017 data (IV Recenseamento Geral da População e Habitação) from the
Instituto Nacional de Estatística (INE) is used to compute per-capita financial
inclusion indicators.

The ETL pipeline (ETL.ipynb) extracts data from multi-sheet Excel files with
4-level merged-cell headers and outputs 9 CSV files consumed here.

Author: Valter Cheque · valtercheque@gmail.com
"""

import math

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard.data_utils import (
    REGIONS,
    last_month_snapshot,
    last_month_snapshot_all_years,
    load_dataframes,
    missing_years,
    normalize_atm_txn,
)
from dashboard.forecasting import (
    aggregate_forecast_yearly,
    build_monthly_series,
    select_best_forecast_model,
)
from dashboard.opportunity import OpportunityWeights, build_opportunity_reason, build_opportunity_scores
from dashboard.scenarios import (
    SCENARIO_MULTIPLIERS,
    build_baseline_forecast_yearly,
    build_indicator_monthly_series,
    scenario_from_baseline,
    summarize_scenario,
)
from dashboard.translations import translate

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Mozambique Electronic Banking and Mobile Wallet Dashboard", layout="wide")

# ── Language toggle (PT default, EN available) ──────────────────────────────
if "lang" not in st.session_state:
    st.session_state.lang = "PT"

def T(key):
    """Return translated string for the current language."""
    return translate(st.session_state.lang, key)


def tab_story(key: str) -> str:
    stories = {
        "demo": {
            "PT": "História: contexto populacional e onde a inclusão bancária ainda está abaixo do potencial.",
            "EN": "Story: population context and where banking inclusion is still below potential.",
        },
        "overview": {
            "PT": "História: fotografia do sistema financeiro no ano seleccionado e variação face ao ano anterior.",
            "EN": "Story: snapshot of the financial system in the selected year and change vs previous year.",
        },
        "ime": {
            "PT": "História: profundidade de uso das carteiras móveis por território e tipo de operação.",
            "EN": "Story: mobile-wallet usage depth by geography and transaction type.",
        },
        "products": {
            "PT": "História: como contas e cartões evoluem e como se distribuem por perfil e geografia.",
            "EN": "Story: how accounts and cards evolve and how they are distributed by profile and geography.",
        },
        "infra": {
            "PT": "História: capacidade física (ATM/POS) para suportar inclusão e uso transacional.",
            "EN": "Story: physical capacity (ATM/POS) to support inclusion and transactional usage.",
        },
        "usage": {
            "PT": "História: comportamento digital e de transacções, em volume e valor.",
            "EN": "Story: digital and transaction behavior, in both volume and value.",
        },
        "trends": {
            "PT": "História: trajetória histórica dos principais indicadores e aceleração/desaceleração.",
            "EN": "Story: historical trajectory of key indicators and acceleration/deceleration.",
        },
        "heatmap": {
            "PT": "História: leitura rápida de concentração e crescimento por província ao longo do tempo.",
            "EN": "Story: quick read of concentration and growth by province over time.",
        },
        "forecast": {
            "PT": "História: projecções de continuidade de tendência e simulação de cenários alternativos.",
            "EN": "Story: trend-continuation forecasts and alternative scenario simulation.",
        },
        "decision": {
            "PT": "História: síntese final com prioridades territoriais, cenários e enquadramento para diferentes públicos.",
            "EN": "Story: final synthesis with territorial priorities, scenarios, and audience framing.",
        },
    }
    return stories[key]["PT" if st.session_state.lang == "PT" else "EN"]


def single_choice_toggle(label: str, options: list[str], key: str) -> str:
    """Render a compact single-choice toggle with graceful fallback."""
    if hasattr(st, "segmented_control"):
        try:
            value = st.segmented_control(
                label,
                options=options,
                default=options[0],
                selection_mode="single",
                key=key,
            )
            return value or options[0]
        except TypeError:
            # Compatibility with older Streamlit signatures.
            value = st.segmented_control(label, options=options, default=options[0], key=key)
            return value or options[0]
    return st.radio(label, options, horizontal=True, key=key)


def metric_with_help(
    target,
    label: str,
    value,
    *,
    delta=None,
    help_pt: str | None = None,
    help_en: str | None = None,
) -> None:
    """Render metric with localized help tooltip and fallback caption."""
    help_text = help_pt if st.session_state.lang == "PT" else help_en
    if help_text:
        try:
            target.metric(label, value, delta=delta, help=help_text)
            return
        except TypeError:
            target.metric(label, value, delta=delta)
            if hasattr(target, "caption"):
                target.caption(f"ℹ️ {help_text}")
            return
    target.metric(label, value, delta=delta)


def format_compact(value: float) -> str:
    """Compact number formatting (K/M/B) for KPI readability."""
    v = float(value)
    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if abs_v >= 1_000:
        return f"{v / 1_000:.2f}K"
    return f"{v:,.0f}"


def _norm_key(text: object) -> str:
    """Normalize labels for robust equality checks."""
    return " ".join(str(text).strip().casefold().replace("-", " ").split())


MONTH_RANK = {
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


MONTH_NAME_BY_NUM = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

MONTH_NAME_BY_NUM_EN = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

MONTH_NUM_FROM_LABEL = {name: num for num, name in MONTH_NAME_BY_NUM.items()}
MONTH_NUM_FROM_LABEL.update({name: num for num, name in MONTH_NAME_BY_NUM_EN.items()})


def month_to_num(month_label: object) -> float:
    """Return month number for PT/EN month labels."""
    if pd.isna(month_label):
        return float("nan")
    return float(MONTH_NUM_FROM_LABEL.get(str(month_label), float("nan")))


def localize_month(month_label: object) -> str:
    """Translate month label according to current app language."""
    month_num = month_to_num(month_label)
    if pd.isna(month_num):
        return str(month_label)
    month_num_int = int(month_num)
    if st.session_state.lang == "EN":
        return MONTH_NAME_BY_NUM_EN[month_num_int]
    return MONTH_NAME_BY_NUM[month_num_int]


def localize_month_df(df: pd.DataFrame, source_col: str = "Month", target_col: str = "Month_Display") -> pd.DataFrame:
    """Create localized month labels plus numeric ordering helper."""
    if source_col not in df.columns:
        return df.copy()
    out = df.copy()
    out["_Month_Num"] = out[source_col].apply(month_to_num)
    out[target_col] = out[source_col].apply(localize_month)
    out = out.sort_values("_Month_Num")
    return out


def t_to_period_label(t_value: float) -> str:
    """Convert decimal year axis to month-year label."""
    year = int(float(t_value))
    month_num = int(round((float(t_value) - year) * 12)) + 1
    month_num = max(1, min(12, month_num))
    month_name = MONTH_NAME_BY_NUM_EN[month_num] if st.session_state.lang == "EN" else MONTH_NAME_BY_NUM[month_num]
    return f"{month_name} {year}"


def plot_chart(fig, **kwargs):
    """Render Plotly chart with clean axis titles for line/bar visuals."""
    trace_types = {getattr(trace, "type", "") for trace in getattr(fig, "data", [])}
    if trace_types.intersection({"bar", "scatter"}):
        fig.update_layout(xaxis_title=None, yaxis_title=None)
    if "use_container_width" not in kwargs:
        kwargs["use_container_width"] = True
    st.plotly_chart(fig, **kwargs)


def clean_ime_district_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove province-level artifacts from Mobile Wallet district files."""
    if df.empty or not {"Province", "District"}.issubset(df.columns):
        return df
    out = df.copy()
    valid_same_name_districts = {"Manica", "Cidade de Maputo"}
    province_name_norms = {_norm_key(p) for provs in REGIONS.values() for p in provs}
    prov_eq_dist = out.apply(
        lambda r: _norm_key(r["District"]) == _norm_key(r["Province"]),
        axis=1,
    )
    district_is_province_name = out["District"].apply(lambda d: _norm_key(d) in province_name_norms)
    allowed_same_name = out["District"].astype(str).isin(valid_same_name_districts)
    # Drop rows where district field carries province-level labels (artifact), except known valid names.
    bad_rows = (prov_eq_dist | district_is_province_name) & ~allowed_same_name
    out = out.loc[~bad_rows].copy()
    return out


# ── Data loading (cached so Streamlit doesn't re-read CSVs on every rerun) ──
CACHE_VERSION = "2026-02-17-etl-2023-and-ime-multiyear-v5"


@st.cache_data
def load_data(cache_version: str = CACHE_VERSION):
    """Load all CSV datasets and census data (normalized)."""
    return load_dataframes()


@st.cache_data
def load_census_districts(path: str = "census_2017_districts.csv") -> pd.DataFrame:
    """Load district-level census denominators used for district IME ratios."""
    if not pd.io.common.file_exists(path):
        return pd.DataFrame(columns=["Province", "District", "Pop_Total_2017", "Pop_15plus_2017"])
    ddf = pd.read_csv(path)
    required = {"Province", "District", "Pop_Total_2017", "Pop_15plus_2017"}
    if not required.issubset(ddf.columns):
        return pd.DataFrame(columns=["Province", "District", "Pop_Total_2017", "Pop_15plus_2017"])
    ddf = ddf[list(required)].copy()
    ddf["Province"] = ddf["Province"].astype(str).str.strip().replace({"Cidade de Maputo": "Província de Maputo"})
    ddf["District"] = ddf["District"].astype(str).str.strip()
    ddf["Pop_Total_2017"] = pd.to_numeric(ddf["Pop_Total_2017"], errors="coerce").fillna(0.0)
    ddf["Pop_15plus_2017"] = pd.to_numeric(ddf["Pop_15plus_2017"], errors="coerce").fillna(0.0)
    ddf = ddf[(ddf["Pop_Total_2017"] > 0) & (ddf["Pop_15plus_2017"] > 0)].copy()
    return ddf


# Unpack into friendly short names used throughout the dashboard
dataframes, census_df = load_data()
census_district_df = load_census_districts()
if not census_district_df.empty:
    census_district_df["_Province_Norm"] = census_district_df["Province"].astype(str).apply(_norm_key)
    census_district_df["_District_Norm"] = census_district_df["District"].astype(str).apply(_norm_key)
regions_map = REGIONS
acc_df, card_df, atm_df, vol_df, pos_df, val_df, mob_df, net_df, pos_txn_df = (
    dataframes["accounts"], dataframes["cards"], dataframes["atm"],
    dataframes["transactions_vol"], dataframes["pos"],
    dataframes["transactions_val"], dataframes["mobile_banking"],
    dataframes["internet_banking"], dataframes["pos_transactions"]
)
ime_sub_df = clean_ime_district_rows(dataframes.get("ime_subscribers_district", pd.DataFrame()))
ime_sub_demo_df = clean_ime_district_rows(dataframes.get("ime_subscribers_district_demo", pd.DataFrame()))
ime_agents_df = clean_ime_district_rows(dataframes.get("ime_agents_district", pd.DataFrame()))
ime_txn_district_df = clean_ime_district_rows(dataframes.get("ime_transactions_district", pd.DataFrame()))
access_points_df = dataframes.get("access_points_district", pd.DataFrame())
fi_indicators_df = dataframes.get("fi_indicators_2020_2025q3", pd.DataFrame())

INCM_SOURCE_TELECOM_URL = "https://acervo.incm.gov.mz/#/public/telecom"
BOM_SOURCE_STATS_URL = "https://www.bancomoc.mz/pt/areas-de-actuacao/estatisticas/dominios-e-indicadores-estatisticos/"
INCM_MOBILE_SUBSCRIBERS_Q2_2025 = pd.DataFrame(
    [
        {"Province": "Cabo Delgado", "Mobile_Subscribers": 281_349},
        {"Province": "Gaza", "Mobile_Subscribers": 311_521},
        {"Province": "Inhambane", "Mobile_Subscribers": 388_663},
        {"Province": "Manica", "Mobile_Subscribers": 260_848},
        # Harmonized to app geography: Maputo Cidade + Maputo Província.
        {"Province": "Província de Maputo", "Mobile_Subscribers": 1_724_294},
        {"Province": "Nampula", "Mobile_Subscribers": 624_051},
        {"Province": "Niassa", "Mobile_Subscribers": 136_983},
        {"Province": "Sofala", "Mobile_Subscribers": 469_984},
        {"Province": "Tete", "Mobile_Subscribers": 344_432},
        {"Province": "Zambézia", "Mobile_Subscribers": 471_814},
    ]
)


def validate_required_series() -> list[str]:
    """Validate critical series so missing data does not silently produce empty charts."""
    errors: list[str] = []
    if census_district_df.empty:
        errors.append("Missing or invalid census_2017_districts.csv (required for district denominator logic).")

    expected_years = set(pd.to_numeric(acc_df.get("Year", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist())
    if not expected_years:
        errors.append("Accounts dataset has no valid Year values.")
        return errors

    def _check_year_coverage(df: pd.DataFrame, label: str) -> None:
        years = set(pd.to_numeric(df.get("Year", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist())
        missing = sorted(expected_years - years)
        if missing:
            errors.append(f"{label} is missing years: {', '.join(map(str, missing))}.")

    mb_val = mob_df[
        mob_df["Metric"].astype(str).str.contains(
            r"Valor das transferências efectuadas para .*telemóveis",
            case=False,
            na=False,
            regex=True,
        )
    ].copy()
    mb_vol = mob_df[
        mob_df["Metric"].astype(str).str.contains(
            r"Volume das transferências efectuadas para .*telemóveis",
            case=False,
            na=False,
            regex=True,
        )
    ].copy()
    if mb_val.empty:
        errors.append("Mobile Banking transfer-to-mobile value series is missing.")
    else:
        _check_year_coverage(mb_val, "Mobile Banking transfer-to-mobile value series")
    if mb_vol.empty:
        errors.append("Mobile Banking transfer-to-mobile volume series is missing.")
    else:
        _check_year_coverage(mb_vol, "Mobile Banking transfer-to-mobile volume series")

    atm_val_norm = normalize_atm_txn(val_df)
    atm_vol_norm = normalize_atm_txn(vol_df)
    atm_withdraw_val = atm_val_norm[
        atm_val_norm["Metric"].astype(str).str.contains("levant", case=False, na=False)
        & atm_val_norm["Sub_Metric"].astype(str).str.contains("fundos depositados em telemóveis", case=False, na=False)
    ].copy()
    atm_withdraw_vol = atm_vol_norm[
        atm_vol_norm["Metric"].astype(str).str.contains("levant", case=False, na=False)
        & atm_vol_norm["Sub_Metric"].astype(str).str.contains("fundos depositados em telemóveis", case=False, na=False)
    ].copy()
    atm_transfer_val = atm_val_norm[
        atm_val_norm["Metric"].astype(str).str.contains("transfer", case=False, na=False)
        & atm_val_norm["Sub_Metric"].astype(str).str.contains("telem", case=False, na=False)
    ].copy()
    atm_transfer_vol = atm_vol_norm[
        atm_vol_norm["Metric"].astype(str).str.contains("transfer", case=False, na=False)
        & atm_vol_norm["Sub_Metric"].astype(str).str.contains("telem", case=False, na=False)
    ].copy()
    if atm_withdraw_val.empty:
        errors.append("ATM withdrawals-from-mobile-wallet value series is missing.")
    else:
        _check_year_coverage(atm_withdraw_val, "ATM withdrawals-from-mobile-wallet value series")
    if atm_withdraw_vol.empty:
        errors.append("ATM withdrawals-from-mobile-wallet volume series is missing.")
    else:
        _check_year_coverage(atm_withdraw_vol, "ATM withdrawals-from-mobile-wallet volume series")
    if atm_transfer_val.empty:
        errors.append("ATM transfer-to-mobile value series is missing.")
    else:
        _check_year_coverage(atm_transfer_val, "ATM transfer-to-mobile value series")
    if atm_transfer_vol.empty:
        errors.append("ATM transfer-to-mobile volume series is missing.")
    else:
        _check_year_coverage(atm_transfer_vol, "ATM transfer-to-mobile volume series")
    return errors


contract_errors = validate_required_series()
if contract_errors:
    if st.session_state.lang == "PT":
        st.error("Falha de validação de dados: séries obrigatórias ausentes/incompletas. Corrigir os ficheiros antes de usar o dashboard.")
    else:
        st.error("Data validation failed: required series are missing/incomplete. Fix the files before using the dashboard.")
    for err in contract_errors:
        st.write(f"- {err}")
    st.stop()

# ── Sidebar: language toggle + global filters ─────────────────────────────
lang_col1, lang_col2 = st.sidebar.columns(2)
with lang_col1:
    if st.button("🇲🇿 PT", use_container_width=True,
                 type="primary" if st.session_state.lang == "PT" else "secondary"):
        st.session_state.lang = "PT"
        st.rerun()
with lang_col2:
    if st.button("🇬🇧 EN", use_container_width=True,
                 type="primary" if st.session_state.lang == "EN" else "secondary"):
        st.session_state.lang = "EN"
        st.rerun()

st.sidebar.title(T("sidebar_title"))
st.sidebar.caption(T("sidebar_caption"))
all_years = sorted(acc_df['Year'].unique(), reverse=True)
year_gaps = missing_years(sorted(all_years))
if year_gaps:
    gap_list = ", ".join(map(str, year_gaps))
    msg_pt = f"Série temporal com lacuna(s): {gap_list}."
    msg_en = f"Time series has missing year(s): {gap_list}."
    st.sidebar.warning(msg_pt if st.session_state.lang == "PT" else msg_en)
selected_year = st.sidebar.selectbox(T("year"), all_years, help=T("help_year"))
denominator_options = (
    [
        "Population 15+ (eligibility-adjusted)",
        "Population 18+ (adult-focused)",
        "Population 21+ (conservative)",
        "Total population (legacy)",
    ]
    if st.session_state.lang == "EN"
    else [
        "População 15+ (ajustada à elegibilidade)",
        "População 18+ (foco adulto)",
        "População 21+ (conservador)",
        "População total (legado)",
    ]
)
if st.session_state.get("fi_denominator") not in denominator_options:
    st.session_state["fi_denominator"] = denominator_options[0]
st.sidebar.selectbox(
    "Denominador de inclusão financeira" if st.session_state.lang == "PT" else "Financial inclusion denominator",
    denominator_options,
    key="fi_denominator",
)
selected_regions = st.sidebar.multiselect(T("zones"), list(regions_map.keys()), default=list(regions_map.keys()), help=T("help_zones"))
prov_options = [p for r in selected_regions for p in regions_map[r]]
selected_prov = st.sidebar.multiselect(T("provinces"), prov_options, default=prov_options, help=T("help_prov"))

if selected_prov:
    dist_filtered = acc_df[acc_df['Province'].isin(selected_prov)]['District'].dropna().unique()
    dist_options = sorted([str(d) for d in dist_filtered])
else:
    dist_options = sorted([str(d) for d in acc_df['District'].unique()])
selected_dist = st.sidebar.multiselect(T("districts"), dist_options, default=None, help=T("help_dist"))


# Decide grouping level: if user picked specific districts, drill down;
# otherwise aggregate at province level.
geo_axis = 'District' if selected_dist else 'Province'
geo_axis_label = T("district") if selected_dist else T("province")
title_suffix = f"{T('per_by')} {geo_axis_label}"


def _population_geq_age_2017(row: pd.Series, threshold_age: float) -> float:
    """Estimate population >= threshold age using Census 2017 grouped-age buckets."""
    p15 = float(row.get("Population_15plus_2017", 0))
    p10_14 = float(row.get("Population_10_14_2017", 0))
    p15_19 = float(row.get("Population_15_19_2017", 0))

    p20_plus = max(0.0, p15 - p15_19)
    # Note to self: keep this interpolation transparent; I prefer explainable approximation over opaque smoothing.
    if threshold_age <= 10:
        frac_10_14 = min(1.0, max(0.0, (15 - threshold_age) / 5))
        return p20_plus + p15_19 + p10_14 * frac_10_14
    if threshold_age < 15:
        frac_10_14 = min(1.0, max(0.0, (15 - threshold_age) / 5))
        return p20_plus + p15_19 + p10_14 * frac_10_14
    if threshold_age < 20:
        frac_15_19 = min(1.0, max(0.0, (20 - threshold_age) / 5))
        return p20_plus + p15_19 * frac_15_19
    return p20_plus if threshold_age < 100 else 0.0


def denominator_population(census_slice: pd.DataFrame, year: int) -> float:
    """Return denominator population for inclusion metrics under selected scenario."""
    label = st.session_state.get("fi_denominator", denominator_options[0])
    fallback_total = float(pd.to_numeric(census_slice.get("Population_Total", 0), errors="coerce").fillna(0).sum())
    if "legacy" in label.lower() or "legado" in label.lower():
        return fallback_total

    min_age = 15
    if "18+" in label:
        min_age = 18
    elif "21+" in label:
        min_age = 21

    # Backward-compatible fallback: if age-bucket columns are absent, use total population.
    required = {"Population_15plus_2017", "Population_10_14_2017", "Population_15_19_2017"}
    if not required.issubset(set(census_slice.columns)):
        return fallback_total

    # Cohort progression from Census 2017 age structure (no births/deaths/migration adjustment).
    threshold_2017 = max(0.0, float(min_age - (year - 2017)))
    est = census_slice.apply(lambda r: _population_geq_age_2017(r, threshold_2017), axis=1).sum()
    est = float(max(est, 0.0))
    return est if est > 0 else fallback_total


def row_denominator_population(row: pd.Series, year: int) -> float:
    """Row-level denominator aligned to selected inclusion scenario."""
    label = st.session_state.get("fi_denominator", denominator_options[0])
    fallback_total = float(pd.to_numeric(row.get("Population_Total", 0), errors="coerce"))
    if "legacy" in label.lower() or "legado" in label.lower():
        return fallback_total
    required = {"Population_15plus_2017", "Population_10_14_2017", "Population_15_19_2017"}
    if not required.issubset(set(row.index)):
        return fallback_total
    min_age = 15
    if "18+" in label:
        min_age = 18
    elif "21+" in label:
        min_age = 21
    threshold_2017 = max(0.0, float(min_age - (year - 2017)))
    est = float(max(_population_geq_age_2017(row, threshold_2017), 0.0))
    return est if est > 0 else fallback_total


def province_15plus_scale_map(year: int) -> dict[str, float]:
    """Province-level scale from 15+ census baseline to selected eligibility denominator."""
    scales: dict[str, float] = {}
    if census_df.empty:
        return scales
    for _, row in census_df.iterrows():
        prov = str(row.get("Province", "")).strip()
        p15 = float(pd.to_numeric(row.get("Population_15plus_2017", 0), errors="coerce"))
        if p15 <= 0:
            scales[prov] = 1.0
            continue
        target = row_denominator_population(row, year)
        scales[prov] = (target / p15) if p15 > 0 else 1.0
    return scales


def district_row_denominator_population(row: pd.Series, year: int, prov_scale: dict[str, float] | None = None) -> float:
    """District-level denominator aligned to selected inclusion scenario."""
    label = st.session_state.get("fi_denominator", denominator_options[0])
    pop_total = float(pd.to_numeric(row.get("Pop_Total_2017", 0), errors="coerce"))
    if "legacy" in label.lower() or "legado" in label.lower():
        return max(pop_total, 0.0)

    pop_15 = float(pd.to_numeric(row.get("Pop_15plus_2017", 0), errors="coerce"))
    if pop_15 <= 0:
        return max(pop_total, 0.0)

    if prov_scale is None:
        prov_scale = province_15plus_scale_map(year)
    prov = str(row.get("Province", "")).strip()
    scale = float(prov_scale.get(prov, 1.0))
    return max(pop_15 * max(scale, 0.0), 0.0)


def district_denominator_population(census_slice: pd.DataFrame, year: int) -> float:
    """Aggregate district denominator for the selected inclusion scenario."""
    if census_slice.empty:
        return 0.0
    prov_scale = province_15plus_scale_map(year)
    vals = census_slice.apply(lambda r: district_row_denominator_population(r, year, prov_scale), axis=1)
    return float(pd.to_numeric(vals, errors="coerce").fillna(0.0).sum())


def build_census_district_denominator_df(
    year: int,
    provinces: list[str] | None = None,
    districts: list[str] | None = None,
) -> pd.DataFrame:
    """Return district denominators for a scope and selected inclusion scenario."""
    if census_district_df.empty:
        return pd.DataFrame(columns=["Province", "District", "Eligible_Population"])
    scoped = census_district_df.copy()
    if provinces:
        scoped = scoped[scoped["Province"].isin(provinces)]
    if districts:
        scoped = scoped[scoped["District"].isin(districts)]
    if scoped.empty:
        return pd.DataFrame(columns=["Province", "District", "Eligible_Population"])
    prov_scale = province_15plus_scale_map(year)
    scoped["Eligible_Population"] = scoped.apply(
        lambda r: district_row_denominator_population(r, year, prov_scale),
        axis=1,
    )
    return scoped[["Province", "District", "Eligible_Population"]].copy()


def lookup_district_denominator(province: str, district: str, year: int) -> float:
    """Lookup district denominator by province/district with normalized matching."""
    if census_district_df.empty:
        return 0.0
    p_norm = _norm_key(province)
    d_norm = _norm_key(district)
    if {"_Province_Norm", "_District_Norm"}.issubset(census_district_df.columns):
        hit = census_district_df[
            (census_district_df["_Province_Norm"] == p_norm)
            & (census_district_df["_District_Norm"] == d_norm)
        ]
    else:
        tmp = census_district_df.copy()
        mask = (
            tmp["Province"].astype(str).apply(_norm_key).eq(p_norm)
            & tmp["District"].astype(str).apply(_norm_key).eq(d_norm)
        )
        hit = tmp[mask]
    if hit.empty:
        return 0.0
    return district_denominator_population(hit, year)


def inclusion_method_note(year: int) -> str:
    label = st.session_state.get("fi_denominator", denominator_options[0])
    if st.session_state.lang == "PT":
        return (
            f"Para calcular os Indicadores de Inclusão Financeira em {year}, é utilizado o Censo 2017 "
            "e é extrapolada a população elegível por coorte etária (progressão do tempo), sem ajuste de "
            "nascimentos, mortes ou migração. Decisão de negócio: adopta-se uma base elegível para reflectir "
            "melhor o mercado potencial de inclusão financeira. "
            f"Cenário seleccionado: {label}."
        )
    return (
        f"To calculate Financial Inclusion Indicators for {year}, we use Census 2017 and extrapolate the "
        "eligible population using age-cohort progression over time, without explicit birth/death/migration "
        "adjustments. Business decision: use an eligibility-based denominator to better reflect the "
        "potential market for financial inclusion. "
        f"Selected scenario: {label}."
    )


def render_page_caveats(extra_notes: list[str] | None = None) -> None:
    """Render a compact caveat panel with optional page-specific notes."""
    if st.session_state.lang == "PT":
        st.caption("ℹ️ Pressupostos e limitações metodológicas aplicam-se a esta página.")
        with st.expander("Pressupostos e limitações"):
            st.write("- A leitura é feita ao nível do sistema; não há dados por banco/provedor.")
            st.write("- O denominador de inclusão usa extrapolação por coorte com base no Censo 2017.")
            st.write("- O detalhe distrital de Carteira Móvel cobre actualmente os anos de 2023, 2024 e 2025.")
            st.write("- A leitura distrital de Carteira Móvel cobre apenas os distritos presentes nos ficheiros oficiais reportados pelo Banco de Moçambique para os anos disponíveis.")
            st.write("- Previsões de Carteira Móvel usam a série mensal disponível (actualmente 2023-2025, 36 observações), adequadas sobretudo para curto prazo.")
            st.write("- Cidade de Maputo é incluída em Província de Maputo para harmonização geográfica.")
            st.markdown(
                f"Fontes oficiais: [INCM Acervo]({INCM_SOURCE_TELECOM_URL}) · "
                f"[Banco de Moçambique]({BOM_SOURCE_STATS_URL})"
            )
            if extra_notes:
                for note in extra_notes:
                    st.write(f"- {note}")
    else:
        st.caption("ℹ️ Methodological assumptions and limitations apply to this page.")
        with st.expander("Assumptions and limitations"):
            st.write("- Interpretation is at system level; no bank/provider-level dataset is available.")
            st.write("- Inclusion denominator uses Census 2017 cohort extrapolation.")
            st.write("- Mobile Wallet district depth currently covers years 2023, 2024 and 2025.")
            st.write("- District-level Mobile Wallet reading covers only districts present in official files reported by Banco de Moçambique for available years.")
            st.write("- Mobile Wallet forecasts use the available monthly series (currently 2023-2025, 36 observations), mainly suitable for short-term reading.")
            st.write("- Cidade de Maputo is included under Província de Maputo for harmonized geographic reporting.")
            st.markdown(
                f"Official sources: [INCM Acervo]({INCM_SOURCE_TELECOM_URL}) · "
                f"[Bank of Mozambique]({BOM_SOURCE_STATS_URL})"
            )
            if extra_notes:
                for note in extra_notes:
                    st.write(f"- {note}")


def _pick_latest_period_value(df: pd.DataFrame) -> tuple[float | None, str | None]:
    """Pick annual value if available; otherwise latest quarter within the year."""
    if df.empty:
        return None, None
    annual = df[df["Quarter"].isna()].copy() if "Quarter" in df.columns else pd.DataFrame()
    if not annual.empty:
        row = annual.iloc[-1]
        return float(row["Value"]), str(row.get("Period", ""))
    q_order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    tmp = df.copy()
    tmp["Q_Ord"] = tmp["Quarter"].astype(str).map(q_order).fillna(0)
    tmp = tmp.sort_values("Q_Ord")
    row = tmp.iloc[-1]
    return float(row["Value"]), str(row.get("Period", ""))


def _pick_latest_quarter_value(df: pd.DataFrame) -> tuple[float | None, str | None]:
    """Pick latest available quarter only (do not mix annual and quarterly rows)."""
    if df.empty or "Quarter" not in df.columns:
        return None, None
    q_order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    tmp = df[df["Quarter"].notna()].copy()
    if tmp.empty:
        return None, None
    tmp["Q_Ord"] = tmp["Quarter"].astype(str).map(q_order).fillna(0)
    tmp = tmp.sort_values("Q_Ord")
    row = tmp.iloc[-1]
    return float(row["Value"]), str(row.get("Period", ""))


def official_inclusion_metrics(year: int) -> tuple[dict[str, float | None], str | None]:
    """Return official BoM national inclusion metrics for a given year."""
    result = {"accounts_per_capita": None, "cards_per_capita": None, "atm_per_100k": None, "pos_per_100k": None}
    if fi_indicators_df.empty:
        return result, None
    year_df = fi_indicators_df[pd.to_numeric(fi_indicators_df["Year"], errors="coerce") == year].copy()
    if year_df.empty:
        return result, None

    def _find_indicator(indicator_label: str) -> pd.DataFrame:
        norm_target = _norm_key(indicator_label)
        return year_df[year_df["Indicator"].astype(str).apply(lambda v: _norm_key(v) == norm_target)].copy()

    period_candidates: list[str] = []

    acc_df_off = _find_indicator("Contas bancárias (por 100 adultos)")
    acc_val, acc_period = _pick_latest_period_value(acc_df_off)
    if acc_val is not None:
        result["accounts_per_capita"] = acc_val / 100.0
        if acc_period:
            period_candidates.append(acc_period)

    card_df_off = _find_indicator("Cartões bancários (por 100 adultos)")
    card_val, card_period = _pick_latest_period_value(card_df_off)
    if card_val is not None:
        result["cards_per_capita"] = card_val / 100.0
        if card_period:
            period_candidates.append(card_period)

    atm_df_off = _find_indicator("ATM (por 100 mil adultos)")
    atm_val, atm_period = _pick_latest_period_value(atm_df_off)
    if atm_val is not None:
        result["atm_per_100k"] = atm_val
        if atm_period:
            period_candidates.append(atm_period)

    pos_df_off = _find_indicator("POS (por 100 mil adultos)")
    pos_val, pos_period = _pick_latest_period_value(pos_df_off)
    if pos_val is not None:
        result["pos_per_100k"] = pos_val
        if pos_period:
            period_candidates.append(pos_period)

    latest_period = sorted(period_candidates)[-1] if period_candidates else None
    return result, latest_period


# ── Filter helpers ──────────────────────────────────────────────────────────
def apply_filters(df, is_geo=True):
    """Apply sidebar year + geography filters."""
    mask = (df['Year'] == selected_year)
    if is_geo and 'Province' in df.columns:
        mask &= (df['Province'].isin(selected_prov))
        if selected_dist and 'District' in df.columns:
            mask &= (df['District'].isin(selected_dist))
    return df[mask]


def apply_geo_only(df):
    """Apply geography filters only (keep all years)."""
    mask = pd.Series(True, index=df.index)
    if 'Province' in df.columns:
        mask &= df['Province'].isin(selected_prov)
        if selected_dist and 'District' in df.columns:
            mask &= df['District'].isin(selected_dist)
    return df[mask]


# Pre-filter the 4 main datasets that support year + geography filtering
filtered_data = {key: apply_filters(df) for key, df in dataframes.items() if key in ['accounts', 'cards', 'atm', 'pos']}
f_acc, f_card, f_atm, f_pos = filtered_data["accounts"], filtered_data["cards"], filtered_data["atm"], filtered_data["pos"]

# Stock-metric snapshots: strict December only (for KPIs, totals, per-capita)
f_acc_snap = last_month_snapshot(f_acc)
f_card_snap = last_month_snapshot(f_card)
f_atm_snap = last_month_snapshot(f_atm)
f_pos_snap = last_month_snapshot(f_pos)


def build_scope_opportunity_df(year: int) -> pd.DataFrame:
    """Compute opportunity score table for current scope."""
    acc_opp = last_month_snapshot(apply_geo_only(acc_df[acc_df["Year"] == year]))
    atm_opp = last_month_snapshot(apply_geo_only(atm_df[atm_df["Year"] == year]))
    pos_opp = last_month_snapshot(apply_geo_only(pos_df[pos_df["Year"] == year]))

    district_scope = build_census_district_denominator_df(
        year,
        provinces=selected_prov if selected_prov else None,
        districts=selected_dist if selected_dist else None,
    )
    if district_scope.empty:
        census_scope = census_df[census_df["Province"].isin(selected_prov)].copy()
        if census_scope.empty:
            census_scope = census_df.copy()
        pop_rows = []
        for _, row in census_scope.iterrows():
            pop_rows.append(
                {
                    "Province": row["Province"],
                    "Population": row_denominator_population(row, year),
                }
            )
        pop_df = pd.DataFrame(pop_rows)
    else:
        pop_df = (
            district_scope.groupby("Province", as_index=False)["Eligible_Population"]
            .sum()
            .rename(columns={"Eligible_Population": "Population"})
        )

    ime_sub_opp = apply_geo_only(ime_sub_df.copy()) if not ime_sub_df.empty else pd.DataFrame()
    ime_agents_opp = apply_geo_only(ime_agents_df.copy()) if not ime_agents_df.empty else pd.DataFrame()
    ime_tx_opp = apply_geo_only(ime_txn_district_df.copy()) if not ime_txn_district_df.empty else pd.DataFrame()

    return build_opportunity_scores(
        population_by_province=pop_df,
        accounts_snapshot=acc_opp,
        atm_snapshot=atm_opp,
        pos_snapshot=pos_opp,
        ime_subscribers=ime_sub_opp,
        ime_agents=ime_agents_opp,
        ime_transactions=ime_tx_opp,
        year=year,
        weights=OpportunityWeights(),
    )


def build_wallet_bridge_annual() -> pd.DataFrame:
    """Build annual national bridge series between bank and mobile-wallet rails."""
    atm_val = normalize_atm_txn(val_df)
    atm_vol = normalize_atm_txn(vol_df)

    atm_withdraw_mask_val = (
        atm_val["Metric"].astype(str).str.casefold().str.contains("levant", na=False)
        & atm_val["Sub_Metric"].astype(str).str.casefold().str.contains("fundos depositados em telemóveis", na=False)
    )
    atm_withdraw_mask_vol = (
        atm_vol["Metric"].astype(str).str.casefold().str.contains("levant", na=False)
        & atm_vol["Sub_Metric"].astype(str).str.casefold().str.contains("fundos depositados em telemóveis", na=False)
    )

    atm_wallet_val = (
        atm_val[atm_withdraw_mask_val]
        .groupby("Year", as_index=False)["Transactions_Amount"]
        .sum()
        .rename(columns={"Transactions_Amount": "ATM_Wallet_Withdrawals_Value"})
    )
    atm_wallet_vol = (
        atm_vol[atm_withdraw_mask_vol]
        .groupby("Year", as_index=False)["Total_Transactions"]
        .sum()
        .rename(columns={"Total_Transactions": "ATM_Wallet_Withdrawals_Volume"})
    )
    mb_wallet_val = (
        mob_df[
            mob_df["Metric"].astype(str).str.contains(
                r"Valor das transferências efectuadas para .*telemóveis", case=False, na=False, regex=True
            )
        ]
        .groupby("Year", as_index=False)["Value"]
        .sum()
        .rename(columns={"Value": "MB_To_Wallet_Value"})
    )
    mb_wallet_vol = (
        mob_df[
            mob_df["Metric"].astype(str).str.contains(
                r"Volume das transferências efectuadas para .*telemóveis", case=False, na=False, regex=True
            )
        ]
        .groupby("Year", as_index=False)["Value"]
        .sum()
        .rename(columns={"Value": "MB_To_Wallet_Volume"})
    )

    bridge = (
        pd.merge(atm_wallet_val, atm_wallet_vol, on="Year", how="outer")
        .merge(mb_wallet_val, on="Year", how="outer")
        .merge(mb_wallet_vol, on="Year", how="outer")
    )
    for col in [
        "ATM_Wallet_Withdrawals_Value",
        "ATM_Wallet_Withdrawals_Volume",
        "MB_To_Wallet_Value",
        "MB_To_Wallet_Volume",
    ]:
        bridge[col] = pd.to_numeric(bridge[col], errors="coerce").fillna(0.0)
    bridge["Year"] = pd.to_numeric(bridge["Year"], errors="coerce")
    bridge = bridge.dropna(subset=["Year"]).copy()
    bridge["Year"] = bridge["Year"].astype(int)
    return bridge.sort_values("Year")


def render_deterministic_qa_panel(opp_df: pd.DataFrame | None = None, key_prefix: str = "overview") -> None:
    """Render deterministic Q&A with one dynamic chart per selected question."""
    st.subheader(
        "Perguntas e respostas (determinísticas)" if st.session_state.lang == "PT" else "Deterministic Q&A",
        help=(
            "Respostas calculadas directamente das tabelas carregadas, sem geração livre."
            if st.session_state.lang == "PT"
            else "Answers computed directly from loaded tables, without free-form generation."
        ),
    )
    st.caption(
        "Respostas calculadas diretamente das tabelas carregadas (sem geração livre de texto)."
        if st.session_state.lang == "PT"
        else "Answers are computed directly from loaded tables (no free-form generation)."
    )

    question_bank_pt = [
        ("Qual distrito lidera em valor de transacções de Carteira Móvel no último mês disponível?", "ime_top_value"),
        ("Qual distrito tem maior rácio de subscrições por agente de Carteira Móvel?", "ime_top_subs_per_agent"),
        ("Mobile Banking cresce mais em valor do que Internet Banking (YoY)?", "mobile_vs_internet_yoy"),
        ("Levantamentos ATM de fundos em telemóveis estão a aumentar ao longo dos anos?", "atm_wallet_withdrawals_trend"),
        ("No Mobile Banking, como evoluem as transferências para telemóveis (valor e volume)?", "mb_to_wallet_trend"),
        ("Como evoluem as transacções entre Carteira Móvel, Mobile Banking e Internet Banking (volume e valor)?", "cross_channel_flow_trend"),
        ("Como evoluiu o indicador oficial de contas por adulto desde 2020?", "official_accounts_change"),
        ("Como evoluiu o indicador oficial de cartões por adulto desde 2020?", "official_cards_change"),
        ("Quais são as 3 províncias com maior pontuação de oportunidade?", "opp_top3"),
        ("Que província lidera no índice IME/INCM (subscrições por 100)?", "incm_top_index"),
        ("Que província tem menor capacidade de agentes por 10 mil subscrições móveis?", "incm_low_agent_capacity"),
        ("Qual a quota feminina de contas e cartões no recorte actual?", "gender_shares"),
        ("Qual a quota da faixa 17-21 em contas e cartões no recorte actual?", "age_17_21_shares"),
        ("[Stock] Quantas contas existem no snapshot de Dezembro?", "stock_accounts"),
        ("[Stock] Quantos cartões existem no snapshot de Dezembro?", "stock_cards"),
        ("[Stock] Quantos ATM existem no snapshot de Dezembro?", "stock_atm"),
        ("[Stock] Quantos POS existem no snapshot de Dezembro?", "stock_pos"),
    ]
    question_bank_en = [
        ("Which district leads Mobile Wallet transaction value in the latest available month?", "ime_top_value"),
        ("Which district has the highest Mobile Wallet subscriptions-per-agent ratio?", "ime_top_subs_per_agent"),
        ("Is Mobile Banking value growing faster YoY than Internet Banking?", "mobile_vs_internet_yoy"),
        ("Are ATM withdrawals of mobile-wallet funds increasing over time?", "atm_wallet_withdrawals_trend"),
        ("How are Mobile Banking transfers to mobile numbers evolving (value and volume)?", "mb_to_wallet_trend"),
        ("How are transactions evolving across Mobile Wallet, Mobile Banking and Internet Banking (volume and value)?", "cross_channel_flow_trend"),
        ("How has the official accounts-per-adult indicator changed since 2020?", "official_accounts_change"),
        ("How has the official cards-per-adult indicator changed since 2020?", "official_cards_change"),
        ("Which are the top 3 provinces by opportunity score?", "opp_top3"),
        ("Which province leads the IME/INCM index (subscriptions per 100)?", "incm_top_index"),
        ("Which province has the lowest agent capacity per 10k mobile subscriptions?", "incm_low_agent_capacity"),
        ("What is the female share in accounts and cards for the current scope?", "gender_shares"),
        ("What is the 17-21 age share in accounts and cards for the current scope?", "age_17_21_shares"),
        ("[Stock] How many accounts exist in the December snapshot?", "stock_accounts"),
        ("[Stock] How many cards exist in the December snapshot?", "stock_cards"),
        ("[Stock] How many ATMs exist in the December snapshot?", "stock_atm"),
        ("[Stock] How many POS exist in the December snapshot?", "stock_pos"),
    ]
    q_bank = question_bank_pt if st.session_state.lang == "PT" else question_bank_en
    q_label = st.selectbox(
        "Escolha uma pergunta" if st.session_state.lang == "PT" else "Choose a question",
        [q for q, _ in q_bank],
        key=f"{key_prefix}_det_qna_question",
    )
    q_id = dict(q_bank)[q_label]

    answer = ""
    source = ""
    caveat = ""
    chart = None
    extra_charts: list = []

    if opp_df is None:
        opp_df = build_scope_opportunity_df(selected_year)

    ime_year_q = int(pd.to_numeric(ime_sub_df["Year"], errors="coerce").dropna().max()) if not ime_sub_df.empty else None
    ime_sub_q = ime_sub_df[ime_sub_df["Year"] == ime_year_q].copy() if ime_year_q else pd.DataFrame()
    ime_agents_q = ime_agents_df[ime_agents_df["Year"] == ime_year_q].copy() if ime_year_q else pd.DataFrame()
    ime_tx_q = ime_txn_district_df[ime_txn_district_df["Year"] == ime_year_q].copy() if ime_year_q else pd.DataFrame()
    if not ime_sub_q.empty:
        ime_sub_q = ime_sub_q[ime_sub_q["Province"].isin(selected_prov)]
    if not ime_agents_q.empty:
        ime_agents_q = ime_agents_q[ime_agents_q["Province"].isin(selected_prov)]
    if not ime_tx_q.empty:
        ime_tx_q = ime_tx_q[ime_tx_q["Province"].isin(selected_prov)]
    if selected_dist:
        if not ime_sub_q.empty:
            ime_sub_q = ime_sub_q[ime_sub_q["District"].isin(selected_dist)]
        if not ime_agents_q.empty:
            ime_agents_q = ime_agents_q[ime_agents_q["District"].isin(selected_dist)]
        if not ime_tx_q.empty:
            ime_tx_q = ime_tx_q[ime_tx_q["District"].isin(selected_dist)]

    incm_benchmark_q = pd.DataFrame()
    if ime_year_q is not None:
        month_series = ime_sub_df[ime_sub_df["Year"] == ime_year_q]["Month"].dropna().astype(str).unique().tolist()
        month_ref_q = "Dezembro" if "Dezembro" in month_series else None
        if month_ref_q is not None:
            ime_prov_scope_q = sorted(set(selected_prov) & set(INCM_MOBILE_SUBSCRIBERS_Q2_2025["Province"].astype(str).tolist()))
            sub_prov_q = (
                ime_sub_df[
                    (ime_sub_df["Year"] == ime_year_q)
                    & (ime_sub_df["Month"].astype(str) == month_ref_q)
                    & (ime_sub_df["Province"].isin(ime_prov_scope_q))
                ]
                .groupby("Province", as_index=False)["Subscribers"]
                .sum()
            )
            ag_prov_q = (
                ime_agents_df[
                    (ime_agents_df["Year"] == ime_year_q)
                    & (ime_agents_df["Month"].astype(str) == month_ref_q)
                    & (ime_agents_df["Province"].isin(ime_prov_scope_q))
                ]
                .groupby("Province", as_index=False)["Agents"]
                .sum()
            )
            incm_benchmark_q = (
                INCM_MOBILE_SUBSCRIBERS_Q2_2025[INCM_MOBILE_SUBSCRIBERS_Q2_2025["Province"].isin(ime_prov_scope_q)]
                .merge(sub_prov_q, on="Province", how="left")
                .merge(ag_prov_q, on="Province", how="left")
            )
            for col in ["Subscribers", "Agents"]:
                incm_benchmark_q[col] = pd.to_numeric(incm_benchmark_q[col], errors="coerce").fillna(0.0)
            incm_benchmark_q["IME_INCM_Index_per_100"] = incm_benchmark_q.apply(
                lambda r: (r["Subscribers"] / r["Mobile_Subscribers"] * 100) if r["Mobile_Subscribers"] > 0 else 0.0,
                axis=1,
            )
            incm_benchmark_q["Agents_per_10k_Mobile"] = incm_benchmark_q.apply(
                lambda r: (r["Agents"] / r["Mobile_Subscribers"] * 10_000) if r["Mobile_Subscribers"] > 0 else 0.0,
                axis=1,
            )

    if q_id == "ime_top_value":
        if ime_tx_q.empty:
            answer = "Sem dados de Carteira Móvel no recorte actual." if st.session_state.lang == "PT" else "No Mobile Wallet data for current scope."
        else:
            tx = ime_tx_q.copy()
            tx["Month_Ord"] = tx["Month"].astype(str).map(MONTH_RANK)
            latest_m = tx["Month_Ord"].max()
            tx_m = tx[tx["Month_Ord"] == latest_m]
            top = tx_m.groupby("District", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
            top10 = top.head(10)
            if top10.empty:
                answer = "Sem dados suficientes." if st.session_state.lang == "PT" else "Insufficient data."
            else:
                district = top10.iloc[0]["District"]
                val = top10.iloc[0]["Value"]
                answer = (
                    f"{district} lidera com {format_compact(val)} em valor de transacções de Carteira Móvel."
                    if st.session_state.lang == "PT"
                    else f"{district} leads with {format_compact(val)} in Mobile Wallet transaction value."
                )
                chart = px.bar(
                    top10,
                    x="District",
                    y="Value",
                    text=[format_compact(v) for v in top10["Value"]],
                    title=(
                        "Top 10 distritos por valor de transacções (Carteira Móvel)"
                        if st.session_state.lang == "PT"
                        else "Top 10 districts by Mobile Wallet transaction value"
                    ),
                )
                chart.update_layout(xaxis_tickangle=-25, yaxis=dict(rangemode="tozero"))
            source = "Mobile_Wallet_Transactions_District_2025.csv"
            caveat = "Cobertura distrital de Carteira Móvel de 2025." if st.session_state.lang == "PT" else "Mobile Wallet district coverage is for 2025."
    elif q_id == "ime_top_subs_per_agent":
        if ime_sub_q.empty or ime_agents_q.empty:
            answer = "Sem dados de Carteira Móvel no recorte actual." if st.session_state.lang == "PT" else "No Mobile Wallet data for current scope."
        else:
            sub_a = ime_sub_q.groupby("District", as_index=False)["Subscribers"].sum()
            ag_a = ime_agents_q.groupby("District", as_index=False)["Agents"].sum()
            merged = pd.merge(sub_a, ag_a, on="District", how="outer")
            merged["Subscribers"] = pd.to_numeric(merged["Subscribers"], errors="coerce").fillna(0)
            merged["Agents"] = pd.to_numeric(merged["Agents"], errors="coerce").fillna(0)
            merged["Ratio"] = merged.apply(lambda r: (r["Subscribers"] / r["Agents"]) if r["Agents"] > 0 else 0, axis=1)
            top = merged.sort_values("Ratio", ascending=False).head(10)
            if top.empty:
                answer = "Sem dados suficientes." if st.session_state.lang == "PT" else "Insufficient data."
            else:
                answer = (
                    f"{top.iloc[0]['District']} tem o maior rácio, com {top.iloc[0]['Ratio']:.1f} subscrições por agente."
                    if st.session_state.lang == "PT"
                    else f"{top.iloc[0]['District']} has the highest ratio at {top.iloc[0]['Ratio']:.1f} subscriptions per agent."
                )
                chart = px.bar(
                    top,
                    x="District",
                    y="Ratio",
                    text=[f"{v:.1f}" for v in top["Ratio"]],
                    title=(
                        "Top 10 distritos por subscrições por agente"
                        if st.session_state.lang == "PT"
                        else "Top 10 districts by subscriptions per agent"
                    ),
                )
                chart.update_layout(xaxis_tickangle=-25, yaxis=dict(rangemode="tozero"))
            source = "Mobile_Wallet_Subscribers_District_2025.csv + Mobile_Wallet_Agents_District_2025.csv"
            caveat = "Rácio não mede qualidade de serviço." if st.session_state.lang == "PT" else "Ratio does not measure service quality."
    elif q_id == "mobile_vs_internet_yoy":
        mob_val = mob_df[mob_df["Metric"].astype(str).str.contains("Valor", case=False, na=False)].groupby("Year")["Value"].sum().sort_index()
        net_val = net_df[net_df["Metric"].astype(str).str.contains("Valor", case=False, na=False)].groupby("Year")["Value"].sum().sort_index()
        if selected_year in mob_val.index and (selected_year - 1) in mob_val.index and selected_year in net_val.index and (selected_year - 1) in net_val.index:
            mob_yoy = ((mob_val.loc[selected_year] - mob_val.loc[selected_year - 1]) / mob_val.loc[selected_year - 1] * 100) if mob_val.loc[selected_year - 1] > 0 else 0
            net_yoy = ((net_val.loc[selected_year] - net_val.loc[selected_year - 1]) / net_val.loc[selected_year - 1] * 100) if net_val.loc[selected_year - 1] > 0 else 0
            winner = "Mobile Banking" if mob_yoy >= net_yoy else "Internet Banking"
            answer = (
                f"{winner} cresce mais no ano seleccionado: Mobile {mob_yoy:+.1f}% vs Internet {net_yoy:+.1f}%."
                if st.session_state.lang == "PT"
                else f"{winner} grows faster in the selected year: Mobile {mob_yoy:+.1f}% vs Internet {net_yoy:+.1f}%."
            )
            yoy_df = pd.DataFrame(
                {
                    "Channel": ["Mobile Banking", "Internet Banking"],
                    "Growth": [mob_yoy, net_yoy],
                }
            )
            chart = px.bar(
                yoy_df,
                x="Channel",
                y="Growth",
                text=[f"{v:+.1f}%" for v in yoy_df["Growth"]],
                title="YoY de valor por canal" if st.session_state.lang == "PT" else "Value YoY by channel",
            )
            chart.update_layout(yaxis=dict(rangemode="tozero"))
        else:
            answer = "Sem histórico suficiente para YoY." if st.session_state.lang == "PT" else "Insufficient history for YoY."
        source = "Mobile_Banking_2020_2025.csv + Internet_Banking_2020_2025.csv"
        caveat = "Comparação nacional agregada por canal." if st.session_state.lang == "PT" else "National channel-level aggregate comparison."
    elif q_id == "atm_wallet_withdrawals_trend":
        bridge = build_wallet_bridge_annual()
        if bridge.empty:
            answer = (
                "Sem histórico suficiente para levantamentos ATM ligados a telemóveis."
                if st.session_state.lang == "PT"
                else "Insufficient history for ATM withdrawals linked to mobile-wallet funds."
            )
        else:
            v_col = "ATM_Wallet_Withdrawals_Value"
            q_col = "ATM_Wallet_Withdrawals_Volume"
            first = bridge.iloc[0]
            last = bridge.iloc[-1]
            v_pct = ((last[v_col] - first[v_col]) / first[v_col] * 100) if first[v_col] > 0 else 0.0
            q_pct = ((last[q_col] - first[q_col]) / first[q_col] * 100) if first[q_col] > 0 else 0.0
            direction = (
                ("crescimento" if v_pct >= 0 else "redução")
                if st.session_state.lang == "PT"
                else ("growth" if v_pct >= 0 else "decline")
            )
            answer = (
                f"Há {direction}: no período {int(first['Year'])}-{int(last['Year'])}, o valor variou {v_pct:+.1f}% e o volume {q_pct:+.1f}%."
                if st.session_state.lang == "PT"
                else f"There is a {direction} pattern: from {int(first['Year'])} to {int(last['Year'])}, value changed {v_pct:+.1f}% and volume {q_pct:+.1f}%."
            )
            fig = go.Figure()
            fig.add_bar(
                x=bridge["Year"],
                y=bridge[v_col],
                name="Valor" if st.session_state.lang == "PT" else "Value",
                marker_color="#2563eb",
            )
            fig.add_scatter(
                x=bridge["Year"],
                y=bridge[q_col],
                name="Volume",
                mode="lines+markers",
                yaxis="y2",
                line=dict(color="#16a34a", width=3),
            )
            fig.update_layout(
                title=(
                    "Levantamentos ATM de fundos em telemóveis: valor e volume"
                    if st.session_state.lang == "PT"
                    else "ATM withdrawals of mobile-wallet funds: value and volume"
                ),
                yaxis=dict(rangemode="tozero"),
                yaxis2=dict(overlaying="y", side="right", rangemode="tozero"),
                xaxis=dict(dtick=1),
                legend=dict(orientation="h", y=1.08, x=0),
            )
            chart = fig
        source = "transactions_val_2020_2025.csv + transactions_vol_2020_2025.csv"
        caveat = (
            "Leitura nacional agregada da ponte ATM↔carteira móvel; não implica causalidade."
            if st.session_state.lang == "PT"
            else "National aggregate ATM↔mobile-wallet bridge reading; does not imply causality."
        )
    elif q_id == "mb_to_wallet_trend":
        bridge = build_wallet_bridge_annual()
        if bridge.empty:
            answer = (
                "Sem histórico suficiente para transferências Mobile Banking para telemóveis."
                if st.session_state.lang == "PT"
                else "Insufficient history for Mobile Banking transfers to mobile numbers."
            )
        else:
            v_col = "MB_To_Wallet_Value"
            q_col = "MB_To_Wallet_Volume"
            first = bridge.iloc[0]
            last = bridge.iloc[-1]
            v_pct = ((last[v_col] - first[v_col]) / first[v_col] * 100) if first[v_col] > 0 else 0.0
            q_pct = ((last[q_col] - first[q_col]) / first[q_col] * 100) if first[q_col] > 0 else 0.0
            direction = (
                ("crescimento" if v_pct >= 0 else "redução")
                if st.session_state.lang == "PT"
                else ("growth" if v_pct >= 0 else "decline")
            )
            answer = (
                f"Observa-se {direction}: entre {int(first['Year'])} e {int(last['Year'])}, o valor variou {v_pct:+.1f}% e o volume {q_pct:+.1f}%."
                if st.session_state.lang == "PT"
                else f"A {direction} pattern is observed: between {int(first['Year'])} and {int(last['Year'])}, value changed {v_pct:+.1f}% and volume changed {q_pct:+.1f}%."
            )
            fig = go.Figure()
            fig.add_bar(
                x=bridge["Year"],
                y=bridge[q_col],
                name="Volume",
                marker_color="#2563eb",
            )
            fig.add_scatter(
                x=bridge["Year"],
                y=bridge[v_col],
                name="Valor" if st.session_state.lang == "PT" else "Value",
                mode="lines+markers",
                yaxis="y2",
                line=dict(color="#f97316", width=3),
            )
            fig.update_layout(
                title=(
                    "Mobile Banking para telemóveis: evolução anual"
                    if st.session_state.lang == "PT"
                    else "Mobile Banking to mobile numbers: annual trend"
                ),
                yaxis=dict(rangemode="tozero"),
                yaxis2=dict(overlaying="y", side="right", rangemode="tozero"),
                xaxis=dict(dtick=1),
                legend=dict(orientation="h", y=1.08, x=0),
            )
            chart = fig
        source = "Mobile_Banking_2020_2025.csv"
        caveat = (
            "Indicador de Mobile Banking refere-se a aplicações bancárias e não ao total de contas de carteira móvel."
            if st.session_state.lang == "PT"
            else "Mobile Banking indicator refers to bank apps, not total mobile-wallet accounts."
        )
    elif q_id == "cross_channel_flow_trend":
        # This comparison is intentionally fixed to national multi-year scope for temporal readability.
        ime_scope = ime_txn_district_df.copy() if not ime_txn_district_df.empty else pd.DataFrame()

        if ime_scope.empty:
            answer = (
                "Sem dados suficientes para comparar canais."
                if st.session_state.lang == "PT"
                else "Insufficient data for cross-channel comparison."
            )
        else:
            ime_vol = ime_scope.groupby("Year", as_index=False)["Volume"].sum().rename(columns={"Volume": "Metric_Value"})
            ime_vol["Channel"] = "Carteira Móvel" if st.session_state.lang == "PT" else "Mobile Wallet"
            ime_val = ime_scope.groupby("Year", as_index=False)["Value"].sum().rename(columns={"Value": "Metric_Value"})
            ime_val["Channel"] = "Carteira Móvel" if st.session_state.lang == "PT" else "Mobile Wallet"

            mb_vol = (
                mob_df[mob_df["Metric"].astype(str).str.contains("Volume", case=False, na=False)]
                .groupby("Year", as_index=False)["Value"]
                .sum()
                .rename(columns={"Value": "Metric_Value"})
            )
            mb_vol["Channel"] = "Mobile Banking"
            mb_val = (
                mob_df[mob_df["Metric"].astype(str).str.contains("Valor", case=False, na=False)]
                .groupby("Year", as_index=False)["Value"]
                .sum()
                .rename(columns={"Value": "Metric_Value"})
            )
            mb_val["Channel"] = "Mobile Banking"

            ib_vol = (
                net_df[net_df["Metric"].astype(str).str.contains("Volume", case=False, na=False)]
                .groupby("Year", as_index=False)["Value"]
                .sum()
                .rename(columns={"Value": "Metric_Value"})
            )
            ib_vol["Channel"] = "Internet Banking"
            ib_val = (
                net_df[net_df["Metric"].astype(str).str.contains("Valor", case=False, na=False)]
                .groupby("Year", as_index=False)["Value"]
                .sum()
                .rename(columns={"Value": "Metric_Value"})
            )
            ib_val["Channel"] = "Internet Banking"

            vol_df_cmp = pd.concat([ime_vol, mb_vol, ib_vol], ignore_index=True)
            val_df_cmp = pd.concat([ime_val, mb_val, ib_val], ignore_index=True)
            vol_df_cmp["Year"] = pd.to_numeric(vol_df_cmp["Year"], errors="coerce")
            val_df_cmp["Year"] = pd.to_numeric(val_df_cmp["Year"], errors="coerce")
            vol_df_cmp = vol_df_cmp.dropna(subset=["Year"]).copy()
            val_df_cmp = val_df_cmp.dropna(subset=["Year"]).copy()
            vol_df_cmp["Year"] = vol_df_cmp["Year"].astype(int)
            val_df_cmp["Year"] = val_df_cmp["Year"].astype(int)
            common_years = sorted(set(ime_vol["Year"].astype(int).tolist()) & set(mb_vol["Year"].astype(int).tolist()) & set(ib_vol["Year"].astype(int).tolist()))
            if common_years:
                vol_df_cmp = vol_df_cmp[vol_df_cmp["Year"].isin(common_years)].copy()
                val_df_cmp = val_df_cmp[val_df_cmp["Year"].isin(common_years)].copy()

            if vol_df_cmp.empty or val_df_cmp.empty:
                answer = (
                    "Sem dados suficientes para comparar canais."
                    if st.session_state.lang == "PT"
                    else "Insufficient data for cross-channel comparison."
                )
            else:
                span = f"{int(vol_df_cmp['Year'].min())}-{int(vol_df_cmp['Year'].max())}"
                answer = (
                    f"No período {span}, observa-se evolução diferenciada por canal em volume e valor."
                    if st.session_state.lang == "PT"
                    else f"Across {span}, channels show differentiated trajectories in both volume and value."
                )
                fig_vol = px.bar(
                    vol_df_cmp.sort_values("Year"),
                    x="Year",
                    y="Metric_Value",
                    color="Channel",
                    barmode="stack",
                    title=(
                        "Comparação por canal — Volume (anual)"
                        if st.session_state.lang == "PT"
                        else "Cross-channel comparison — Volume (annual)"
                    ),
                )
                fig_vol.update_layout(xaxis=dict(dtick=1), yaxis=dict(rangemode="tozero"))
                fig_val = px.line(
                    val_df_cmp.sort_values("Year"),
                    x="Year",
                    y="Metric_Value",
                    color="Channel",
                    markers=True,
                    title=(
                        "Comparação por canal — Valor (anual)"
                        if st.session_state.lang == "PT"
                        else "Cross-channel comparison — Value (annual)"
                    ),
                )
                fig_val.update_layout(xaxis=dict(dtick=1), yaxis=dict(rangemode="tozero"))
                extra_charts = [fig_vol, fig_val]
        source = "IME_Transactions_District_2023_2025.csv + Mobile_Banking_2020_2025.csv + Internet_Banking_2020_2025.csv"
        caveat = (
            "Comparação nacional multi-anual (ignora filtros laterais) e com escopos de reporte diferentes; usar como leitura direccional."
            if st.session_state.lang == "PT"
            else "National multi-year comparison (ignores sidebar filters) and uses different reporting scopes; treat as directional reading."
        )
    elif q_id in {"official_accounts_change", "official_cards_change"}:
        indicator = "Contas bancárias (por 100 adultos)" if q_id == "official_accounts_change" else "Cartões bancários (por 100 adultos)"
        idf = fi_indicators_df[fi_indicators_df["Indicator"].astype(str).apply(lambda x: _norm_key(x) == _norm_key(indicator))].copy()
        v2020, plast = None, None
        vlast = None
        if not idf.empty:
            idf_q = idf[idf["Quarter"].notna()].copy() if "Quarter" in idf.columns else idf.iloc[0:0].copy()
            d2020 = idf_q[pd.to_numeric(idf_q["Year"], errors="coerce") == 2020]
            latest_year_in_q = pd.to_numeric(idf_q["Year"], errors="coerce").max() if not idf_q.empty else None
            dlast = (
                idf_q[pd.to_numeric(idf_q["Year"], errors="coerce") == latest_year_in_q]
                if latest_year_in_q is not None
                else pd.DataFrame()
            )
            v2020, _ = _pick_latest_quarter_value(d2020)
            vlast, plast = _pick_latest_quarter_value(dlast)
            series_rows = []
            for y in sorted(pd.to_numeric(idf_q["Year"], errors="coerce").dropna().astype(int).unique().tolist()):
                y_df = idf_q[pd.to_numeric(idf_q["Year"], errors="coerce") == y]
                y_val, _ = _pick_latest_quarter_value(y_df)
                if y_val is not None:
                    series_rows.append({"Year": y, "Value": y_val})
            if series_rows:
                series_df = pd.DataFrame(series_rows)
                chart = px.line(
                    series_df,
                    x="Year",
                    y="Value",
                    markers=True,
                    title=(
                        "Evolução oficial do indicador (último trimestre do ano)"
                        if st.session_state.lang == "PT"
                        else "Official indicator evolution (latest quarter by year)"
                    ),
                )
                chart.update_layout(xaxis=dict(dtick=1), yaxis=dict(rangemode="tozero"))
        if v2020 is None or vlast is None:
            answer = "Sem dados oficiais suficientes." if st.session_state.lang == "PT" else "Insufficient official data."
        else:
            delta = vlast - v2020
            pct = (delta / v2020 * 100) if v2020 > 0 else 0
            answer = (
                f"O indicador variou de {v2020:.2f} para {vlast:.2f} ({pct:+.1f}%) até {plast}."
                if st.session_state.lang == "PT"
                else f"The indicator moved from {v2020:.2f} to {vlast:.2f} ({pct:+.1f}%) up to {plast}."
            )
        source = "Financial_Inclusion_Indicators_2020_2025Q3.csv"
        caveat = (
            "Série trimestral oficial: leitura construída apenas com o último trimestre disponível de cada ano (sem mistura com linhas anuais)."
            if st.session_state.lang == "PT"
            else "Official quarterly series: built only from the latest available quarter of each year (no annual+quarter mixing)."
        )
    elif q_id == "opp_top3":
        if not opp_df.empty:
            top3 = opp_df.head(3)
            labels = [f"{r['Province']} ({r['Opportunity_Score']:.1f})" for _, r in top3.iterrows()]
            answer = (
                "Top 3 oportunidades: " + ", ".join(labels) + "."
                if st.session_state.lang == "PT"
                else "Top 3 opportunities: " + ", ".join(labels) + "."
            )
            chart = px.bar(
                top3,
                x="Province",
                y="Opportunity_Score",
                text=[f"{v:.1f}" for v in top3["Opportunity_Score"]],
                title=(
                    "Top 3 províncias por pontuação de oportunidade"
                    if st.session_state.lang == "PT"
                    else "Top 3 provinces by opportunity score"
                ),
            )
            chart.update_layout(yaxis=dict(rangemode="tozero"))
        else:
            answer = "Sem dados de oportunidade no recorte actual." if st.session_state.lang == "PT" else "No opportunity data for current scope."
        source = "Opportunity score (derived from Mobile Wallet + stock + infrastructure datasets)"
        caveat = "Pontuação de priorização, não causalidade." if st.session_state.lang == "PT" else "Prioritization score, not causality."
    elif q_id == "incm_top_index":
        if incm_benchmark_q.empty:
            answer = "Sem dados INCM/IME suficientes no recorte actual." if st.session_state.lang == "PT" else "Insufficient INCM/IME data in current scope."
        else:
            top = incm_benchmark_q.sort_values("IME_INCM_Index_per_100", ascending=False)
            prov = str(top.iloc[0]["Province"])
            idx = float(top.iloc[0]["IME_INCM_Index_per_100"])
            answer = (
                f"{prov} lidera com índice IME/INCM de {idx:.1f} subscrições por 100 subscrições móveis."
                if st.session_state.lang == "PT"
                else f"{prov} leads with an IME/INCM index of {idx:.1f} subscriptions per 100 mobile subscriptions."
            )
            chart = px.bar(
                top,
                x="Province",
                y="IME_INCM_Index_per_100",
                text=[f"{v:.1f}" for v in top["IME_INCM_Index_per_100"]],
                title=(
                    "Índice IME/INCM por província"
                    if st.session_state.lang == "PT"
                    else "IME/INCM index by province"
                ),
            )
            chart.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
        source = "INCM Acervo (Q2 2025) + IME_Subscribers_District_2025.csv"
        caveat = (
            "Índice relativo (não representa pessoas únicas) e pode exceder 100."
            if st.session_state.lang == "PT"
            else "Relative index (not unique persons) and may exceed 100."
        )
    elif q_id == "incm_low_agent_capacity":
        if incm_benchmark_q.empty:
            answer = "Sem dados INCM/IME suficientes no recorte actual." if st.session_state.lang == "PT" else "Insufficient INCM/IME data in current scope."
        else:
            low = incm_benchmark_q.sort_values("Agents_per_10k_Mobile", ascending=True)
            prov = str(low.iloc[0]["Province"])
            cap = float(low.iloc[0]["Agents_per_10k_Mobile"])
            answer = (
                f"{prov} apresenta a menor capacidade, com {cap:.1f} agentes por 10 mil subscrições móveis."
                if st.session_state.lang == "PT"
                else f"{prov} has the lowest capacity at {cap:.1f} agents per 10k mobile subscriptions."
            )
            chart = px.bar(
                low,
                x="Province",
                y="Agents_per_10k_Mobile",
                text=[f"{v:.1f}" for v in low["Agents_per_10k_Mobile"]],
                title=(
                    "Capacidade de agentes por 10 mil subscrições móveis"
                    if st.session_state.lang == "PT"
                    else "Agent capacity per 10k mobile subscriptions"
                ),
            )
            chart.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
        source = "INCM Acervo (Q2 2025) + IME_Agents_District_2025.csv"
        caveat = (
            "Leitura de capacidade relativa; não mede qualidade de serviço."
            if st.session_state.lang == "PT"
            else "Relative capacity reading; does not measure service quality."
        )
    elif q_id == "gender_shares":
        acc_total = f_acc_snap["Total_Accounts"].sum()
        card_total = f_card_snap["Total_Cards"].sum()
        acc_f = f_acc_snap[f_acc_snap["Gender"] == "Mulheres"]["Total_Accounts"].sum()
        card_f = f_card_snap[f_card_snap["Gender"] == "Mulheres"]["Total_Cards"].sum()
        a_share = (acc_f / acc_total * 100) if acc_total > 0 else 0
        c_share = (card_f / card_total * 100) if card_total > 0 else 0
        answer = (
            f"Quota feminina: contas {a_share:.1f}% e cartões {c_share:.1f}%."
            if st.session_state.lang == "PT"
            else f"Female share: accounts {a_share:.1f}% and cards {c_share:.1f}%."
        )
        sh_df = pd.DataFrame(
            [
                {"Indicator": "Contas" if st.session_state.lang == "PT" else "Accounts", "Segment": "Mulheres" if st.session_state.lang == "PT" else "Female", "Share": a_share},
                {"Indicator": "Contas" if st.session_state.lang == "PT" else "Accounts", "Segment": "Outros" if st.session_state.lang == "PT" else "Others", "Share": max(0.0, 100 - a_share)},
                {"Indicator": "Cartões" if st.session_state.lang == "PT" else "Cards", "Segment": "Mulheres" if st.session_state.lang == "PT" else "Female", "Share": c_share},
                {"Indicator": "Cartões" if st.session_state.lang == "PT" else "Cards", "Segment": "Outros" if st.session_state.lang == "PT" else "Others", "Share": max(0.0, 100 - c_share)},
            ]
        )
        chart = px.bar(
            sh_df,
            x="Indicator",
            y="Share",
            color="Segment",
            barmode="stack",
            text=[f"{v:.1f}%" for v in sh_df["Share"]],
            title="Distribuição por género" if st.session_state.lang == "PT" else "Gender distribution",
        )
        chart.update_layout(yaxis=dict(range=[0, 100]))
        source = "accounts_2020_2025.csv + cards_2020_2025.csv"
        caveat = "Quota mede distribuição, não qualidade de acesso." if st.session_state.lang == "PT" else "Share measures distribution, not quality of access."
    elif q_id == "age_17_21_shares":
        acc_total = f_acc_snap["Total_Accounts"].sum()
        card_total = f_card_snap["Total_Cards"].sum()
        acc_y = f_acc_snap[f_acc_snap["Age"] == "17-21"]["Total_Accounts"].sum()
        card_y = f_card_snap[f_card_snap["Age"] == "17-21"]["Total_Cards"].sum()
        a_share = (acc_y / acc_total * 100) if acc_total > 0 else 0
        c_share = (card_y / card_total * 100) if card_total > 0 else 0
        answer = (
            f"Faixa 17-21: contas {a_share:.1f}% e cartões {c_share:.1f}%."
            if st.session_state.lang == "PT"
            else f"Age 17-21: accounts {a_share:.1f}% and cards {c_share:.1f}%."
        )
        age_df = pd.DataFrame(
            [
                {"Indicator": "Contas" if st.session_state.lang == "PT" else "Accounts", "Segment": "17-21", "Share": a_share},
                {"Indicator": "Contas" if st.session_state.lang == "PT" else "Accounts", "Segment": "Outras idades" if st.session_state.lang == "PT" else "Other ages", "Share": max(0.0, 100 - a_share)},
                {"Indicator": "Cartões" if st.session_state.lang == "PT" else "Cards", "Segment": "17-21", "Share": c_share},
                {"Indicator": "Cartões" if st.session_state.lang == "PT" else "Cards", "Segment": "Outras idades" if st.session_state.lang == "PT" else "Other ages", "Share": max(0.0, 100 - c_share)},
            ]
        )
        chart = px.bar(
            age_df,
            x="Indicator",
            y="Share",
            color="Segment",
            barmode="stack",
            text=[f"{v:.1f}%" for v in age_df["Share"]],
            title="Distribuição por faixa etária (17-21)" if st.session_state.lang == "PT" else "Age-group distribution (17-21)",
        )
        chart.update_layout(yaxis=dict(range=[0, 100]))
        source = "accounts_2020_2025.csv + cards_2020_2025.csv"
        caveat = "Depende da disponibilidade de reporte por faixa etária." if st.session_state.lang == "PT" else "Depends on age-group reporting availability."
    elif q_id == "stock_accounts":
        total_val = f_acc_snap["Total_Accounts"].sum()
        answer = (
            f"O snapshot de Dezembro mostra {format_compact(total_val)} contas."
            if st.session_state.lang == "PT"
            else f"December snapshot shows {format_compact(total_val)} accounts."
        )
        byp = f_acc_snap.groupby("Province", as_index=False)["Total_Accounts"].sum().sort_values("Total_Accounts", ascending=False).head(10)
        chart = px.bar(
            byp,
            x="Province",
            y="Total_Accounts",
            text=[format_compact(v) for v in byp["Total_Accounts"]],
            title="Top províncias por contas" if st.session_state.lang == "PT" else "Top provinces by accounts",
        )
        chart.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
        source = "accounts_2020_2025.csv"
        caveat = "Stock medido pelo valor reportado em Dezembro." if st.session_state.lang == "PT" else "Stock measured using December reported value."
    elif q_id == "stock_cards":
        total_val = f_card_snap["Total_Cards"].sum()
        answer = (
            f"O snapshot de Dezembro mostra {format_compact(total_val)} cartões."
            if st.session_state.lang == "PT"
            else f"December snapshot shows {format_compact(total_val)} cards."
        )
        byp = f_card_snap.groupby("Province", as_index=False)["Total_Cards"].sum().sort_values("Total_Cards", ascending=False).head(10)
        chart = px.bar(
            byp,
            x="Province",
            y="Total_Cards",
            text=[format_compact(v) for v in byp["Total_Cards"]],
            title="Top províncias por cartões" if st.session_state.lang == "PT" else "Top provinces by cards",
        )
        chart.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
        source = "cards_2020_2025.csv"
        caveat = "Stock medido pelo valor reportado em Dezembro." if st.session_state.lang == "PT" else "Stock measured using December reported value."
    elif q_id == "stock_atm":
        total_val = f_atm_snap["ATMs_Number"].sum()
        answer = (
            f"O snapshot de Dezembro mostra {format_compact(total_val)} ATM."
            if st.session_state.lang == "PT"
            else f"December snapshot shows {format_compact(total_val)} ATMs."
        )
        byp = f_atm_snap.groupby("Province", as_index=False)["ATMs_Number"].sum().sort_values("ATMs_Number", ascending=False).head(10)
        chart = px.bar(
            byp,
            x="Province",
            y="ATMs_Number",
            text=[format_compact(v) for v in byp["ATMs_Number"]],
            title="Top províncias por ATM" if st.session_state.lang == "PT" else "Top provinces by ATMs",
        )
        chart.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
        source = "ATM_Infrastructure_2020_2025.csv"
        caveat = "Stock medido pelo valor reportado em Dezembro." if st.session_state.lang == "PT" else "Stock measured using December reported value."
    elif q_id == "stock_pos":
        total_val = f_pos_snap["POSs_Number"].sum()
        answer = (
            f"O snapshot de Dezembro mostra {format_compact(total_val)} POS."
            if st.session_state.lang == "PT"
            else f"December snapshot shows {format_compact(total_val)} POS."
        )
        byp = f_pos_snap.groupby("Province", as_index=False)["POSs_Number"].sum().sort_values("POSs_Number", ascending=False).head(10)
        chart = px.bar(
            byp,
            x="Province",
            y="POSs_Number",
            text=[format_compact(v) for v in byp["POSs_Number"]],
            title="Top províncias por POS" if st.session_state.lang == "PT" else "Top provinces by POS",
        )
        chart.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
        source = "POS_Infrastructure_2020_2025.csv"
        caveat = "Stock medido pelo valor reportado em Dezembro." if st.session_state.lang == "PT" else "Stock measured using December reported value."
    elif q_id == "stock_top_atm_prov":
        atm_top = f_atm_snap.groupby("Province", as_index=False)["ATMs_Number"].sum().sort_values("ATMs_Number", ascending=False).head(1)
        if atm_top.empty:
            answer = "Sem dados ATM no recorte." if st.session_state.lang == "PT" else "No ATM data in scope."
        else:
            answer = (
                f"{atm_top.iloc[0]['Province']} lidera com {format_compact(atm_top.iloc[0]['ATMs_Number'])} ATM."
                if st.session_state.lang == "PT"
                else f"{atm_top.iloc[0]['Province']} leads with {format_compact(atm_top.iloc[0]['ATMs_Number'])} ATMs."
            )
        byp = f_atm_snap.groupby("Province", as_index=False)["ATMs_Number"].sum().sort_values("ATMs_Number", ascending=False).head(10)
        chart = px.bar(
            byp,
            x="Province",
            y="ATMs_Number",
            text=[format_compact(v) for v in byp["ATMs_Number"]],
            title="Ranking de ATM por província" if st.session_state.lang == "PT" else "ATM ranking by province",
        )
        chart.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
        source = "ATM_Infrastructure_2020_2025.csv"
        caveat = "Ranking calculado com o valor reportado em Dezembro." if st.session_state.lang == "PT" else "Ranking computed using December reported value."
    elif q_id == "stock_top_pos_prov":
        pos_top = f_pos_snap.groupby("Province", as_index=False)["POSs_Number"].sum().sort_values("POSs_Number", ascending=False).head(1)
        if pos_top.empty:
            answer = "Sem dados POS no recorte." if st.session_state.lang == "PT" else "No POS data in scope."
        else:
            answer = (
                f"{pos_top.iloc[0]['Province']} lidera com {format_compact(pos_top.iloc[0]['POSs_Number'])} POS."
                if st.session_state.lang == "PT"
                else f"{pos_top.iloc[0]['Province']} leads with {format_compact(pos_top.iloc[0]['POSs_Number'])} POS."
            )
        byp = f_pos_snap.groupby("Province", as_index=False)["POSs_Number"].sum().sort_values("POSs_Number", ascending=False).head(10)
        chart = px.bar(
            byp,
            x="Province",
            y="POSs_Number",
            text=[format_compact(v) for v in byp["POSs_Number"]],
            title="Ranking de POS por província" if st.session_state.lang == "PT" else "POS ranking by province",
        )
        chart.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
        source = "POS_Infrastructure_2020_2025.csv"
        caveat = "Ranking calculado com o valor reportado em Dezembro." if st.session_state.lang == "PT" else "Ranking computed using December reported value."

    st.info(answer)
    if chart is not None:
        plot_chart(chart, use_container_width=True)
    if extra_charts:
        for extra_chart in extra_charts:
            plot_chart(extra_chart, use_container_width=True)
    if caveat:
        st.caption(("Nota: " if st.session_state.lang == "PT" else "Caveat: ") + caveat)
    # Keep source internally mapped in the logic, but do not display source tags in the UI.
    _ = source


# ── Dashboard tabs ──────────────────────────────────────────────────────────
tab_home, tab_overview, tab_ime, tab_decision, tab_demo, tab_channels, tab_accounts_cards, tab_infra, tab_trends, tab_forecast = st.tabs(
    [
        T("tab_home"),
        T("tab_overview"),
        T("tab_ime"),
        T("tab_decision"),
        T("tab_demo"),
        f"{T('tab_digital')} + {T('tab_txn')}",
        f"{T('tab_accounts')} + {T('tab_cards')}",
        T("tab_infra"),
        T("tab_trends"),
        T("tab_forecast"),
    ]
)

# ==========================================
# PAGE 0: HOME
# ==========================================
with tab_home:
    st.title(T("title_home"))
    st.caption(T("caption_home"))

    core_years = sorted(int(y) for y in all_years)
    core_span = f"{core_years[0]}-{core_years[-1]}" if core_years else "N/A"
    wallet_years = (
        sorted(pd.to_numeric(ime_txn_district_df["Year"], errors="coerce").dropna().astype(int).unique().tolist())
        if not ime_txn_district_df.empty and "Year" in ime_txn_district_df.columns
        else []
    )
    wallet_span = (
        f"{wallet_years[0]}-{wallet_years[-1]}"
        if len(wallet_years) > 1
        else (str(wallet_years[0]) if len(wallet_years) == 1 else "N/A")
    )
    geo_scope = (
        f"{len(selected_prov)} províncias"
        if st.session_state.lang == "PT"
        else f"{len(selected_prov)} provinces"
    )

    h1, h2, h3 = st.columns(3)
    metric_with_help(
        h1,
        "Período de Dados da Banca Electrónica" if st.session_state.lang == "PT" else "Electronic Banking Data Period",
        core_span,
        help_pt=(
            "Dados da banca tradicional reportados pelo Banco de Moçambique: contas, cartões, transacções em ATM/POS, "
            "Internet Banking e Mobile Banking."
        ),
        help_en=(
            "Traditional banking-system data reported by Banco de Moçambique: accounts, cards, ATM/POS transactions, "
            "Internet Banking, and Mobile Banking."
        ),
    )
    metric_with_help(
        h2,
        "Período de Dados de Carteira Móvel" if st.session_state.lang == "PT" else "Mobile Wallet Data Period",
        wallet_span,
        help_pt=(
            "Dados reportados por serviços de Carteira Móvel em Moçambique (M-Pesa, e-Mola, mKesh e Conta Móvel), "
            "incluindo subscrições, agentes, transferências, depósitos, levantamentos e pagamentos."
        ),
        help_en=(
            "Data reported by Mobile Wallet services in Mozambique (M-Pesa, e-Mola, mKesh, and Conta Móvel), "
            "including subscriptions, agents, transfers, deposits, withdrawals, and payments."
        ),
    )
    h3.metric("Cobertura geográfica actual" if st.session_state.lang == "PT" else "Current geographic scope", geo_scope)

    st.markdown("### " + ("O que pode ser explorado" if st.session_state.lang == "PT" else "What you can explore"))
    e1, e2, e3 = st.columns(3)
    e1.info(
        "**Tendências de finanças digitais**\n\n"
        "Evolução de transacções, canais e intensidade de uso."
        if st.session_state.lang == "PT"
        else "**Digital finance trends**\n\nTrack transaction, channel, and usage intensity evolution."
    )
    e2.info(
        "**Comparação territorial**\n\n"
        "Leituras por província e distrito para priorização."
        if st.session_state.lang == "PT"
        else "**Territorial comparison**\n\nCompare provinces and districts for prioritization."
    )
    e3.info(
        "**Leitura de cenários**\n\n"
        "Projecções de curto prazo para apoiar planeamento."
        if st.session_state.lang == "PT"
        else "**Scenario reading**\n\nUse short-term projections to support planning."
    )

    st.markdown("### " + ("Páginas e perguntas principais" if st.session_state.lang == "PT" else "Pages and key questions"))
    page_rows = (
        [
            (T("tab_overview"), "Quais são os sinais mais importantes no recorte actual?"),
            (T("tab_ime"), "Como as Carteiras Móveis são usadas por território e tipo de operação?"),
            (T("tab_decision"), "Onde estão as prioridades e como comparar distritos para investimento?"),
            (T("tab_demo"), "Qual é o contexto demográfico e de inclusão financeira?"),
            (f"{T('tab_digital')} + {T('tab_txn')}", "Como evoluem canais digitais e transacções por valor e volume?"),
            (f"{T('tab_accounts')} + {T('tab_cards')}", "Como evoluem contas e cartões por perfil e geografia?"),
            (T("tab_infra"), "Como evolui a infraestrutura física de ATM/POS?"),
            (T("tab_trends"), "Quais são as tendências estruturais no período histórico?"),
            (T("tab_forecast"), "Qual é a trajectória esperada de curto prazo para indicadores de fluxo?"),
        ]
        if st.session_state.lang == "PT"
        else [
            (T("tab_overview"), "What are the most important signals in the current scope?"),
            (T("tab_ime"), "How are Mobile Wallets used by territory and operation type?"),
            (T("tab_decision"), "Where are priorities and how can districts be compared for investment?"),
            (T("tab_demo"), "What is the demographic and financial-inclusion context?"),
            (f"{T('tab_digital')} + {T('tab_txn')}", "How do digital channels and transactions evolve by value and volume?"),
            (f"{T('tab_accounts')} + {T('tab_cards')}", "How do accounts and cards evolve by profile and geography?"),
            (T("tab_infra"), "How does ATM/POS physical infrastructure evolve?"),
            (T("tab_trends"), "What structural trends matter in the historical period?"),
            (T("tab_forecast"), "What is the expected short-term path for flow indicators?"),
        ]
    )
    page_df = pd.DataFrame(
        page_rows,
        columns=[
            "Página" if st.session_state.lang == "PT" else "Page",
            "Pergunta principal" if st.session_state.lang == "PT" else "Main question",
        ],
    )
    st.dataframe(page_df, use_container_width=True, hide_index=True)

    st.markdown("### " + ("Como ler este dashboard" if st.session_state.lang == "PT" else "How to read this dashboard"))
    r1, r2, r3 = st.columns(3)
    with r1:
        st.subheader(
            "Stock vs Fluxo" if st.session_state.lang == "PT" else "Stock vs Flow",
            help=(
                "Stock usa valor reportado em Dezembro; fluxo usa agregação do período."
                if st.session_state.lang == "PT"
                else "Stock uses December reported value; flow uses period aggregation."
            ),
        )
        st.caption(
            "Contas, cartões, ATM e POS são stock; transacções são fluxo."
            if st.session_state.lang == "PT"
            else "Accounts, cards, ATM and POS are stock; transactions are flow."
        )
    with r2:
        st.subheader(
            "Subscrições vs pessoas" if st.session_state.lang == "PT" else "Subscriptions vs people",
            help=(
                "Uma pessoa pode ter mais de uma conta/serviço; subscrições não equivalem a pessoas únicas."
                if st.session_state.lang == "PT"
                else "One person can hold multiple services; subscriptions are not unique people."
            ),
        )
        st.caption(
            "Usar os indicadores de subscrições como sinal de intensidade relativa."
            if st.session_state.lang == "PT"
            else "Use subscription indicators as a relative intensity signal."
        )
    with r3:
        st.subheader(
            "Inclusão oficial + fallback" if st.session_state.lang == "PT" else "Official inclusion + fallback",
            help=(
                "Prioriza-se o indicador oficial; na ausência, usa-se extrapolação do Censo 2017."
                if st.session_state.lang == "PT"
                else "Official indicators are prioritized; when missing, Census 2017 extrapolation is used."
            ),
        )
        st.caption(
            "O cenário 15+/18+/21+ afecta o denominador dos rácios de inclusão."
            if st.session_state.lang == "PT"
            else "The 15+/18+/21+ scenario changes the denominator used in inclusion ratios."
        )
    st.caption(
        "Valor = montante financeiro envolvido nas transacções | Volume = número de transacções."
        if st.session_state.lang == "PT"
        else "Value = amount involved in transactions | Volume = number of transactions."
    )

    st.markdown("### " + ("Pressupostos e limitações principais" if st.session_state.lang == "PT" else "Key assumptions and limitations"))
    if st.session_state.lang == "PT":
        st.write("- Cidade de Maputo é incluída em Província de Maputo para harmonização geográfica.")
        st.write("- O detalhe distrital de Carteira Móvel cobre apenas distritos presentes nos ficheiros oficiais.")
        st.write("- Quando indicador oficial de inclusão não está disponível, aplica-se extrapolação do Censo 2017 por coorte.")
    else:
        st.write("- Cidade de Maputo is included under Província de Maputo for geographic harmonization.")
        st.write("- District-level Mobile Wallet detail covers only districts present in official files.")
        st.write("- When official inclusion indicators are unavailable, Census 2017 cohort extrapolation is applied.")

    st.markdown("### " + ("Fontes" if st.session_state.lang == "PT" else "Sources"))
    st.markdown(
        f"- [Banco de Moçambique — Domínios e Indicadores]({BOM_SOURCE_STATS_URL})\n"
        f"- [INCM Acervo — Telecom]({INCM_SOURCE_TELECOM_URL})"
    )

    st.markdown("### " + ("Percurso sugerido" if st.session_state.lang == "PT" else "Suggested path"))
    if st.session_state.lang == "PT":
        st.write("1. Visão Geral + Q&A")
        st.write("2. Carteiras Móveis")
        st.write("3. Insights Estratégicos / Oportunidades")
        st.write("4. Previsões")
    else:
        st.write("1. Overview + Q&A")
        st.write("2. Mobile Wallets")
        st.write("3. Strategic Insights / Opportunities")
        st.write("4. Forecasts")

    render_page_caveats()

# ==========================================
# PAGE 1: CONTEXTO DEMOGRÁFICO (CENSUS)
# ==========================================
with tab_demo:
    st.title(T("title_demo"))
    st.caption(T("caption_demo"))
    st.caption(tab_story("demo"))
    st.info(T("census_source"))

    # Match census provinces to selected banking provinces (names now align)
    census_filtered = census_df[census_df['Province'].isin(selected_prov)]
    if census_filtered.empty:
        census_filtered = census_df.copy()

    demo_total_pop = census_filtered["Population_Total"].sum()
    demo_urban_share = (census_filtered["Population_Urban"].sum() / demo_total_pop * 100) if demo_total_pop > 0 else 0
    demo_internet_avg = (
        (census_filtered["Internet_Usage_Pct"] * census_filtered["Population_Total"]).sum() / demo_total_pop
        if demo_total_pop > 0 else 0
    )
    d1, d2, d3 = st.columns(3)
    d1.metric("População" if st.session_state.lang == "PT" else "Population", format_compact(demo_total_pop))
    d2.metric("Urbano (%)" if st.session_state.lang == "PT" else "Urban (%)", f"{demo_urban_share:.1f}%")
    d3.metric(
        "Uso de Internet (%)" if st.session_state.lang == "PT" else "Internet Usage (%)",
        f"{demo_internet_avg:.1f}%",
    )
    st.caption(
        (
            "ℹ️ A população nesta secção usa o total do Censo 2017 no recorte geográfico seleccionado "
            "(com Cidade de Maputo agregada em Província de Maputo). Nos indicadores de inclusão financeira, "
            "o denominador pode ser diferente conforme o cenário 15+/18+/21+."
        )
        if st.session_state.lang == "PT"
        else (
            "ℹ️ Population in this section uses Census 2017 totals for the selected geographic scope "
            "(with Cidade de Maputo aggregated into Província de Maputo). Financial inclusion indicators may "
            "use a different denominator depending on the 15+/18+/21+ scenario."
        )
    )

    # --- Population overview bar chart ---
    st.subheader(T("population_by_province"))

    fig_pop = px.bar(
        census_filtered.sort_values('Population_Total', ascending=True),
        y='Province', x='Population_Total', orientation='h',
        color='Population_Total', color_continuous_scale='YlOrRd',
        text=[format_compact(v) for v in census_filtered.sort_values('Population_Total', ascending=True)['Population_Total']],
    )
    fig_pop.update_layout(
        xaxis_title=T("value"), yaxis_title=T("province"),
        coloraxis_showscale=False, height=450
    )
    plot_chart(fig_pop, use_container_width=True)

    # --- Gender + Urban/Rural side by side ---
    demo_col1, demo_col2 = st.columns(2)
    with demo_col1:
        st.subheader(T("gender_split"))
        total_m = census_filtered['Population_Male'].sum()
        total_f = census_filtered['Population_Female'].sum()
        gender_label = T("gender_label")
        fig_gen = px.pie(
            values=[total_m, total_f],
            names=['Homens' if st.session_state.lang == 'PT' else 'Male',
                   'Mulheres' if st.session_state.lang == 'PT' else 'Female'],
            hole=0.4
        )
        plot_chart(fig_gen, use_container_width=True)

    with demo_col2:
        st.subheader(T("urban_rural"))
        total_u = census_filtered['Population_Urban'].sum()
        total_r = census_filtered['Population_Rural'].sum()
        fig_ur = px.pie(
            values=[total_u, total_r],
            names=['Urbano' if st.session_state.lang == 'PT' else 'Urban',
                   'Rural' if st.session_state.lang == 'PT' else 'Rural'],
            hole=0.4
        )
        plot_chart(fig_ur, use_container_width=True)

    # --- Financial Inclusion KPI cards ---
    st.markdown("---")
    st.subheader(
        T("financial_inclusion"),
        help=(
            "Indicadores de inclusão financeira por população elegível. "
            "Prioriza-se a métrica oficial do Banco de Moçambique quando disponível; "
            "na ausência, aplica-se cálculo interno com base no Censo 2017 extrapolado por coorte."
            if st.session_state.lang == "PT"
            else "Financial inclusion indicators per eligible population. "
            "Official Banco de Moçambique metrics are prioritized when available; "
            "otherwise, internal calculation uses Census 2017 cohort extrapolation."
        ),
    )

    # Compute per-capita from the latest year banking data (December snapshot only)
    latest_year = max(all_years)
    latest_acc = acc_df[acc_df['Year'] == latest_year]
    latest_card = card_df[card_df['Year'] == latest_year]
    latest_atm = atm_df[atm_df['Year'] == latest_year]
    latest_pos = pos_df[pos_df['Year'] == latest_year]

    # Use strict December snapshot to avoid 12x inflation on stock metrics
    latest_acc = last_month_snapshot(latest_acc)
    latest_card = last_month_snapshot(latest_card)
    latest_atm = last_month_snapshot(latest_atm)
    latest_pos = last_month_snapshot(latest_pos)

    total_pop = denominator_population(census_filtered, latest_year)
    total_acc_latest = latest_acc['Total_Accounts'].sum()
    total_card_latest = latest_card['Total_Cards'].sum()
    total_atm_latest = latest_atm['ATMs_Number'].sum()
    total_pos_latest = latest_pos['POSs_Number'].sum()

    official_metrics, official_period = official_inclusion_metrics(latest_year)
    use_official = all(official_metrics[k] is not None for k in ["accounts_per_capita", "cards_per_capita", "atm_per_100k", "pos_per_100k"])

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    if use_official:
        kpi1.metric(T("accounts_per_capita"), f"{official_metrics['accounts_per_capita']:.2f}")
        kpi2.metric(T("cards_per_capita"), f"{official_metrics['cards_per_capita']:.2f}")
        kpi3.metric(T("atm_per_100k"), f"{official_metrics['atm_per_100k']:.1f}")
        kpi4.metric(T("pos_per_100k"), f"{official_metrics['pos_per_100k']:.1f}")
        st.caption(
            (
                f"ℹ️ Indicadores oficiais do Banco de Moçambique (nacional) — período {official_period or latest_year}. "
                "Estes cartões não variam com filtros geográficos."
            )
            if st.session_state.lang == "PT"
            else (
                f"ℹ️ Official Banco de Moçambique indicators (national) — period {official_period or latest_year}. "
                "These cards do not vary by geographic filters."
            )
        )
        st.caption(
            (
                "ℹ️ Regra de período: usa-se o valor anual quando disponível; caso contrário, usa-se o último trimestre publicado."
            )
            if st.session_state.lang == "PT"
            else (
                "ℹ️ Period rule: annual value is used when available; otherwise, the latest published quarter is used."
            )
        )
    else:
        kpi1.metric(T("accounts_per_capita"), f"{total_acc_latest / total_pop:.2f}" if total_pop > 0 else "N/A")
        kpi2.metric(T("cards_per_capita"), f"{total_card_latest / total_pop:.2f}" if total_pop > 0 else "N/A")
        kpi3.metric(T("atm_per_100k"), f"{total_atm_latest / total_pop * 100_000:.1f}" if total_pop > 0 else "N/A")
        kpi4.metric(T("pos_per_100k"), f"{total_pos_latest / total_pop * 100_000:.1f}" if total_pop > 0 else "N/A")
        st.caption(
            (
                "ℹ️ Fallback metodológico: na ausência de indicador oficial para o período, os cartões são calculados com "
                "dados bancários reportados (contas, cartões, ATM e POS) e com denominador de população elegível "
                "extrapolado do Censo 2017 por progressão de coorte etária."
            )
            if st.session_state.lang == "PT"
            else (
                "ℹ️ Methodological fallback: when the official indicator is unavailable for the period, cards are computed "
                "from reported banking data (accounts, cards, ATM, POS) and an eligible-population denominator "
                "extrapolated from Census 2017 using age-cohort progression."
            )
        )
        st.caption(f"ℹ️ {inclusion_method_note(latest_year)}")

    st.markdown("###### " + ("Inclusão por género e idade (último ano)" if st.session_state.lang == "PT" else "Gender and age inclusion lens (latest year)"))
    female_acc_share = (
        latest_acc[latest_acc["Gender"] == "Mulheres"]["Total_Accounts"].sum() / total_acc_latest * 100
        if total_acc_latest > 0 else 0
    )
    female_card_share = (
        latest_card[latest_card["Gender"] == "Mulheres"]["Total_Cards"].sum() / total_card_latest * 100
        if total_card_latest > 0 else 0
    )
    youth_acc_share = (
        latest_acc[latest_acc["Age"] == "17-21"]["Total_Accounts"].sum() / total_acc_latest * 100
        if total_acc_latest > 0 else 0
    )
    youth_card_share = (
        latest_card[latest_card["Age"] == "17-21"]["Total_Cards"].sum() / total_card_latest * 100
        if total_card_latest > 0 else 0
    )
    ig1, ig2, ig3, ig4 = st.columns(4)
    ig1.metric("Quota feminina (contas)" if st.session_state.lang == "PT" else "Female share (accounts)", f"{female_acc_share:.1f}%")
    ig2.metric("Quota feminina (cartões)" if st.session_state.lang == "PT" else "Female share (cards)", f"{female_card_share:.1f}%")
    ig3.metric("Faixa 17-21 (contas)" if st.session_state.lang == "PT" else "Age 17-21 (accounts)", f"{youth_acc_share:.1f}%")
    ig4.metric("Faixa 17-21 (cartões)" if st.session_state.lang == "PT" else "Age 17-21 (cards)", f"{youth_card_share:.1f}%")

    age_cols = st.columns(2)
    with age_cols[0]:
        age_acc_ctx = latest_acc[latest_acc["Age"].isin(["0-16", "17-21", "22-60", "+60"])]
        if not age_acc_ctx.empty:
            age_acc_ctx = age_acc_ctx.groupby("Age", observed=False)["Total_Accounts"].sum().reset_index()
            age_acc_ctx["Share"] = age_acc_ctx["Total_Accounts"] / age_acc_ctx["Total_Accounts"].sum() * 100
            fig_age_acc_ctx = px.bar(
                age_acc_ctx,
                x="Age",
                y="Share",
                text=[f"{v:.1f}%" for v in age_acc_ctx["Share"]],
                title="Contas por faixa etária (%)" if st.session_state.lang == "PT" else "Accounts by age group (%)",
            )
            fig_age_acc_ctx.update_layout(yaxis_title="%")
            plot_chart(fig_age_acc_ctx, use_container_width=True)
    with age_cols[1]:
        age_card_ctx = latest_card[latest_card["Age"].isin(["0-16", "17-21", "22-60", "+60"])]
        if not age_card_ctx.empty:
            age_card_ctx = age_card_ctx.groupby("Age", observed=False)["Total_Cards"].sum().reset_index()
            age_card_ctx["Share"] = age_card_ctx["Total_Cards"] / age_card_ctx["Total_Cards"].sum() * 100
            fig_age_card_ctx = px.bar(
                age_card_ctx,
                x="Age",
                y="Share",
                text=[f"{v:.1f}%" for v in age_card_ctx["Share"]],
                title="Cartões por faixa etária (%)" if st.session_state.lang == "PT" else "Cards by age group (%)",
            )
            fig_age_card_ctx.update_layout(yaxis_title="%")
            plot_chart(fig_age_card_ctx, use_container_width=True)

    # --- Underbanked Gap: Population vs Accounts per province ---
    st.markdown("---")
    st.subheader(T("underbanked_gap"))

    gap_rows = []
    for _, row in census_filtered.iterrows():
        prov_name = row['Province']
        # Province names now align between census and banking data
        prov_acc = latest_acc[latest_acc['Province'] == prov_name]
        total_a = prov_acc['Total_Accounts'].sum() if not prov_acc.empty else 0
        row_pop = row_denominator_population(row, latest_year)
        gap_rows.append({
            T("province"): prov_name,
            'Population (Denominator)': row_pop,
            f'{T("total_accounts")} ({latest_year})': total_a,
            T("accounts_per_capita"): round(total_a / row_pop, 3) if row_pop > 0 else 0
        })

    gap_df = pd.DataFrame(gap_rows).sort_values(T("accounts_per_capita"), ascending=False)

    # Per capita bar chart
    fig_pc = px.bar(
        gap_df, x=T("province"), y=T("accounts_per_capita"),
        color=T("accounts_per_capita"), color_continuous_scale='YlOrRd',
        text=[f"{v:.2f}" for v in gap_df[T("accounts_per_capita")]],
    )
    fig_pc.update_layout(
        title=T("accounts_per_capita"),
        yaxis_title=T("accounts_per_capita"),
        coloraxis_showscale=False, height=400
    )
    plot_chart(fig_pc, use_container_width=True)

    # --- Gender Parity Index ---
    st.markdown("---")
    st.subheader(T("gender_parity"))
    st.markdown(T("gender_parity_desc"))

    gpi_rows = []
    for _, row in census_filtered.iterrows():
        prov_name = row['Province']
        prov_acc_data = latest_acc[latest_acc['Province'] == prov_name]
        if not prov_acc_data.empty:
            female_acc = prov_acc_data[prov_acc_data['Gender'] == 'Mulheres']['Total_Accounts'].sum()
            total_a = prov_acc_data['Total_Accounts'].sum()
            female_acc_share = female_acc / total_a if total_a > 0 else 0
            female_pop_share = row['Population_Female'] / row['Population_Total'] if row['Population_Total'] > 0 else 0
            gpi = female_acc_share / female_pop_share if female_pop_share > 0 else 0
            gpi_rows.append({
                T("province"): prov_name,
                T("gender_parity"): round(gpi, 3)
            })

    if gpi_rows:
        gpi_df = pd.DataFrame(gpi_rows).sort_values(T("gender_parity"), ascending=False)
        fig_gpi = px.bar(
            gpi_df, x=T("province"), y=T("gender_parity"),
            color=T("gender_parity"), color_continuous_scale='RdYlGn',
            text=[f"{v:.2f}" for v in gpi_df[T("gender_parity")]],
        )
        fig_gpi.add_hline(y=1.0, line_dash="dash", line_color="grey",
                          annotation_text="Paridade" if st.session_state.lang == 'PT' else "Parity")
        fig_gpi.update_layout(coloraxis_showscale=False, height=400)
        plot_chart(fig_gpi, use_container_width=True)

    # --- Connectivity context: Phone/Internet vs Digital Banking ---
    st.markdown("---")
    st.subheader(T("connectivity_context"), help=T("connectivity_desc"))

    conn_col1, conn_col2 = st.columns(2)
    with conn_col1:
        fig_phone = px.bar(
            census_filtered.sort_values('Phone_Ownership_Pct', ascending=True),
            y='Province', x='Phone_Ownership_Pct', orientation='h',
            color='Phone_Ownership_Pct', color_continuous_scale='Blues',
            text=[f"{v:.1f}%" for v in census_filtered.sort_values('Phone_Ownership_Pct', ascending=True)['Phone_Ownership_Pct']],
            title=T("phone_vs_mobile_banking")
        )
        fig_phone.update_layout(xaxis_title="%", coloraxis_showscale=False, height=400)
        plot_chart(fig_phone, use_container_width=True)

    with conn_col2:
        fig_internet = px.bar(
            census_filtered.sort_values('Internet_Usage_Pct', ascending=True),
            y='Province', x='Internet_Usage_Pct', orientation='h',
            color='Internet_Usage_Pct', color_continuous_scale='Purples',
            text=[f"{v:.1f}%" for v in census_filtered.sort_values('Internet_Usage_Pct', ascending=True)['Internet_Usage_Pct']],
            title=T("internet_vs_internet_banking")
        )
        fig_internet.update_layout(xaxis_title="%", coloraxis_showscale=False, height=400)
        plot_chart(fig_internet, use_container_width=True)

    st.caption(T("census_note_short"))
    render_page_caveats()


# ==========================================
# PAGE 2: VISÃO GERAL
# ==========================================
with tab_overview:
    st.title(T("title_overview"))
    st.caption(T("caption_overview"))
    st.caption(tab_story("overview"))

    opp_df_overview = build_scope_opportunity_df(selected_year)

    ime_sub_years_ov = set(pd.to_numeric(ime_sub_df["Year"], errors="coerce").dropna().astype(int).tolist()) if not ime_sub_df.empty else set()
    ime_agents_years_ov = set(pd.to_numeric(ime_agents_df["Year"], errors="coerce").dropna().astype(int).tolist()) if not ime_agents_df.empty else set()
    ime_years_overview = sorted(ime_sub_years_ov & ime_agents_years_ov)
    ime_overview_available = selected_year in ime_years_overview
    wallet_subs_total = None
    wallet_agents_total = None
    if ime_overview_available:
        ime_sub_scope = apply_geo_only(ime_sub_df[ime_sub_df["Year"] == selected_year].copy())
        ime_sub_scope = ime_sub_scope[ime_sub_scope["Month"].astype(str) == "Dezembro"]
        if not ime_sub_scope.empty:
            wallet_subs_total = float(ime_sub_scope["Subscribers"].sum())
        ime_agents_scope = apply_geo_only(ime_agents_df[ime_agents_df["Year"] == selected_year].copy())
        ime_agents_scope = ime_agents_scope[ime_agents_scope["Month"].astype(str) == "Dezembro"]
        if not ime_agents_scope.empty:
            wallet_agents_total = float(ime_agents_scope["Agents"].sum())

    mobile_value_total = float(
        mob_df[
            (mob_df["Year"] == selected_year)
            & (mob_df["Metric"].astype(str).str.contains("Valor", case=False, na=False))
        ]["Value"].sum()
    )
    internet_value_total = float(
        net_df[
            (net_df["Year"] == selected_year)
            & (net_df["Metric"].astype(str).str.contains("Valor", case=False, na=False))
        ]["Value"].sum()
    )
    official_metrics, official_period = official_inclusion_metrics(selected_year)
    accounts_pc_off = official_metrics.get("accounts_per_capita")
    top_opp_label = (
        f"{opp_df_overview.iloc[0]['Province']} ({opp_df_overview.iloc[0]['Opportunity_Score']:.1f})"
        if not opp_df_overview.empty
        else ("N/A")
    )

    ov1, ov2, ov3 = st.columns(3)
    ov4, ov5, ov6 = st.columns(3)
    metric_with_help(
        ov1,
        "Subscrições de Carteira Móvel" if st.session_state.lang == "PT" else "Mobile Wallet subscriptions",
        "N/A" if wallet_subs_total is None else format_compact(wallet_subs_total),
        help_pt="Total de subscrições reportadas no recorte seleccionado.",
        help_en="Total reported subscriptions in the selected scope.",
    )
    metric_with_help(
        ov2,
        "Agentes de Carteira Móvel" if st.session_state.lang == "PT" else "Mobile Wallet agents",
        "N/A" if wallet_agents_total is None else format_compact(wallet_agents_total),
        help_pt="Total de agentes reportados no recorte seleccionado.",
        help_en="Total reported agents in the selected scope.",
    )
    metric_with_help(
        ov3,
        "Mobile Banking (Valor)" if st.session_state.lang == "PT" else "Mobile Banking (Value)",
        format_compact(mobile_value_total),
        help_pt="Valor anual agregado das transacções de Mobile Banking.",
        help_en="Annual aggregated transaction value for Mobile Banking.",
    )
    metric_with_help(
        ov4,
        "Internet Banking (Valor)" if st.session_state.lang == "PT" else "Internet Banking (Value)",
        format_compact(internet_value_total),
        help_pt="Valor anual agregado das transacções de Internet Banking.",
        help_en="Annual aggregated transaction value for Internet Banking.",
    )
    metric_with_help(
        ov5,
        "Contas por adulto (oficial)" if st.session_state.lang == "PT" else "Accounts per adult (official)",
        "N/A" if accounts_pc_off is None else f"{accounts_pc_off:.2f}",
        help_pt="Indicador oficial do Banco de Moçambique (por 100 adultos), convertido para per capita.",
        help_en="Official Banco de Moçambique indicator (per 100 adults), converted to per-capita.",
    )
    metric_with_help(
        ov6,
        "Província líder (oportunidade)" if st.session_state.lang == "PT" else "Top opportunity province",
        top_opp_label,
        help_pt="Província com maior pontuação no índice de oportunidade.",
        help_en="Province with the highest opportunity-score ranking.",
    )
    if not ime_overview_available:
        st.info(
            "Dados de Carteira Móvel indisponíveis para o ano seleccionado."
            if st.session_state.lang == "PT"
            else "Mobile Wallet data is unavailable for the selected year."
        )

    st.caption(
        (
            f"Indicador oficial de inclusão: período {official_period}."
            if official_period
            else "Indicador oficial de inclusão indisponível para o período seleccionado."
        )
        if st.session_state.lang == "PT"
        else (
            f"Official inclusion indicator period: {official_period}."
            if official_period
            else "Official inclusion indicator unavailable for the selected period."
        )
    )

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        mob_series = (
            mob_df[mob_df["Metric"].astype(str).str.contains("Valor", case=False, na=False)]
            .groupby("Year", as_index=False)["Value"]
            .sum()
            .rename(columns={"Value": "Mobile"})
        )
        net_series = (
            net_df[net_df["Metric"].astype(str).str.contains("Valor", case=False, na=False)]
            .groupby("Year", as_index=False)["Value"]
            .sum()
            .rename(columns={"Value": "Internet"})
        )
        trend_df = pd.merge(mob_series, net_series, on="Year", how="outer").fillna(0).sort_values("Year")
        trend_long = trend_df.melt(id_vars=["Year"], value_vars=["Mobile", "Internet"], var_name="Channel", value_name="Value")
        fig_ov_trend = px.line(
            trend_long,
            x="Year",
            y="Value",
            color="Channel",
            markers=True,
            title=(
                "Tendência de valor: Mobile vs Internet Banking"
                if st.session_state.lang == "PT"
                else "Value trend: Mobile vs Internet Banking"
            ),
        )
        fig_ov_trend.update_layout(xaxis=dict(dtick=1), yaxis=dict(rangemode="tozero"))
        plot_chart(fig_ov_trend, use_container_width=True)

    with chart_col2:
        if opp_df_overview.empty:
            st.info("Sem dados de oportunidade no recorte actual." if st.session_state.lang == "PT" else "No opportunity data in current scope.")
        else:
            top5_opp = opp_df_overview.head(5).copy()
            fig_ov_opp = px.bar(
                top5_opp,
                x="Province",
                y="Opportunity_Score",
                text=[f"{v:.1f}" for v in top5_opp["Opportunity_Score"]],
                title=(
                    "Top 5 províncias por oportunidade"
                    if st.session_state.lang == "PT"
                    else "Top 5 provinces by opportunity"
                ),
            )
            fig_ov_opp.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-20)
            plot_chart(fig_ov_opp, use_container_width=True)

    st.markdown("---")
    st.subheader(
        "Relação Banca ↔ Carteira Móvel" if st.session_state.lang == "PT" else "Banking ↔ Mobile Wallet Relationship",
        help=(
            "Compara transferências de Mobile Banking para telemóveis com levantamentos ATM de fundos depositados em telemóveis."
            if st.session_state.lang == "PT"
            else "Compares Mobile Banking transfers to mobile numbers against ATM withdrawals of mobile-wallet funds."
        ),
    )
    st.caption(
        "Leitura nacional agregada para acompanhar sinal de entrada (bank-to-wallet) e saída (wallet-to-cash)."
        if st.session_state.lang == "PT"
        else "National aggregate view to track inflow (bank-to-wallet) and outflow (wallet-to-cash) signals."
    )

    bridge_annual = build_wallet_bridge_annual()
    if bridge_annual.empty:
        st.info(
            "Sem histórico suficiente para análise de relação entre canais."
            if st.session_state.lang == "PT"
            else "Insufficient history for cross-channel relationship analysis."
        )
    else:
        bridge_row = bridge_annual[bridge_annual["Year"] == selected_year]
        if bridge_row.empty:
            bridge_row = bridge_annual.tail(1)
        bridge_row = bridge_row.iloc[0]

        bridge_m1, bridge_m2, bridge_m3 = st.columns(3)
        metric_with_help(
            bridge_m1,
            "Transferências Mobile Banking → telemóveis (valor)" if st.session_state.lang == "PT" else "Mobile Banking transfers → mobile (value)",
            format_compact(float(bridge_row["MB_To_Wallet_Value"])),
            help_pt="Valor anual transferido de Mobile Banking para telemóveis.",
            help_en="Annual value transferred from Mobile Banking to mobile numbers.",
        )
        metric_with_help(
            bridge_m2,
            "Levantamentos ATM de fundos em telemóveis (valor)" if st.session_state.lang == "PT" else "ATM withdrawals of mobile-wallet funds (value)",
            format_compact(float(bridge_row["ATM_Wallet_Withdrawals_Value"])),
            help_pt="Valor anual levantado em ATM a partir de fundos depositados em telemóveis.",
            help_en="Annual ATM withdrawal value from funds deposited in mobile-wallet accounts.",
        )
        cashout_ratio = (
            float(bridge_row["ATM_Wallet_Withdrawals_Value"]) / float(bridge_row["MB_To_Wallet_Value"])
            if float(bridge_row["MB_To_Wallet_Value"]) > 0
            else math.nan
        )
        metric_with_help(
            bridge_m3,
            "Rácio saída/entrada" if st.session_state.lang == "PT" else "Outflow/inflow ratio",
            "N/A" if math.isnan(cashout_ratio) else f"{cashout_ratio:.2f}x",
            help_pt="Relação entre levantamentos ATM (saída) e transferências Mobile Banking para telemóveis (entrada).",
            help_en="Ratio between ATM withdrawals (outflow) and Mobile Banking transfers to mobile numbers (inflow).",
        )

        bridge_value_opt = "Valor" if st.session_state.lang == "PT" else "Value"
        bridge_volume_opt = "Volume"
        bridge_metric_view = single_choice_toggle(
            "Métrica da série" if st.session_state.lang == "PT" else "Series metric",
            [bridge_value_opt, bridge_volume_opt],
            key="overview_bridge_metric_toggle",
        )

        if bridge_metric_view == bridge_value_opt:
            bridge_long = bridge_annual.melt(
                id_vars=["Year"],
                value_vars=["MB_To_Wallet_Value", "ATM_Wallet_Withdrawals_Value"],
                var_name="Metric",
                value_name="Value",
            )
            chart_title = "Série anual (valor)" if st.session_state.lang == "PT" else "Annual series (value)"
            metric_labels = {
                "MB_To_Wallet_Value": "Mobile Banking → telemóveis" if st.session_state.lang == "PT" else "Mobile Banking → mobile",
                "ATM_Wallet_Withdrawals_Value": (
                    "Levantamentos ATM (fundos em telemóveis)"
                    if st.session_state.lang == "PT"
                    else "ATM withdrawals (mobile-wallet funds)"
                ),
            }
        else:
            bridge_long = bridge_annual.melt(
                id_vars=["Year"],
                value_vars=["MB_To_Wallet_Volume", "ATM_Wallet_Withdrawals_Volume"],
                var_name="Metric",
                value_name="Value",
            )
            chart_title = "Série anual (volume)" if st.session_state.lang == "PT" else "Annual series (volume)"
            metric_labels = {
                "MB_To_Wallet_Volume": "Mobile Banking → telemóveis" if st.session_state.lang == "PT" else "Mobile Banking → mobile",
                "ATM_Wallet_Withdrawals_Volume": (
                    "Levantamentos ATM (fundos em telemóveis)"
                    if st.session_state.lang == "PT"
                    else "ATM withdrawals (mobile-wallet funds)"
                ),
            }

        bridge_long["Metric"] = bridge_long["Metric"].map(metric_labels)
        fig_bridge = px.line(
            bridge_long,
            x="Year",
            y="Value",
            color="Metric",
            markers=True,
            title=chart_title,
        )
        fig_bridge.update_layout(xaxis=dict(dtick=1), yaxis=dict(rangemode="tozero"), height=460)
        plot_chart(fig_bridge, use_container_width=True)

        st.caption(
            "Nota: a leitura mostra co-movimento estatístico entre séries; não estabelece relação causal."
            if st.session_state.lang == "PT"
            else "Note: this is a statistical co-movement reading between series; it does not establish causality."
        )

    st.markdown("---")
    render_deterministic_qa_panel(opp_df=opp_df_overview, key_prefix="overview")
    render_page_caveats()

# ==========================================
# PAGE 3: CARTEIRAS MÓVEIS
# ==========================================
with tab_ime:
    st.title(T("title_ime"))
    st.caption(T("caption_ime"))
    st.caption(tab_story("ime"))

    mobile_context_pt = (
        "ℹ️ Os indicadores das carteiras móveis incluem utilizadores de M-Pesa, mKesh, e-Mola e Conta Móvel. "
        "Como as plataformas são contabilizadas por conta/serviço, "
        "uma mesma pessoa pode ter registo em mais de uma plataforma."
    )
    mobile_context_en = (
        "ℹ️ Methodological context (Mozambique): Mobile Wallet indicators include users from "
        "M-Pesa, mKesh, e-Mola, and Conta Móvel. As platforms are counted by account/service, "
        "the same person may be registered in more than one platform."
    )
    st.info(mobile_context_pt if st.session_state.lang == "PT" else mobile_context_en)
    st.caption(
        (
            "ℹ️ Base de denominador (quando aplicável): Censo distrital 2017 (15+) com extrapolação por coorte a partir da estrutura provincial; "
            "Cidade de Maputo está harmonizada em Província de Maputo; subscrições representam serviços (não pessoas únicas)."
        )
        if st.session_state.lang == "PT"
        else (
            "ℹ️ Denominator basis (when applicable): district Census 2017 (15+) with cohort extrapolation from province age structure; "
            "Cidade de Maputo is harmonized under Província de Maputo; subscriptions represent services (not unique people)."
        )
    )

    if ime_sub_df.empty or ime_agents_df.empty or ime_txn_district_df.empty:
        st.warning(
            "Ficheiros de Carteira Móvel não encontrados. Executar: python etl.py --export-ime"
            if st.session_state.lang == "PT"
            else "Mobile Wallet files not found. Run: python etl.py --export-ime"
        )
    else:
        sub_years = set(pd.to_numeric(ime_sub_df["Year"], errors="coerce").dropna().astype(int).tolist())
        ag_years = set(pd.to_numeric(ime_agents_df["Year"], errors="coerce").dropna().astype(int).tolist())
        tx_years = set(pd.to_numeric(ime_txn_district_df["Year"], errors="coerce").dropna().astype(int).tolist())
        ime_year_options = sorted(sub_years & ag_years & tx_years)
        if not ime_year_options:
            ime_year_options = sorted(sub_years or ag_years or tx_years)
        ime_year = selected_year
        ime_year_available = ime_year in ime_year_options
        st.caption(
            f"ℹ️ Série distrital de Carteira Móvel disponível para {ime_year_options[0]}-{ime_year_options[-1]}. "
            + (
                f"A visualização usa o ano seleccionado na barra lateral ({ime_year})."
                if st.session_state.lang == "PT"
                else f"The view uses the sidebar-selected year ({ime_year})."
            )
        )
        if not ime_year_available:
            st.info(
                "Dados de Carteira Móvel indisponíveis para o ano seleccionado."
                if st.session_state.lang == "PT"
                else "Mobile Wallet data is unavailable for the selected year."
            )

        sub_year = ime_sub_df[ime_sub_df["Year"] == ime_year].copy()
        ag_year = ime_agents_df[ime_agents_df["Year"] == ime_year].copy()
        tx_year = ime_txn_district_df[ime_txn_district_df["Year"] == ime_year].copy()

        if ime_year_available:
            control_c1, control_c2 = st.columns(2)
            with control_c1:
                month_label = "Mês (Carteira Móvel)" if st.session_state.lang == "PT" else "Month (Mobile Wallet)"
                all_months_label = "Todos" if st.session_state.lang == "PT" else "All"
                month_values = sub_year["Month"].dropna()
                available_months = (
                    sorted(
                        month_values.astype(str).unique().tolist(),
                        key=lambda m: month_to_num(m),
                    )
                    if not month_values.empty
                    else []
                )
                month_display_to_raw = {localize_month(m): m for m in available_months}
                month_options_display = [all_months_label] + [localize_month(m) for m in available_months]
                ime_month_pick = st.selectbox(
                    month_label,
                    month_options_display,
                    index=0,
                    key="ime_page_month",
                )
                ime_month = None if ime_month_pick == all_months_label else month_display_to_raw.get(ime_month_pick, ime_month_pick)
            with control_c2:
                measure_label = "Métrica de transacção" if st.session_state.lang == "PT" else "Transaction metric"
                ime_measure = st.selectbox(
                    measure_label,
                    [T("value"), T("volume")],
                    index=0,
                    key="ime_page_measure",
                )
    
            available_prov = sorted(sub_year["Province"].dropna().astype(str).unique().tolist())
            ime_prov = [p for p in selected_prov if p in available_prov]
            if not ime_prov:
                ime_prov = available_prov
    
            available_dist = sorted(
                sub_year[sub_year["Province"].isin(ime_prov)]["District"].dropna().astype(str).unique().tolist()
            )
            selected_dist_valid = [d for d in (selected_dist or []) if d in available_dist]
            ime_dist = selected_dist_valid
            if not ime_dist:
                ime_dist = available_dist
            use_district_axis = len(selected_dist_valid) > 0
            all_month_fallback = (
                "Dezembro" if "Dezembro" in available_months else (available_months[-1] if available_months else None)
            )
            # Note to self: 'Todos' is for trends; stock KPIs/rankings must still anchor to one month (December first).
    
            tx_metric_col = "Value" if ime_measure == T("value") else "Volume"
    
            st.caption(
                (
                    f"Filtros aplicados: {len(ime_prov)} província(s), "
                    + (
                        (
                            f"{len(ime_dist)} distrito(s), mês: {localize_month(ime_month)}."
                            if ime_month is not None
                            else (
                                f"{len(ime_dist)} distrito(s), mês: todos (KPIs/rankings usam {localize_month(all_month_fallback)})."
                                if all_month_fallback is not None
                                else f"{len(ime_dist)} distrito(s), mês: todos."
                            )
                        )
                    )
                )
                if st.session_state.lang == "PT"
                else (
                    f"Applied filters: {len(ime_prov)} province(s), "
                    + (
                        (
                            f"{len(ime_dist)} district(s), month: {localize_month(ime_month)}."
                            if ime_month is not None
                            else (
                                f"{len(ime_dist)} district(s), month: all (KPIs/rankings use {localize_month(all_month_fallback)})."
                                if all_month_fallback is not None
                                else f"{len(ime_dist)} district(s), month: all."
                            )
                        )
                    )
                )
            )
    
            def _ime_geo_filter(df: pd.DataFrame) -> pd.DataFrame:
                out = df[df["Province"].isin(ime_prov)].copy()
                if "District" in out.columns:
                    out = out[out["District"].isin(ime_dist)]
                return out
    
            sub_geo = _ime_geo_filter(sub_year)
            ag_geo = _ime_geo_filter(ag_year)
            tx_geo = _ime_geo_filter(tx_year)
            tx_all_geo = _ime_geo_filter(ime_txn_district_df.copy())
    
            effective_month_ref = (
                ime_month
                if ime_month is not None else all_month_fallback
            )
            if effective_month_ref is not None:
                tx_month = tx_geo[tx_geo["Month"].astype(str) == effective_month_ref].copy()
            else:
                tx_month = tx_geo.copy()
    
            stock_month_ref = effective_month_ref
            sub_stock = (
                sub_geo[sub_geo["Month"].astype(str) == stock_month_ref].copy()
                if stock_month_ref is not None
                else pd.DataFrame(columns=sub_geo.columns)
            )
            ag_stock = (
                ag_geo[ag_geo["Month"].astype(str) == stock_month_ref].copy()
                if stock_month_ref is not None
                else pd.DataFrame(columns=ag_geo.columns)
            )
    
            subs_total = sub_stock["Subscribers"].sum() if "Subscribers" in sub_stock.columns else 0
            agents_total = ag_stock["Agents"].sum() if "Agents" in ag_stock.columns else 0
            denom_scope_df = build_census_district_denominator_df(
                ime_year,
                provinces=ime_prov if ime_prov else None,
                districts=ime_dist if ime_dist else None,
            )
            eligible_scope_total = float(
                pd.to_numeric(denom_scope_df.get("Eligible_Population", pd.Series(dtype=float)), errors="coerce")
                .fillna(0.0)
                .sum()
            )
            wallet_pen_scope = ((subs_total / eligible_scope_total) * 100) if eligible_scope_total > 0 else math.nan
            tx_types = ["Depósitos", "Levantamentos", "Transferências", "Pagamentos"]
            tx_totals = {
                t: float(tx_month.loc[tx_month["Transaction_Type"] == t, tx_metric_col].sum()) for t in tx_types
            }
            tx_type_labels = {
                "Depósitos": ("Depósitos", "Deposits"),
                "Levantamentos": ("Levantamentos", "Withdrawals"),
                "Transferências": ("Transferências", "Transfers"),
                "Pagamentos": ("Pagamentos", "Payments"),
            }
            tx_help_en = {
                "Depósitos": "Money deposited into Mobile Wallet agent accounts.",
                "Levantamentos": "Money withdrawals from Mobile Wallet.",
                "Transferências": "Transfers between Mobile Wallet accounts.",
                "Pagamentos": "Service payments using Mobile Wallet.",
            }
            tx_help_pt = {
                "Depósitos": "Dinheiro depositado em contas de agente de Carteira Móvel.",
                "Levantamentos": "Levantamento de dinheiro a partir da Carteira Móvel.",
                "Transferências": "Transferências entre contas de Carteira Móvel.",
                "Pagamentos": "Pagamento de serviços com Carteira Móvel.",
            }
    
            def _metric_with_optional_help(col, tx_key: str) -> None:
                pt_label, en_label = tx_type_labels[tx_key]
                label = f"{pt_label if st.session_state.lang == 'PT' else en_label} ({ime_measure})"
                value = format_compact(tx_totals[tx_key])
                metric_with_help(
                    col,
                    label,
                    value,
                    help_pt=tx_help_pt[tx_key],
                    help_en=tx_help_en[tx_key],
                )
    
            if stock_month_ref is None:
                st.info(
                    "Sem dados de Dezembro para indicadores de stock (Subscrições/Agentes)."
                    if st.session_state.lang == "PT"
                    else "No December data found for stock indicators (Subscriptions/Agents)."
                )
    
            k1, k2, k3 = st.columns(3)
            k4, k5, k6 = st.columns(3)
            metric_with_help(
                k1,
                "Subscrições" if st.session_state.lang == "PT" else "Subscriptions",
                format_compact(subs_total),
                help_pt="Número de subscrições de Carteira Móvel reportadas no período.",
                help_en="Number of Mobile Wallet subscriptions reported in the period.",
            )
            metric_with_help(
                k2,
                "Agentes" if st.session_state.lang == "PT" else "Agents",
                format_compact(agents_total),
                help_pt="Número de agentes de Carteira Móvel reportados no período.",
                help_en="Number of Mobile Wallet agents reported in the period.",
            )
            _metric_with_optional_help(k3, "Depósitos")
            _metric_with_optional_help(k4, "Levantamentos")
            _metric_with_optional_help(k5, "Transferências")
            _metric_with_optional_help(k6, "Pagamentos")
            st.caption(
                (
                    f"ℹ️ Subscrições e Agentes (stock) usam o valor reportado em {localize_month(stock_month_ref)}."
                    if stock_month_ref is not None
                    else "ℹ️ Subscrições e Agentes (stock) sem mês de referência disponível."
                )
                if st.session_state.lang == "PT"
                else (
                    f"ℹ️ Subscriptions and Agents (stock) use the reported value from {localize_month(stock_month_ref)}."
                    if stock_month_ref is not None
                    else "ℹ️ Subscriptions and Agents (stock) have no reference month available."
                )
            )
            st.caption(
                (
                    f"ℹ️ Penetração no recorte (subscrições por 100 elegíveis): {wallet_pen_scope:.1f}."
                    if not math.isnan(wallet_pen_scope)
                    else "ℹ️ Penetração no recorte indisponível (denominador distrital ausente para os filtros)."
                )
                if st.session_state.lang == "PT"
                else (
                    f"ℹ️ In-scope penetration (subscriptions per 100 eligible): {wallet_pen_scope:.1f}."
                    if not math.isnan(wallet_pen_scope)
                    else "ℹ️ In-scope penetration unavailable (district denominator missing for current filters)."
                )
            )
    
            st.markdown("---")
            st.subheader(
                "Baseline de mercado móvel (INCM)"
                if st.session_state.lang == "PT"
                else "Mobile market baseline (INCM)",
                help=(
                    "INCM, 2025 T2: total de subscrições móveis por província. "
                    "Usado como contexto de mercado para leitura de intensidade relativa IME/INCM. "
                    "Subscrições representam subscrições de serviço (não pessoas únicas)."
                    if st.session_state.lang == "PT"
                    else "INCM, 2025 Q2: total mobile subscriptions by province. "
                    "Used as market context for IME/INCM relative intensity reading. "
                    "Reported totals represent service subscriptions (not unique people)."
                ),
            )
            st.caption(
                f"[INCM Acervo]({INCM_SOURCE_TELECOM_URL}) · "
                + (
                    "Período de referência: 2025 T2."
                    if st.session_state.lang == "PT"
                    else "Reference period: 2025 Q2."
                )
            )
    
            incm_scope = INCM_MOBILE_SUBSCRIBERS_Q2_2025.copy()
            if selected_prov:
                incm_scope = incm_scope[incm_scope["Province"].isin(selected_prov)]
            if not incm_scope.empty:
                fig_incm = px.bar(
                    incm_scope.sort_values("Mobile_Subscribers", ascending=False),
                    x="Province",
                    y="Mobile_Subscribers",
                    text=[format_compact(v) for v in incm_scope.sort_values("Mobile_Subscribers", ascending=False)["Mobile_Subscribers"]],
                    title=(
                        "Total de subscrições móveis por província (INCM)"
                        if st.session_state.lang == "PT"
                        else "Total mobile subscriptions by province (INCM)"
                    ),
                )
                fig_incm.update_layout(xaxis_tickangle=-20, yaxis=dict(rangemode="tozero"), height=360)
                plot_chart(fig_incm, use_container_width=True)
            else:
                st.info(
                    "Sem dados INCM no recorte geográfico actual."
                    if st.session_state.lang == "PT"
                    else "No INCM data for current geographic scope."
                )
    
            ratio_month_ref = stock_month_ref
            if ratio_month_ref is not None:
                sub_prov_ref = (
                    sub_year[(sub_year["Province"].isin(ime_prov)) & (sub_year["Month"].astype(str) == ratio_month_ref)]
                    .groupby("Province", as_index=False)["Subscribers"]
                    .sum()
                )
                ag_prov_ref = (
                    ag_year[(ag_year["Province"].isin(ime_prov)) & (ag_year["Month"].astype(str) == ratio_month_ref)]
                    .groupby("Province", as_index=False)["Agents"]
                    .sum()
                )
                tx_prov_ref = (
                    tx_year[(tx_year["Province"].isin(ime_prov)) & (tx_year["Month"].astype(str) == ratio_month_ref)]
                    .groupby("Province", as_index=False)
                    .agg(Tx_Value=("Value", "sum"), Tx_Volume=("Volume", "sum"))
                )
                incm_ratio_scope = INCM_MOBILE_SUBSCRIBERS_Q2_2025[INCM_MOBILE_SUBSCRIBERS_Q2_2025["Province"].isin(ime_prov)].copy()
                ratio_df = (
                    incm_ratio_scope
                    .merge(sub_prov_ref, on="Province", how="left")
                    .merge(ag_prov_ref, on="Province", how="left")
                    .merge(tx_prov_ref, on="Province", how="left")
                )
                for col in ["Subscribers", "Agents", "Tx_Value", "Tx_Volume"]:
                    ratio_df[col] = pd.to_numeric(ratio_df[col], errors="coerce").fillna(0.0)
                ratio_df["Wallet_Penetration"] = ratio_df.apply(
                    lambda r: (r["Subscribers"] / r["Mobile_Subscribers"]) if r["Mobile_Subscribers"] > 0 else 0.0,
                    axis=1,
                )
                ratio_df["IME_INCM_Index_per_100"] = ratio_df["Wallet_Penetration"] * 100
                ratio_df["Agents_per_10k_Mobile"] = ratio_df.apply(
                    lambda r: (r["Agents"] / r["Mobile_Subscribers"] * 10_000) if r["Mobile_Subscribers"] > 0 else 0.0,
                    axis=1,
                )
                ratio_df["Tx_Value_per_Mobile"] = ratio_df.apply(
                    lambda r: (r["Tx_Value"] / r["Mobile_Subscribers"]) if r["Mobile_Subscribers"] > 0 else 0.0,
                    axis=1,
                )
                ratio_df["Tx_Volume_per_Mobile"] = ratio_df.apply(
                    lambda r: (r["Tx_Volume"] / r["Mobile_Subscribers"]) if r["Mobile_Subscribers"] > 0 else 0.0,
                    axis=1,
                )
    
                total_mobile = ratio_df["Mobile_Subscribers"].sum()
                total_subs_ref = ratio_df["Subscribers"].sum()
                total_agents_ref = ratio_df["Agents"].sum()
                total_tx_value_ref = ratio_df["Tx_Value"].sum()
                total_tx_volume_ref = ratio_df["Tx_Volume"].sum()
                pen_total = (total_subs_ref / total_mobile) if total_mobile > 0 else 0.0
                ime_incm_index_total = pen_total * 100
                ag_10k_total = (total_agents_ref / total_mobile * 10_000) if total_mobile > 0 else 0.0
                value_per_mobile_total = (total_tx_value_ref / total_mobile) if total_mobile > 0 else 0.0
                volume_per_mobile_total = (total_tx_volume_ref / total_mobile) if total_mobile > 0 else 0.0
    
                st.caption(
                    (
                        f"Leitura de oportunidade com IME de {localize_month(ratio_month_ref)} {ime_year}, "
                        "alinhada ao baseline INCM 2025 T2."
                    )
                    if st.session_state.lang == "PT"
                    else (
                        f"Opportunity lens uses IME data from {localize_month(ratio_month_ref)} {ime_year}, "
                        "aligned with INCM 2025 Q2 baseline."
                    )
                )
                l1, l2, l3, l4 = st.columns(4)
                l1.metric(
                    "Índice IME/INCM (por 100)" if st.session_state.lang == "PT" else "IME/INCM index (per 100)",
                    f"{ime_incm_index_total:.1f}",
                )
                l2.metric(
                    "Agentes por 10 mil subscrições móveis" if st.session_state.lang == "PT" else "Agents per 10k mobile subscriptions",
                    f"{ag_10k_total:.1f}",
                )
                l3.metric(
                    "Valor por subscrição móvel" if st.session_state.lang == "PT" else "Value per mobile subscription",
                    format_compact(value_per_mobile_total),
                )
                l4.metric(
                    "Volume por subscrição móvel" if st.session_state.lang == "PT" else "Volume per mobile subscription",
                    format_compact(volume_per_mobile_total),
                )
                st.caption(
                    "ℹ️ O índice IME/INCM pode exceder 100 porque compara subscrições/reportes de serviço (não pessoas únicas). "
                    "Usar como sinal relativo entre províncias."
                    if st.session_state.lang == "PT"
                    else "ℹ️ The IME/INCM index may exceed 100 because it compares service subscriptions/reporting (not unique people). "
                    "Use it as a relative cross-province signal."
                )
    
                pen_plot = ratio_df.sort_values("IME_INCM_Index_per_100", ascending=False).copy()
                fig_pen = px.bar(
                    pen_plot,
                    x="Province",
                    y="IME_INCM_Index_per_100",
                    text=[f"{v:.1f}" for v in pen_plot["IME_INCM_Index_per_100"]],
                    title=(
                        "Índice IME/INCM por província (subscrições por 100)"
                        if st.session_state.lang == "PT"
                        else "IME/INCM index by province (subscriptions per 100)"
                    ),
                )
                fig_pen.update_layout(xaxis_tickangle=-20, yaxis=dict(rangemode="tozero"), height=360)
                plot_chart(fig_pen, use_container_width=True)
    
            c1, c2 = st.columns(2)
            with c1:
                group_axis = "District" if use_district_axis else "Province"
                eff_df = pd.merge(
                    sub_stock.groupby(group_axis, as_index=False)["Subscribers"].sum(),
                    ag_stock.groupby(group_axis, as_index=False)["Agents"].sum(),
                    on=group_axis,
                    how="outer",
                )
                eff_df["Subscribers"] = pd.to_numeric(eff_df["Subscribers"], errors="coerce").fillna(0)
                eff_df["Agents"] = pd.to_numeric(eff_df["Agents"], errors="coerce").fillna(0)
                eff_df["Subscribers_per_Agent"] = eff_df.apply(
                    lambda r: (r["Subscribers"] / r["Agents"]) if r["Agents"] > 0 else 0,
                    axis=1,
                )
                if eff_df.empty:
                    st.info(
                        "Sem dados para eficiência da rede com os filtros seleccionados."
                        if st.session_state.lang == "PT"
                        else "No network-efficiency data for selected filters."
                    )
                else:
                    eff_show = eff_df.sort_values("Subscribers_per_Agent", ascending=False)
                    geo_label = (
                        ("Distrito" if use_district_axis else "Província")
                        if st.session_state.lang == "PT"
                        else ("District" if use_district_axis else "Province")
                    )
                    ratio_label = "Subscrições por agente" if st.session_state.lang == "PT" else "Subscriptions per agent"
                    eff_show_plot = eff_show.rename(columns={group_axis: geo_label}).copy()
                    eff_show_plot[ratio_label] = eff_show_plot["Subscribers_per_Agent"]
                    fig_eff = px.bar(
                        eff_show_plot,
                        x=geo_label,
                        y=ratio_label,
                        text=[f"{v:.1f}" for v in eff_show_plot[ratio_label]],
                        title=(
                            ("Subscrições por Agente por Distrito" if use_district_axis else "Subscrições por Agente por Província")
                            if st.session_state.lang == "PT"
                            else ("Subscriptions per Agent by District" if use_district_axis else "Subscriptions per Agent by Province")
                        ),
                    )
                    fig_eff.update_layout(height=420)
                    plot_chart(fig_eff, use_container_width=True)
    
            with c2:
                metric_options = (
                    [
                        "Subscrições",
                        "Agentes",
                        "Penetração (subscrições por 100 elegíveis)",
                        f"Depósitos ({ime_measure})",
                        f"Levantamentos ({ime_measure})",
                        f"Transferências ({ime_measure})",
                        f"Pagamentos ({ime_measure})",
                    ]
                    if st.session_state.lang == "PT"
                    else [
                        "Subscriptions",
                        "Agents",
                        "Penetration (subscriptions per 100 eligible)",
                        f"Deposits ({ime_measure})",
                        f"Withdrawals ({ime_measure})",
                        f"Transfers ({ime_measure})",
                        f"Payments ({ime_measure})",
                    ]
                )
                top_metric = st.selectbox(
                    "Top distritos por" if st.session_state.lang == "PT" else "Top districts by",
                    metric_options,
                    key="ime_top_metric",
                )
                if top_metric in ["Subscrições", "Subscriptions"]:
                    top_df = sub_stock.groupby("District", as_index=False)["Subscribers"].sum().rename(columns={"Subscribers": "Total"})
                elif top_metric in ["Agentes", "Agents"]:
                    top_df = ag_stock.groupby("District", as_index=False)["Agents"].sum().rename(columns={"Agents": "Total"})
                elif top_metric in [
                    "Penetração (subscrições por 100 elegíveis)",
                    "Penetration (subscriptions per 100 eligible)",
                ]:
                    sub_pen = sub_stock.groupby("District", as_index=False)["Subscribers"].sum()
                    pop_pen = (
                        denom_scope_df.groupby("District", as_index=False)["Eligible_Population"].sum()
                        if not denom_scope_df.empty
                        else pd.DataFrame(columns=["District", "Eligible_Population"])
                    )
                    top_df = sub_pen.merge(pop_pen, on="District", how="left")
                    top_df["Eligible_Population"] = pd.to_numeric(top_df["Eligible_Population"], errors="coerce").fillna(0.0)
                    top_df["Total"] = top_df.apply(
                        lambda r: (r["Subscribers"] / r["Eligible_Population"] * 100) if r["Eligible_Population"] > 0 else 0.0,
                        axis=1,
                    )
                else:
                    tx_label_map = {
                        f"Depósitos ({ime_measure})": "Depósitos",
                        f"Levantamentos ({ime_measure})": "Levantamentos",
                        f"Transferências ({ime_measure})": "Transferências",
                        f"Pagamentos ({ime_measure})": "Pagamentos",
                        f"Deposits ({ime_measure})": "Depósitos",
                        f"Withdrawals ({ime_measure})": "Levantamentos",
                        f"Transfers ({ime_measure})": "Transferências",
                        f"Payments ({ime_measure})": "Pagamentos",
                    }
                    tx_type = tx_label_map[top_metric]
                    top_df = (
                        tx_month[tx_month["Transaction_Type"] == tx_type]
                        .groupby("District", as_index=False)[tx_metric_col]
                        .sum()
                        .rename(columns={tx_metric_col: "Total"})
                    )
                if top_df.empty:
                    st.info(
                        "Sem dados para ranking distrital com os filtros seleccionados."
                        if st.session_state.lang == "PT"
                        else "No district ranking data for selected filters."
                    )
                else:
                    top_show = top_df.sort_values("Total", ascending=False).head(10).sort_values("Total", ascending=True)
                    district_axis = "Distrito" if st.session_state.lang == "PT" else "District"
                    top_show_plot = top_show.rename(columns={"District": district_axis}).copy()
                    is_pen_metric = top_metric in [
                        "Penetração (subscrições por 100 elegíveis)",
                        "Penetration (subscriptions per 100 eligible)",
                    ]
                    fig_top = px.bar(
                        top_show_plot,
                        y=district_axis,
                        x="Total",
                        orientation="h",
                        text=[
                            (f"{v:.1f}" if is_pen_metric else format_compact(v))
                            for v in top_show_plot["Total"]
                        ],
                        title=(
                            f"Top 10 distritos — {top_metric}"
                            if st.session_state.lang == "PT"
                            else f"Top 10 districts — {top_metric}"
                        ),
                    )
                    fig_top.update_layout(height=420)
                    plot_chart(fig_top, use_container_width=True)
    
            st.markdown("---")
            t1, t2 = st.columns(2)
            with t1:
                tx_trend = (
                    tx_geo.groupby(["Month", "Transaction_Type"], as_index=False)[tx_metric_col]
                    .sum()
                    .rename(columns={tx_metric_col: "Total"})
                )
                if not tx_trend.empty:
                    tx_type_col = "Tipo de transacção" if st.session_state.lang == "PT" else "Transaction Type"
                    tx_trend = tx_trend.copy()
                    if st.session_state.lang == "EN":
                        tx_trend[tx_type_col] = tx_trend["Transaction_Type"].replace(
                            {
                                "Depósitos": "Deposits",
                                "Levantamentos": "Withdrawals",
                                "Transferências": "Transfers",
                                "Pagamentos": "Payments",
                            }
                        )
                    else:
                        tx_trend[tx_type_col] = tx_trend["Transaction_Type"]
                    tx_trend = localize_month_df(tx_trend, source_col="Month", target_col="Month_Display")
                    fig_tx_trend = px.line(
                        tx_trend,
                        x="Month_Display",
                        y="Total",
                        color=tx_type_col,
                        markers=True,
                        title=(
                            f"Tendência - transacções de carteira móvel ({ime_measure})"
                            if st.session_state.lang == "PT"
                            else f"Trend - mobile wallet transactions ({ime_measure})"
                        ),
                    )
                    fig_tx_trend.update_layout(yaxis=dict(rangemode="tozero"), height=420)
                    plot_chart(fig_tx_trend, use_container_width=True)
            with t2:
                year_mix = (
                    tx_all_geo.groupby("Year", as_index=False)
                    .agg(Volume=("Volume", "sum"), Value=("Value", "sum"))
                    .sort_values("Year")
                )
                if not year_mix.empty:
                    fig_mix = go.Figure()
                    fig_mix.add_trace(
                        go.Bar(
                            x=year_mix["Year"],
                            y=year_mix["Volume"],
                            name="Volume",
                            marker_color="#2563eb",
                        )
                    )
                    fig_mix.add_trace(
                        go.Scatter(
                            x=year_mix["Year"],
                            y=year_mix["Value"],
                            name="Valor" if st.session_state.lang == "PT" else "Value",
                            mode="lines+markers",
                            yaxis="y2",
                            line=dict(color="#f97316", width=3),
                        )
                    )
                    fig_mix.update_layout(
                        title=(
                            "Tendência anual de transacções de carteira móvel"
                            if st.session_state.lang == "PT"
                            else "Annual trend of mobile wallet transactions"
                        ),
                        yaxis=dict(rangemode="tozero"),
                        yaxis2=dict(overlaying="y", side="right", rangemode="tozero"),
                        xaxis=dict(dtick=1),
                        height=420,
                    )
                    plot_chart(fig_mix, use_container_width=True)
    
            if not ime_sub_demo_df.empty and effective_month_ref is not None:
                demo_scope = ime_sub_demo_df[
                    (ime_sub_demo_df["Year"] == ime_year)
                    & (ime_sub_demo_df["Month"].astype(str) == effective_month_ref)
                    & (ime_sub_demo_df["Province"].isin(ime_prov))
                    & (ime_sub_demo_df["District"].isin(ime_dist))
                ].copy()
                if not demo_scope.empty:
                    d1, d2 = st.columns(2)
                    with d1:
                        gender_split = demo_scope.groupby("Gender", as_index=False)["Subscribers"].sum()
                        if not gender_split.empty:
                            fig_gender = px.pie(
                                gender_split,
                                values="Subscribers",
                                names="Gender",
                                title="Subscrições de Carteira Móvel por género" if st.session_state.lang == "PT" else "Mobile Wallet subscriptions by gender",
                                hole=0.45,
                            )
                            fig_gender.update_layout(height=380)
                            plot_chart(fig_gender, use_container_width=True)
                    with d2:
                        age_col = "Age" if "Age" in demo_scope.columns else ("Age_Group" if "Age_Group" in demo_scope.columns else None)
                        if age_col is None:
                            age_split = pd.DataFrame()
                        else:
                            unknown_label = "Não informado" if st.session_state.lang == "PT" else "Not informed"
                            age_labels = demo_scope[age_col].astype(str).replace({"nan": unknown_label, "NaN": unknown_label})
                            age_tmp = demo_scope.copy()
                            age_tmp["_AgeLabel"] = age_labels
                            age_split = age_tmp.groupby("_AgeLabel", as_index=False)["Subscribers"].sum()
                            preferred_order = ["0-16", "17-21", "22-60", "+60", unknown_label]
                            age_split["_order"] = age_split["_AgeLabel"].apply(
                                lambda v: preferred_order.index(v) if v in preferred_order else len(preferred_order)
                            )
                            age_split = age_split.sort_values("_order").drop(columns=["_order"])
                        if not age_split.empty:
                            fig_age = px.bar(
                                age_split,
                                x="_AgeLabel",
                                y="Subscribers",
                                text=[format_compact(v) for v in age_split["Subscribers"]],
                                title="Subscrições de Carteira Móvel por faixa etária" if st.session_state.lang == "PT" else "Mobile Wallet subscriptions by age group",
                            )
                            fig_age.update_layout(height=380)
                            plot_chart(fig_age, use_container_width=True)
                        else:
                            st.info(
                                "Sem dados por faixa etária para os filtros seleccionados."
                                if st.session_state.lang == "PT"
                                else "No age-group data for selected filters."
                            )
        render_page_caveats(
            [
                "A leitura distrital de Carteira Móvel cobre os distritos presentes nos ficheiros oficiais dos anos disponíveis.",
            ]
            if st.session_state.lang == "PT"
            else [
                "Mobile Wallet district view only covers districts present in official files for available years.",
            ]
        )

# ==========================================
# PAGE 4: PRODUCTS (toggle Accounts/Cards)
# ==========================================
with tab_accounts_cards:
    view_prompt = "Ver" if st.session_state.lang == "PT" else "View"
    opt_accounts = T("tab_accounts")
    opt_cards = T("tab_cards")
    products_view = single_choice_toggle(
        view_prompt,
        [opt_accounts, opt_cards],
        key="products_view_toggle",
    )
    if products_view == opt_accounts:
        st.title(T("title_accounts"))
    else:
        st.title(T("title_cards"))
    st.caption(tab_story("products"))

    if products_view == opt_accounts:
        st.caption(T("caption_accounts"))
        acc_prev = dataframes["accounts"][
            (dataframes["accounts"]["Year"] == (selected_year - 1)) &
            (dataframes["accounts"]["Province"].isin(selected_prov))
        ]
        if selected_dist and "District" in acc_prev.columns:
            acc_prev = acc_prev[acc_prev["District"].isin(selected_dist)]
        acc_prev_snap = last_month_snapshot(acc_prev)
        acc_prev_total = acc_prev_snap["Total_Accounts"].sum()
        acc_curr_total = f_acc_snap["Total_Accounts"].sum()
        acc_growth = ((acc_curr_total - acc_prev_total) / acc_prev_total * 100) if acc_prev_total > 0 else None
        meticais_share = (
            f_acc_snap[f_acc_snap["Account_Currency"] == "Em Meticais"]["Total_Accounts"].sum() / acc_curr_total * 100
            if acc_curr_total > 0 else 0
        )
        a1, a2, a3 = st.columns(3)
        a1.metric(T("total_accounts"), format_compact(acc_curr_total), delta=f"{acc_growth:+.1f}%" if acc_growth is not None else None)
        a2.metric(T("districts"), format_compact(f_acc_snap['District'].nunique()))
        share_mzn_label = "Quota MZN (%)" if st.session_state.lang == "PT" else "MZN Share (%)"
        a3.metric(share_mzn_label, f"{meticais_share:.1f}%")

        st.subheader(f"{T('monthly_trend_accounts')} ({selected_year})")
        month_acc = f_acc.groupby('Month', observed=False)['Total_Accounts'].sum().reset_index()
        month_acc = localize_month_df(month_acc, source_col="Month", target_col=T("month"))
        month_acc = month_acc[[T("month"), "Total_Accounts"]].copy()
        month_acc.columns = [T("month"), T("total_accounts")]
        fig_month_acc = px.line(
            month_acc,
            x=T("month"),
            y=T("total_accounts"),
            markers=True,
            title=f"{T('monthly_trend_accounts')} ({selected_year})",
        )
        fig_month_acc.update_layout(yaxis=dict(rangemode='tozero'))
        plot_chart(fig_month_acc, use_container_width=True)

        st.subheader(f"{T('accounts_by_age')} ({selected_year})")
        age_buckets = ["0-16", "17-21", "22-60", "+60"]
        age_acc_detail = f_acc_snap[f_acc_snap["Age"].isin(age_buckets)]
        if age_acc_detail.empty:
            msg_pt = (
                "Dados indisponíveis para este gráfico no ano seleccionado. "
                "No ano de 2020, o Banco de Moçambique não reportou contas por faixa etária."
            )
            msg_en = (
                "Data unavailable for this chart in the selected year. "
                "In 2020, Banco de Moçambique did not report accounts by age group."
            )
            st.info(msg_pt if st.session_state.lang == "PT" else msg_en)
        else:
            age_acc = age_acc_detail.groupby('Age', observed=False)['Total_Accounts'].sum().reset_index()
            age_acc.columns = [T("age_group"), T("total_accounts")]
            plot_chart(
                px.bar(age_acc, y=T("age_group"), x=T("total_accounts"), orientation='h', color=T("age_group")),
                use_container_width=True,
            )

        st.subheader(f"{T('currency_distribution')} {title_suffix} ({selected_year})")
        curr_data = f_acc_snap.groupby([geo_axis, 'Account_Currency'])['Total_Accounts'].sum().reset_index()
        curr_data.columns = [geo_axis_label, T("currency_label"), T("total_accounts")]
        plot_chart(px.bar(curr_data, x=geo_axis_label, y=T("total_accounts"), color=T("currency_label"), barmode='group'), use_container_width=True)

    else:
        st.caption(T("caption_cards"))
        card_prev = dataframes["cards"][
            (dataframes["cards"]["Year"] == (selected_year - 1)) &
            (dataframes["cards"]["Province"].isin(selected_prov))
        ]
        if selected_dist and "District" in card_prev.columns:
            card_prev = card_prev[card_prev["District"].isin(selected_dist)]
        card_prev_snap = last_month_snapshot(card_prev)
        card_prev_total = card_prev_snap["Total_Cards"].sum()
        card_curr_total = f_card_snap["Total_Cards"].sum()
        card_growth = ((card_curr_total - card_prev_total) / card_prev_total * 100) if card_prev_total > 0 else None
        debit_share = (
            f_card_snap[f_card_snap["Card_Type"] == "Cartões de Débito"]["Total_Cards"].sum() / card_curr_total * 100
            if card_curr_total > 0 else 0
        )
        c1, c2, c3 = st.columns(3)
        c1.metric(T("total_cards"), format_compact(card_curr_total), delta=f"{card_growth:+.1f}%" if card_growth is not None else None)
        c2.metric(T("districts"), format_compact(f_card_snap['District'].nunique()))
        share_debit_label = "Quota Débito (%)" if st.session_state.lang == "PT" else "Debit Share (%)"
        c3.metric(share_debit_label, f"{debit_share:.1f}%")

        st.subheader(f"{T('monthly_trend_cards')} ({selected_year})")
        month_card = f_card.groupby('Month', observed=False)['Total_Cards'].sum().reset_index()
        month_card = localize_month_df(month_card, source_col="Month", target_col=T("month"))
        month_card = month_card[[T("month"), "Total_Cards"]].copy()
        month_card.columns = [T("month"), T("total_cards")]
        fig_month_card = px.line(
            month_card,
            x=T("month"),
            y=T("total_cards"),
            markers=True,
            title=f"{T('monthly_trend_cards')} ({selected_year})",
        )
        fig_month_card.update_layout(yaxis=dict(rangemode='tozero'))
        plot_chart(fig_month_card, use_container_width=True)

        st.subheader(f"{T('product_adoption_age')} ({selected_year})")
        age_buckets = ["0-16", "17-21", "22-60", "+60"]
        age_card_detail = f_card_snap[f_card_snap["Age"].isin(age_buckets)]
        if age_card_detail.empty:
            msg_pt = (
                "Dados indisponíveis para este gráfico no ano seleccionado. "
                "No ano de 2020, o Banco de Moçambique não reportou cartões por faixa etária."
            )
            msg_en = (
                "Data unavailable for this chart in the selected year. "
                "In 2020, Banco de Moçambique did not report cards by age group."
            )
            st.info(msg_pt if st.session_state.lang == "PT" else msg_en)
        else:
            age_card = age_card_detail.groupby(['Age', 'Card_Type'], observed=False)['Total_Cards'].sum().reset_index()
            age_card.columns = [T("age_group"), T("card_type_label"), T("total_cards")]
            plot_chart(
                px.bar(age_card, y=T("age_group"), x=T("total_cards"), color=T("card_type_label"), orientation='h'),
                use_container_width=True,
            )

        st.subheader(f"{T('card_type')} {title_suffix} ({selected_year})")
        card_type_geo = f_card_snap.groupby([geo_axis, 'Card_Type'])['Total_Cards'].sum().reset_index()
        card_type_geo.columns = [geo_axis_label, T("card_type_label"), T("total_cards")]
        plot_chart(px.bar(card_type_geo, x=geo_axis_label, y=T("total_cards"), color=T("card_type_label"), barmode='group'), use_container_width=True)
    render_page_caveats()

# ==========================================
# PAGE 5: INFRAESTRUTURA
# ==========================================
with tab_infra:
    st.title(T("title_infra"))
    st.caption(T("caption_infra"))
    st.caption(tab_story("infra"))
    curr_atm_total = f_atm_snap["ATMs_Number"].sum()
    curr_pos_total = f_pos_snap["POSs_Number"].sum()
    infra_ratio = (curr_pos_total / curr_atm_total) if curr_atm_total > 0 else 0
    i1, i2, i3 = st.columns(3)
    i1.metric(T("num_atms"), format_compact(curr_atm_total))
    i2.metric(T("num_pos"), format_compact(curr_pos_total))
    i3.metric("POS/ATM", f"{infra_ratio:.1f}")

    # Per-capita infrastructure from census (December snapshot)
    infra_pop_sel = denominator_population(census_df[census_df["Province"].isin(selected_prov)], selected_year)
    if infra_pop_sel > 0:
        inf_k1, inf_k2 = st.columns(2)
        inf_k1.metric(T("atm_per_100k"), f"{curr_atm_total / infra_pop_sel * 100_000:.1f}")
        inf_k2.metric(T("pos_per_100k"), f"{curr_pos_total / infra_pop_sel * 100_000:.1f}")
        st.caption(T("census_note_short"))
        st.caption(f"ℹ️ {inclusion_method_note(selected_year)}")

    col_i1, col_i2 = st.columns(2)
    with col_i1:
        atm_sum = f_atm_snap.groupby(geo_axis)['ATMs_Number'].sum().reset_index()
        atm_sum.columns = [geo_axis_label, T("num_atms")]
        plot_chart(
            px.bar(atm_sum, x=geo_axis_label, y=T("num_atms"), title=f"{T('atm_distribution')} ({selected_year})"),
            use_container_width=True,
        )
    with col_i2:
        pos_sum = f_pos_snap.groupby(geo_axis)['POSs_Number'].sum().reset_index()
        pos_sum.columns = [geo_axis_label, T("num_pos")]
        plot_chart(
            px.bar(pos_sum, x=geo_axis_label, y=T("num_pos"), title=f"{T('pos_distribution')} ({selected_year})"),
            use_container_width=True,
        )
    render_page_caveats()

# ==========================================
# PAGE 6: USAGE (toggle Digital/Transactions)
# ==========================================
with tab_channels:
    usage_view_prompt = "Ver" if st.session_state.lang == "PT" else "View"
    usage_opt_digital = T("tab_digital")
    usage_opt_txn = T("tab_txn")
    usage_view = single_choice_toggle(
        usage_view_prompt,
        [usage_opt_txn, usage_opt_digital],
        key="usage_view_toggle",
    )
    if usage_view == usage_opt_digital:
        st.title(T("title_digital"))
    else:
        st.title(T("title_txn"))
    st.caption(tab_story("usage"))

    if usage_view == usage_opt_digital:
        st.caption(T("caption_digital"))
        mobile_context_pt = (
            "ℹ️ Contexto metodológico (Moçambique): no ficheiro Banca Electrónica, o indicador de Mobile Banking "
            "refere-se exclusivamente às aplicações móveis da banca comercial (ex.: NetPlus, IZI, Daki). "
            "Não inclui carteiras móveis IME (M-Pesa, mKesh, e-Mola, Conta Móvel)."
        )
        mobile_context_en = (
            "ℹ️ Methodology context (Mozambique): in the Banca Electrónica file, the Mobile Banking indicator "
            "refers only to commercial bank mobile apps (e.g., NetPlus, IZI, Daki). "
            "It does not include IME mobile wallets (M-Pesa, mKesh, e-Mola, Conta Móvel)."
        )
        st.info(mobile_context_pt if st.session_state.lang == "PT" else mobile_context_en)

        st.caption(
            "ℹ️ A análise descritiva detalhada de Carteira Móvel está na página dedicada `📱 Carteiras Móveis`."
            if st.session_state.lang == "PT"
            else "ℹ️ Detailed Mobile Wallet descriptive analysis is available in the dedicated `📱 Mobile Wallets` page."
        )

        common_metrics = sorted(set(mob_df['Metric'].unique()) & set(net_df['Metric'].unique()))
        if not common_metrics:
            common_metrics = sorted(mob_df['Metric'].unique())

        digital_metric = st.selectbox(
            T("comparison_metric"), common_metrics, key="digital_metric",
            help=T("help_comparison")
        )
        mob_current = mob_df[(mob_df["Year"] == selected_year) & (mob_df["Metric"] == digital_metric)]["Value"].sum()
        net_current = net_df[(net_df["Year"] == selected_year) & (net_df["Metric"] == digital_metric)]["Value"].sum()
        total_current = mob_current + net_current
        mobile_share = (mob_current / total_current * 100) if total_current > 0 else 0
        d1, d2, d3 = st.columns(3)
        d1.metric("Mobile", format_compact(mob_current))
        d2.metric("Internet", format_compact(net_current))
        mobile_share_label = "Quota Mobile (%)" if st.session_state.lang == "PT" else "Mobile Share (%)"
        d3.metric(mobile_share_label, f"{mobile_share:.1f}%")

        st.subheader(f"Mobile vs Internet — {digital_metric} ({selected_year})")
        f_mob = mob_df[(mob_df['Year'] == selected_year) & (mob_df['Metric'] == digital_metric)]
        f_net = net_df[(net_df['Year'] == selected_year) & (net_df['Metric'] == digital_metric)]
        m_mob = f_mob.groupby('Month', observed=False)['Value'].sum().reset_index().assign(Canal='Mobile Banking')
        m_net = f_net.groupby('Month', observed=False)['Value'].sum().reset_index().assign(Canal='Internet Banking')
        m_mob = localize_month_df(m_mob, source_col="Month", target_col=T("month"))
        m_net = localize_month_df(m_net, source_col="Month", target_col=T("month"))
        m_mob = m_mob[[T("month"), "Value", "Canal"]].rename(columns={"Value": T("value")})
        m_net = m_net[[T("month"), "Value", "Canal"]].rename(columns={"Value": T("value")})
        comp_dig = pd.concat([m_mob, m_net])
        fig_comp_dig = px.line(
            comp_dig,
            x=T("month"),
            y=T("value"),
            color='Canal',
            markers=True,
            title=f"{T('monthly_comparison')}: {digital_metric} ({selected_year})",
        )
        fig_comp_dig.update_layout(yaxis=dict(rangemode='tozero'))
        plot_chart(fig_comp_dig, use_container_width=True)

        st.markdown("---")

        dc_col1, dc_col2 = st.columns(2)
        with dc_col1:
            dig_channel = st.selectbox(
                T("channel"), ["Mobile Banking", "Internet Banking"], key="dig_channel",
                help=T("help_channel")
            )
        dig_src = mob_df if dig_channel == "Mobile Banking" else net_df
        available_dig_metrics = sorted(dig_src['Metric'].unique())
        with dc_col2:
            dig_detail_metric = st.selectbox(
                T("detailed_metric"), available_dig_metrics, key="dig_detail_metric",
                help=T("help_detail_metric")
            )

        dig_filtered = dig_src[dig_src['Metric'] == dig_detail_metric]
        dig_label = f"{dig_channel} — {dig_detail_metric}"

        st.subheader(f"{dig_label} — {selected_year}")
        dig_monthly = dig_filtered[dig_filtered['Year'] == selected_year].groupby('Month', observed=False)['Value'].sum().reset_index()
        dig_monthly = localize_month_df(dig_monthly, source_col="Month", target_col=T("month"))
        dig_monthly = dig_monthly[[T("month"), "Value"]].rename(columns={"Value": T("value")})
        fig_dig_monthly = px.line(dig_monthly, x=T("month"), y=T("value"), markers=True,
                                  title=f"{T('monthly_trend')} ({selected_year})")
        fig_dig_monthly.update_layout(yaxis=dict(rangemode='tozero'))
        plot_chart(fig_dig_monthly, use_container_width=True)

        dig_yearly = dig_filtered.groupby('Year')['Value'].sum().reset_index().sort_values('Year')
        dig_yearly.rename(columns={'Year': T("year"), 'Value': T("value")}, inplace=True)

        if not dig_yearly.empty:
            dig_yearly[T("growth_pct")] = dig_yearly[T("value")].pct_change() * 100

            v2_col1, v2_col2 = st.columns(2)
            with v2_col1:
                fig_dig_bar = px.bar(dig_yearly, x=T("year"), y=T("value"), text_auto='.3s',
                                     title=T("annual_evolution"))
                fig_dig_bar.update_layout(xaxis=dict(dtick=1))
                plot_chart(fig_dig_bar, use_container_width=True)
            with v2_col2:
                growth_dig = dig_yearly.dropna(subset=[T("growth_pct")]).copy()
                if not growth_dig.empty:
                    fig_dig_gr = px.bar(growth_dig, x=T("year"), y=T("growth_pct"), text_auto='.1f',
                                        title=T("yoy_growth"),
                                        color=T("growth_pct"), color_continuous_scale='RdYlGn')
                    fig_dig_gr.update_layout(xaxis=dict(dtick=1))
                    plot_chart(fig_dig_gr, use_container_width=True)

    else:
        st.caption(T("caption_txn"))
        vol_norm = normalize_atm_txn(vol_df)
        val_norm = normalize_atm_txn(val_df)

        atm_choices = {}
        for metric in ['Levantamentos', 'Transferências']:
            subs = vol_norm[vol_norm['Metric'] == metric]['Sub_Metric'].dropna().unique().tolist()
            for sub in subs:
                label = f"ATM — {metric}: {sub}"
                atm_choices[label] = (metric, sub)
        atm_choices["ATM — Pagamentos de Serviços"] = ("Pagamentos de Serviços", None)

        pos_choice_label = "POS — Pagamentos"
        mob_choice_label = "Mobile Banking — Transacções"
        net_choice_label = "Internet Banking — Transacções"

        all_txn_options = list(atm_choices.keys()) + [pos_choice_label, mob_choice_label, net_choice_label]

        txn_selection = st.selectbox(
            T("txn_type"), all_txn_options, key="txn_selection",
            help=T("help_txn")
        )

        txn_title = txn_selection

        if txn_selection in atm_choices:
            atm_metric, atm_sub = atm_choices[txn_selection]
            mask_vol = vol_norm['Metric'] == atm_metric
            mask_val = val_norm['Metric'] == atm_metric
            if atm_sub is not None:
                mask_vol = mask_vol & (vol_norm['Sub_Metric'] == atm_sub)
                mask_val = mask_val & (val_norm['Sub_Metric'] == atm_sub)
            sel_vol = vol_norm[mask_vol]
            sel_val = val_norm[mask_val]
            vol_monthly = sel_vol[sel_vol['Year'] == selected_year].groupby('Month', observed=False)['Total_Transactions'].sum().reset_index()
            vol_monthly.columns = ['Month', T("volume")]
            val_monthly = sel_val[sel_val['Year'] == selected_year].groupby('Month', observed=False)['Transactions_Amount'].sum().reset_index()
            val_monthly.columns = ['Month', T("value")]
            vol_annual = sel_vol.groupby('Year')['Total_Transactions'].sum().reset_index()
            vol_annual.columns = ['Year', T("volume")]
            val_annual = sel_val.groupby('Year')['Transactions_Amount'].sum().reset_index()
            val_annual.columns = ['Year', T("value")]
        elif txn_selection == pos_choice_label:
            pos_vol_src = pos_txn_df[pos_txn_df['Metric'].str.contains('Volume', case=False, na=False)]
            pos_val_src = pos_txn_df[pos_txn_df['Metric'].str.contains('Valor', case=False, na=False)]
            vol_monthly = pos_vol_src[pos_vol_src['Year'] == selected_year].groupby('Month', observed=False)['Value'].sum().reset_index()
            vol_monthly.columns = ['Month', T("volume")]
            val_monthly = pos_val_src[pos_val_src['Year'] == selected_year].groupby('Month', observed=False)['Value'].sum().reset_index()
            val_monthly.columns = ['Month', T("value")]
            vol_annual = pos_vol_src.groupby('Year')['Value'].sum().reset_index()
            vol_annual.columns = ['Year', T("volume")]
            val_annual = pos_val_src.groupby('Year')['Value'].sum().reset_index()
            val_annual.columns = ['Year', T("value")]
        elif txn_selection == mob_choice_label:
            mob_vol_m = [m for m in mob_df['Metric'].unique() if 'Volume' in str(m)]
            mob_val_m = [m for m in mob_df['Metric'].unique() if 'Valor' in str(m)]
            vol_monthly = mob_df[(mob_df['Year'] == selected_year) & (mob_df['Metric'].isin(mob_vol_m))].groupby('Month', observed=False)['Value'].sum().reset_index()
            vol_monthly.columns = ['Month', T("volume")]
            val_monthly = mob_df[(mob_df['Year'] == selected_year) & (mob_df['Metric'].isin(mob_val_m))].groupby('Month', observed=False)['Value'].sum().reset_index()
            val_monthly.columns = ['Month', T("value")]
            vol_annual = mob_df[mob_df['Metric'].isin(mob_vol_m)].groupby('Year')['Value'].sum().reset_index()
            vol_annual.columns = ['Year', T("volume")]
            val_annual = mob_df[mob_df['Metric'].isin(mob_val_m)].groupby('Year')['Value'].sum().reset_index()
            val_annual.columns = ['Year', T("value")]
        else:
            net_vol_m = [m for m in net_df['Metric'].unique() if 'Volume' in str(m)]
            net_val_m = [m for m in net_df['Metric'].unique() if 'Valor' in str(m)]
            vol_monthly = net_df[(net_df['Year'] == selected_year) & (net_df['Metric'].isin(net_vol_m))].groupby('Month', observed=False)['Value'].sum().reset_index()
            vol_monthly.columns = ['Month', T("volume")]
            val_monthly = net_df[(net_df['Year'] == selected_year) & (net_df['Metric'].isin(net_val_m))].groupby('Month', observed=False)['Value'].sum().reset_index()
            val_monthly.columns = ['Month', T("value")]
            vol_annual = net_df[net_df['Metric'].isin(net_vol_m)].groupby('Year')['Value'].sum().reset_index()
            vol_annual.columns = ['Year', T("volume")]
            val_annual = net_df[net_df['Metric'].isin(net_val_m)].groupby('Year')['Value'].sum().reset_index()
            val_annual.columns = ['Year', T("value")]

        st.markdown("---")
        st.subheader(f"{txn_title} — {selected_year}")
        year_vol = vol_monthly[T("volume")].sum() if not vol_monthly.empty else 0
        year_val = val_monthly[T("value")].sum() if not val_monthly.empty else 0
        avg_ticket = (year_val / year_vol) if year_vol > 0 else 0
        t1, t2, t3 = st.columns(3)
        t1.metric(T("volume"), format_compact(year_vol))
        t2.metric(f"{T('value')} (MZN)", format_compact(year_val))
        ticket_label = "Ticket Médio (MZN)" if st.session_state.lang == "PT" else "Avg Ticket (MZN)"
        t3.metric(ticket_label, format_compact(avg_ticket))

        vol_monthly = localize_month_df(vol_monthly, source_col="Month", target_col=T("month"))
        val_monthly = localize_month_df(val_monthly, source_col="Month", target_col=T("month"))
        vol_monthly = vol_monthly[[T("month"), T("volume")]]
        val_monthly = val_monthly[[T("month"), T("value")]]

        col_v1, col_v2 = st.columns(2)
        with col_v1:
            fig_vol_m = px.bar(
                vol_monthly,
                x=T("month"),
                y=T("volume"),
                title=f"{T('vol_monthly_title')} — {txn_title} ({selected_year})",
            )
            fig_vol_m.update_layout(yaxis=dict(rangemode='tozero'))
            plot_chart(fig_vol_m, use_container_width=True)
        with col_v2:
            fig_val_m = px.line(
                val_monthly,
                x=T("month"),
                y=T("value"),
                markers=True,
                title=f"{T('val_monthly_title')} — {txn_title} ({selected_year})",
            )
            fig_val_m.update_layout(yaxis=dict(rangemode='tozero'))
            plot_chart(fig_val_m, use_container_width=True)

        vol_annual.rename(columns={'Year': T("year")}, inplace=True)
        val_annual.rename(columns={'Year': T("year")}, inplace=True)
        annual_merged = pd.merge(vol_annual, val_annual, on=T("year"), how='outer').sort_values(T("year"))

        if not annual_merged.empty and annual_merged[T("volume")].sum() > 0:
            fig_annual = go.Figure()
            fig_annual.add_trace(go.Bar(
                x=annual_merged[T("year")], y=annual_merged[T("volume")],
                name=T("volume"), yaxis='y', marker_color='#636EFA',
                text=[format_compact(v) for v in annual_merged[T("volume")]], textposition='outside'))
            fig_annual.add_trace(go.Scatter(
                x=annual_merged[T("year")], y=annual_merged[T("value")],
                name=f"{T('value')} (MZN)", yaxis='y2', mode='lines+markers',
                marker_color='#EF553B', line=dict(width=3)))
            fig_annual.update_layout(
                title=f"{T('annual_evol_title')} — {txn_title}",
                xaxis=dict(title=T("year"), dtick=1),
                yaxis=dict(title=T("volume"), side='left'),
                yaxis2=dict(title=f"{T('value')} (MZN)", side='right', overlaying='y'),
                legend=dict(x=0.01, y=0.99), height=450)
            plot_chart(fig_annual, use_container_width=True)
    render_page_caveats()

# ==========================================
# PAGE 7: TENDÊNCIAS HISTÓRICAS
# ==========================================
with tab_trends:
    st.title(T("title_trends"))
    st.caption(T("caption_trends"))
    st.caption(tab_story("trends"))

    trend_indicator = st.selectbox(
        T("indicator"),
        ["Contas Bancárias", "Cartões Bancários", "ATMs", "POS",
         "Mobile Banking", "Internet Banking"],
        key="trend_indicator",
        help=T("help_indicator")
    )

    if trend_indicator == "Contas Bancárias":
        geo_trend = last_month_snapshot_all_years(apply_geo_only(acc_df)); trend_col = 'Total_Accounts'; trend_label = T("total_accounts")
    elif trend_indicator == "Cartões Bancários":
        geo_trend = last_month_snapshot_all_years(apply_geo_only(card_df)); trend_col = 'Total_Cards'; trend_label = T("total_cards")
    elif trend_indicator == "ATMs":
        geo_trend = last_month_snapshot_all_years(apply_geo_only(atm_df)); trend_col = 'ATMs_Number'; trend_label = T("num_atms")
    elif trend_indicator == "POS":
        geo_trend = last_month_snapshot_all_years(apply_geo_only(pos_df)); trend_col = 'POSs_Number'; trend_label = T("num_pos")
    elif trend_indicator == "Mobile Banking":
        geo_trend = mob_df; trend_col = 'Value'; trend_label = T("value")
    else:
        geo_trend = net_df; trend_col = 'Value'; trend_label = T("value")

    st.markdown("---")

    if trend_indicator in ["Mobile Banking", "Internet Banking"]:
        available_metrics = sorted(geo_trend['Metric'].unique())
        selected_trend_metric = st.selectbox(
            T("metric"), available_metrics, key="trend_sub_metric",
            help=T("help_sub_metric")
        )
        geo_trend_filtered = geo_trend[geo_trend['Metric'] == selected_trend_metric]
        yearly_trend = geo_trend_filtered.groupby('Year')[trend_col].sum().reset_index()
        yearly_trend.columns = ['Year', 'Total']
        trend_chart_label = f"{trend_indicator} — {selected_trend_metric}"
    else:
        yearly_trend = geo_trend.groupby('Year')[trend_col].sum().reset_index()
        yearly_trend.columns = ['Year', 'Total']
        trend_chart_label = trend_indicator

    latest_trend_val = yearly_trend.sort_values("Year").iloc[-1]["Total"] if not yearly_trend.empty else 0
    yoy_trend = None
    cagr_trend = None
    if len(yearly_trend) >= 2:
        ys = yearly_trend.sort_values("Year")
        prev_v = ys.iloc[-2]["Total"]
        curr_v = ys.iloc[-1]["Total"]
        yoy_trend = ((curr_v - prev_v) / prev_v * 100) if prev_v > 0 else None
        first_v = ys.iloc[0]["Total"]
        n_years = int(ys.iloc[-1]["Year"] - ys.iloc[0]["Year"])
        if first_v > 0 and n_years > 0:
            cagr_trend = (((curr_v / first_v) ** (1 / n_years)) - 1) * 100
    tr1, tr2, tr3 = st.columns(3)
    tr1.metric(trend_chart_label, format_compact(latest_trend_val))
    tr2.metric(T("yoy_growth"), f"{yoy_trend:+.1f}%" if yoy_trend is not None else "N/A")
    tr3.metric("CAGR", f"{cagr_trend:.1f}%" if cagr_trend is not None else "N/A")

    st.subheader(f"{trend_chart_label} — {T('annual_evolution')}")
    fig_trend_bar = px.bar(yearly_trend, x='Year', y='Total', text_auto='.2s',
                           title=f"{trend_label} {T('by_year')}",
                           labels={'Year': T("year"), 'Total': trend_label})
    fig_trend_bar.update_layout(xaxis=dict(dtick=1))
    plot_chart(fig_trend_bar, use_container_width=True)

    if trend_indicator not in ["Mobile Banking", "Internet Banking"] and 'Province' in geo_trend.columns:
        prov_year_trend = geo_trend.groupby(['Year', 'Province'])[trend_col].sum().reset_index()
        prov_year_trend.columns = ['Year', T("province"), 'Total']
        fig_trend_prov = px.line(prov_year_trend, x='Year', y='Total', color=T("province"),
                                 markers=True,
                                 title=f"{trend_label} {T('by_province_over_years')}",
                                 labels={'Year': T("year"), 'Total': trend_label})
        fig_trend_prov.update_layout(xaxis=dict(dtick=1))
        plot_chart(fig_trend_prov, use_container_width=True)

    if len(yearly_trend) > 1:
        yearly_trend = yearly_trend.sort_values('Year')
        yearly_trend[T("growth_pct")] = yearly_trend['Total'].pct_change() * 100
        growth_display = yearly_trend.dropna(subset=[T("growth_pct")]).copy()
        if not growth_display.empty:
            fig_trend_growth = px.bar(growth_display, x='Year', y=T("growth_pct"),
                                      text_auto='.1f',
                                      title=f"{T('yoy_growth')} — {trend_chart_label}",
                                      color=T("growth_pct"),
                                      color_continuous_scale='RdYlGn',
                                      labels={'Year': T("year")})
            fig_trend_growth.update_layout(xaxis=dict(dtick=1))
            plot_chart(fig_trend_growth, use_container_width=True)

# Heatmap view condensed into Historical Trends page.
with tab_trends:
    expander_title = "Mapa de Calor por Província (opcional)" if st.session_state.lang == "PT" else "Province Heatmap (optional)"
    with st.expander(expander_title, expanded=True):
        st.caption(tab_story("heatmap"))
        heatmap_metric = st.selectbox(
            T("indicator"),
            ["Contas Bancárias", "Cartões Bancários", "ATMs", "POS"],
            key="heatmap_metric",
            help=T("help_heatmap"),
        )

        if heatmap_metric == "Contas Bancárias":
            hm_data = last_month_snapshot_all_years(apply_geo_only(acc_df)).groupby(["Year", "Province"])["Total_Accounts"].sum().reset_index()
            val_col = "Total_Accounts"
        elif heatmap_metric == "Cartões Bancários":
            hm_data = last_month_snapshot_all_years(apply_geo_only(card_df)).groupby(["Year", "Province"])["Total_Cards"].sum().reset_index()
            val_col = "Total_Cards"
        elif heatmap_metric == "ATMs":
            hm_data = last_month_snapshot_all_years(apply_geo_only(atm_df)).groupby(["Year", "Province"])["ATMs_Number"].sum().reset_index()
            val_col = "ATMs_Number"
        else:
            hm_data = last_month_snapshot_all_years(apply_geo_only(pos_df)).groupby(["Year", "Province"])["POSs_Number"].sum().reset_index()
            val_col = "POSs_Number"

        if hm_data.empty:
            st.info("Sem dados para o mapa de calor." if st.session_state.lang == "PT" else "No data for heatmap.")
        else:
            hm_latest_year = int(hm_data["Year"].max())
            hm_latest = hm_data[hm_data["Year"] == hm_latest_year]
            hm_total_latest = hm_latest[val_col].sum()
            hm_top_prov = hm_latest.sort_values(val_col, ascending=False).iloc[0]["Province"] if not hm_latest.empty else "N/A"
            hm_avg_growth = None
            if hm_data["Year"].nunique() > 1:
                hm_tmp = hm_data.pivot_table(index="Province", columns="Year", values=val_col, aggfunc="sum", fill_value=0)
                hm_growth = hm_tmp.pct_change(axis=1) * 100
                hm_vals = hm_growth.iloc[:, 1:].stack().dropna()
                if not hm_vals.empty:
                    hm_avg_growth = hm_vals.mean()
            hm1, hm2, hm3 = st.columns(3)
            hm1.metric(f"{heatmap_metric} ({hm_latest_year})", format_compact(hm_total_latest))
            hm2.metric("Top Província" if st.session_state.lang == "PT" else "Top Province", hm_top_prov)
            hm3.metric(T("growth_pct"), f"{hm_avg_growth:+.1f}%" if hm_avg_growth is not None else "N/A")

            pivot = hm_data.pivot_table(index="Province", columns="Year", values=val_col, aggfunc="sum", fill_value=0)
            fig_hm = go.Figure(
                data=go.Heatmap(
                    z=pivot.values,
                    x=[str(c) for c in pivot.columns],
                    y=pivot.index.tolist(),
                    colorscale="YlOrRd",
                    text=[[f"{v:,.0f}" for v in row] for row in pivot.values],
                    texttemplate="%{text}",
                    hovertemplate=f"{T('province')}: %{{y}}<br>{T('year')}: %{{x}}<br>{T('value')}: %{{text}}<extra></extra>",
                )
            )
            fig_hm.update_layout(
                title=f"{heatmap_metric} {T('by_province_year')}",
                xaxis_title=T("year"),
                yaxis_title=T("province"),
                height=500,
            )
            plot_chart(fig_hm, use_container_width=True)

            if len(pivot.columns) > 1:
                growth_pivot = pivot.pct_change(axis=1) * 100
                growth_pivot = growth_pivot.iloc[:, 1:]
                fig_growth = go.Figure(
                    data=go.Heatmap(
                        z=growth_pivot.values,
                        x=[str(c) for c in growth_pivot.columns],
                        y=growth_pivot.index.tolist(),
                        colorscale="RdYlGn",
                        zmid=0,
                        text=[[f"{v:.1f}%" for v in row] for row in growth_pivot.values],
                        texttemplate="%{text}",
                        hovertemplate=f"{T('province')}: %{{y}}<br>{T('year')}: %{{x}}<br>{T('growth_pct')}: %{{text}}<extra></extra>",
                    )
                )
                fig_growth.update_layout(
                    title=f"{T('yoy_growth')} — {heatmap_metric} {T('by_province_year')}",
                    xaxis_title=T("year"),
                    yaxis_title=T("province"),
                    height=500,
                )
                plot_chart(fig_growth, use_container_width=True)
    render_page_caveats()

# ==========================================
# PAGE 8: PREVISÕES (POLYNOMIAL + MONTHLY)
# ==========================================
with tab_forecast:
    st.title(T("title_forecast"))
    st.caption(T("forecast_caption"))
    st.caption(tab_story("forecast"))

    # --- Methodology explanation ---
    st.info(T("methodology"))

    pred_col1, pred_col2 = st.columns(2)
    with pred_col1:
        forecast_horizon = st.slider(T("forecast_horizon"), 1, 10, 5, key="forecast_h",
                                      help=T("forecast_horizon"))
    with pred_col2:
        group_amounts = "Valores" if st.session_state.lang == "PT" else "Amounts"
        group_volumes = "Volumes"
        forecast_group = single_choice_toggle(
            "Prioridade" if st.session_state.lang == "PT" else "Priority",
            [group_amounts, group_volumes],
            key="forecast_group",
        )

        grouped_indicators = {
            group_amounts: [
                "Transacções ATM (Valor)",
                "Transacções POS (Valor)",
                "Transacções Mobile Banking (Valor)",
                "Transacções Internet Banking (Valor)",
                "Carteiras Móveis - Depósitos (Valor)",
                "Carteiras Móveis - Levantamentos (Valor)",
                "Carteiras Móveis - Transferências (Valor)",
                "Carteiras Móveis - Pagamentos (Valor)",
            ],
            group_volumes: [
                "Transacções ATM (Volume)",
                "Transacções POS (Volume)",
                "Transacções Mobile Banking (Volume)",
                "Transacções Internet Banking (Volume)",
                "Carteiras Móveis - Depósitos (Volume)",
                "Carteiras Móveis - Levantamentos (Volume)",
                "Carteiras Móveis - Transferências (Volume)",
                "Carteiras Móveis - Pagamentos (Volume)",
            ],
        }
        forecast_indicator = st.selectbox(T("forecast_indicator"), grouped_indicators[forecast_group], 
            key="forecast_indicator",
            help=T("forecast_indicator")
        )

    def get_atm_txn_forecast_data(vol_or_val):
        if vol_or_val == 'vol':
            df = normalize_atm_txn(vol_df)
            return df, 'Total_Transactions'
        else:
            df = normalize_atm_txn(val_df)
            return df, 'Transactions_Amount'

    has_province = False
    wallet_scope_hint = None
    if forecast_indicator == "Transacções ATM (Volume)":
        src_df, metric_col = get_atm_txn_forecast_data('vol')
    elif forecast_indicator == "Transacções ATM (Valor)":
        src_df, metric_col = get_atm_txn_forecast_data('val')
    elif forecast_indicator == "Transacções POS (Volume)":
        src_df = pos_txn_df[pos_txn_df['Metric'].str.contains('Volume', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transacções POS (Valor)":
        src_df = pos_txn_df[pos_txn_df['Metric'].str.contains('Valor', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transacções Mobile Banking (Volume)":
        src_df = mob_df[mob_df['Metric'].str.contains('Volume', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transacções Mobile Banking (Valor)":
        src_df = mob_df[mob_df['Metric'].str.contains('Valor', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transacções Internet Banking (Volume)":
        src_df = net_df[net_df['Metric'].str.contains('Volume', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transacções Internet Banking (Valor)":
        src_df = net_df[net_df['Metric'].str.contains('Valor', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator.startswith("Carteiras Móveis - "):
        ime_map = {
            "Carteiras Móveis - Depósitos (Volume)": ("Depósitos", "Volume"),
            "Carteiras Móveis - Levantamentos (Volume)": ("Levantamentos", "Volume"),
            "Carteiras Móveis - Transferências (Volume)": ("Transferências", "Volume"),
            "Carteiras Móveis - Pagamentos (Volume)": ("Pagamentos", "Volume"),
            "Carteiras Móveis - Depósitos (Valor)": ("Depósitos", "Value"),
            "Carteiras Móveis - Levantamentos (Valor)": ("Levantamentos", "Value"),
            "Carteiras Móveis - Transferências (Valor)": ("Transferências", "Value"),
            "Carteiras Móveis - Pagamentos (Valor)": ("Pagamentos", "Value"),
        }
        tx_type, metric_col = ime_map[forecast_indicator]
        wallet_raw = ime_txn_district_df[ime_txn_district_df["Transaction_Type"] == tx_type].copy()
        src_df = wallet_raw.copy()
        if not wallet_raw.empty:
            scoped_geo = apply_geo_only(wallet_raw)
            if not scoped_geo.empty:
                src_df = scoped_geo
            else:
                scoped_prov = wallet_raw[wallet_raw["Province"].isin(selected_prov)].copy()
                if not scoped_prov.empty:
                    src_df = scoped_prov
                    wallet_scope_hint = (
                        "ℹ️ Não existem registos para o distrito seleccionado neste indicador; foi aplicado recorte por província."
                        if st.session_state.lang == "PT"
                        else "ℹ️ No records for the selected district in this indicator; province-level scope was applied."
                    )
                else:
                    src_df = wallet_raw
                    wallet_scope_hint = (
                        "ℹ️ Não existem registos para os filtros geográficos actuais; foi aplicada a série nacional."
                        if st.session_state.lang == "PT"
                        else "ℹ️ No records for the current geographic filters; national series was applied."
                    )
            has_province = "Province" in src_df.columns
    else:
        src_df = pd.DataFrame()
        metric_col = "Value"

    st.subheader(
        f"{T('national_forecast')} — {forecast_indicator}",
        help=(
            "Projecção principal para o indicador seleccionado, com histórico observado e valores projectados."
            if st.session_state.lang == "PT"
            else "Main projection for the selected indicator, showing observed history and forecasted values."
        ),
    )
    is_wallet_indicator = forecast_indicator.startswith("Carteiras Móveis - ")
    wallet_forecast_months = 3
    forecast_horizon_years = forecast_horizon
    if is_wallet_indicator:
        wallet_forecast_months = st.slider(
            "Horizonte (meses)" if st.session_state.lang == "PT" else "Horizon (months)",
            1,
            24,
            6,
            key="wallet_forecast_months",
        )
        forecast_horizon_years = max(1, math.ceil(wallet_forecast_months / 12))
        if wallet_scope_hint:
            st.caption(wallet_scope_hint)
        st.caption(
            "ℹ️ As previsões de Carteira Móvel baseiam-se na série mensal disponível (actualmente 2023-2025, 36 observações). "
            "A leitura é indicativa e mais adequada para curto prazo; não deve ser usada isoladamente "
            "para decisões de investimento de médio/longo prazo."
            if st.session_state.lang == "PT"
            else "ℹ️ Mobile Wallet forecasts use the available monthly series (currently 2023-2025, 36 observations). "
            "Interpretation is indicative and better suited for short-term use; it should not be used alone "
            "for medium/long-term investment decisions."
        )

    monthly_series = build_monthly_series(src_df, metric_col)
    fc_type = T("flow_label")
    fc_type_short = "Flow" if st.session_state.lang == "EN" else "Fluxo"
    fc_latest = monthly_series["Value"].iloc[-1] if not monthly_series.empty else 0
    fc1, fc2, fc3 = st.columns(3)
    fc1.metric(
        T("forecast_horizon"),
        f"{wallet_forecast_months} meses" if (is_wallet_indicator and st.session_state.lang == "PT")
        else (f"{wallet_forecast_months} months" if is_wallet_indicator else f"{forecast_horizon}"),
    )
    fc2.metric(T("indicator"), fc_type_short)
    fc3.metric(
        "Último valor observado" if st.session_state.lang == "PT" else "Last observed value",
        format_compact(fc_latest),
    )
    flow_note = (
        "ℹ️ Para indicadores de fluxo, é considerada a soma anual. "
        "Racional: fluxo mede actividade acumulada no período. "
        "Regra aplicada: agregam-se os 12 meses do ano."
        if st.session_state.lang == "PT"
        else "ℹ️ For flow indicators, annual sum is considered. "
        "Rationale: flow measures accumulated activity over the period. "
        "Applied rule: all 12 months are aggregated."
    )
    st.caption(flow_note)

    hist_label = T("historic")
    pred_label = T("forecast")
    hist_tag = "historic"
    pred_tag = "forecast"

    if len(monthly_series) >= 3:
        combined, r2, res_std, model_meta = select_best_forecast_model(
            monthly_series, n_future_years=forecast_horizon_years, indicator_name=forecast_indicator
        )

        if combined is not None:
            if is_wallet_indicator:
                pred_trim = combined[combined["Tipo"] == pred_tag].sort_values("t").head(wallet_forecast_months).copy()
                hist_keep = combined[combined["Tipo"] == hist_tag].copy()
                combined = pd.concat([hist_keep, pred_trim], ignore_index=True)
                combined["Tipo_Display"] = combined["Tipo"].replace({hist_tag: hist_label, pred_tag: pred_label})

                wallet_view = combined.copy()
                wallet_view["Período"] = wallet_view["t"].apply(t_to_period_label)
                recent_hist = wallet_view[wallet_view["Tipo"] == hist_tag].tail(18)
                wallet_plot = pd.concat([recent_hist, wallet_view[wallet_view["Tipo"] == pred_tag]], ignore_index=True)
                period_order = [t_to_period_label(t) for t in sorted(wallet_plot["t"].unique())]
                fig_wallet = px.line(
                    wallet_plot.sort_values("t"),
                    x="Período",
                    y="Value",
                    color="Tipo_Display",
                    markers=True,
                    category_orders={"Período": period_order},
                    title=(
                        "Projecção mensal de Carteira Móvel"
                        if st.session_state.lang == "PT"
                        else "Mobile Wallet monthly projection"
                    ),
                )
                fig_wallet.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-35)
                plot_chart(fig_wallet, use_container_width=True)
                future_table = wallet_view[wallet_view["Tipo"] == pred_tag][["Período", "Value", "Lower", "Upper"]].copy()
                if not future_table.empty:
                    future_table["Value"] = future_table["Value"].apply(format_compact)
                    future_table["Lower"] = future_table["Lower"].apply(format_compact)
                    future_table["Upper"] = future_table["Upper"].apply(format_compact)
                    st.dataframe(future_table, use_container_width=True, hide_index=True)

            yearly_fc = aggregate_forecast_yearly(combined, forecast_indicator, hist_label, pred_label)

            if not yearly_fc.empty:
                hist_yr = yearly_fc[yearly_fc['Tipo'] == hist_label]
                pred_yr = yearly_fc[yearly_fc['Tipo'] == pred_label]

                tipo_label = T("flow_label")
                if not is_wallet_indicator:
                    fig_fc = go.Figure()
                    fig_fc.add_trace(go.Bar(
                        x=hist_yr['Ano'], y=hist_yr['Valor'],
                        name=hist_label, marker_color='#636EFA',
                        text=[format_compact(v) for v in hist_yr['Valor']],
                        textposition='outside'
                    ))

                    if not pred_yr.empty:
                        fig_fc.add_trace(go.Scatter(
                            x=pred_yr['Ano'], y=pred_yr['Upper'],
                            mode='lines', line=dict(width=0),
                            showlegend=False, hoverinfo='skip'
                        ))
                        fig_fc.add_trace(go.Scatter(
                            x=pred_yr['Ano'], y=pred_yr['Lower'],
                            mode='lines', line=dict(width=0),
                            fill='tonexty', fillcolor='rgba(239,85,59,0.15)',
                            showlegend=False, hoverinfo='skip'
                        ))
                        fig_fc.add_trace(go.Scatter(
                            x=pred_yr['Ano'], y=pred_yr['Valor'],
                            mode='lines+markers', name=pred_label,
                            marker_color='#EF553B', line=dict(width=3, dash='dash'),
                            text=[format_compact(v) for v in pred_yr['Valor']],
                            textposition='top center'
                        ))

                    fig_fc.update_layout(
                        title=f"{T('forecast')}: {forecast_indicator}",
                        xaxis=dict(title=T("year"), dtick=1),
                        yaxis=dict(title=T("value"), rangemode='tozero'),
                        legend=dict(x=0.01, y=0.99),
                        height=500
                    )
                    plot_chart(fig_fc, use_container_width=True)

                holdout_smape = model_meta.get("holdout_smape")
                holdout_mae = model_meta.get("holdout_mae")
                holdout_smape_label = "N/A" if holdout_smape is None else f"{holdout_smape:.2f}%"
                holdout_mae_label = "N/A" if holdout_mae is None else format_compact(holdout_mae)
                r2_label = "N/A" if r2 is None else f"{r2:.3f}"
                if is_wallet_indicator:
                    hist_tail = combined[combined["Tipo"] == hist_tag].sort_values("t")
                    pred_tail = combined[combined["Tipo"] == pred_tag].sort_values("t")
                    current_v = float(hist_tail.iloc[-1]["Value"]) if not hist_tail.empty else None
                    projected_v = float(pred_tail.iloc[-1]["Value"]) if not pred_tail.empty else None
                    horizon_for_rate = wallet_forecast_months
                    avg_change_abs = 0.0
                    avg_change_pct = None
                    if current_v is not None and projected_v is not None and horizon_for_rate > 0:
                        avg_change_abs = (projected_v - current_v) / horizon_for_rate
                        if current_v > 0:
                            avg_change_pct = (((projected_v / current_v) ** (1 / horizon_for_rate)) - 1) * 100
                else:
                    current_v = hist_yr.iloc[-1]["Valor"] if not hist_yr.empty else None
                    projected_v = pred_yr.iloc[-1]["Valor"] if not pred_yr.empty else None
                    horizon_for_rate = forecast_horizon
                    avg_change_abs = 0.0
                    avg_change_pct = None
                    if current_v is not None and projected_v is not None and horizon_for_rate > 0:
                        avg_change_abs = (projected_v - current_v) / horizon_for_rate
                        if current_v > 0:
                            avg_change_pct = (((projected_v / current_v) ** (1 / horizon_for_rate)) - 1) * 100

                change_pct = 0.0
                if current_v is not None and projected_v is not None and current_v > 0:
                    change_pct = ((projected_v - current_v) / current_v) * 100

                if change_pct > 3:
                    trend_pt, trend_en = "aumento", "increase"
                elif change_pct < -3:
                    trend_pt, trend_en = "redução", "decline"
                else:
                    trend_pt, trend_en = "estabilidade", "stability"

                if holdout_smape is not None:
                    if holdout_smape <= 10:
                        conf_pt, conf_en = "elevada", "high"
                    elif holdout_smape <= 20:
                        conf_pt, conf_en = "moderada", "moderate"
                    else:
                        conf_pt, conf_en = "baixa", "low"
                elif r2 is not None:
                    if r2 >= 0.8:
                        conf_pt, conf_en = "elevada", "high"
                    elif r2 >= 0.5:
                        conf_pt, conf_en = "moderada", "moderate"
                    else:
                        conf_pt, conf_en = "baixa", "low"
                else:
                    conf_pt, conf_en = "moderada", "moderate"

                if st.session_state.lang == "PT":
                    r2_sentence = f"O ajuste histórico é forte (R²={r2:.0%}). " if (r2 is not None and r2 >= 0.75) else ""
                    avg_pct_label = (
                        f"{avg_change_pct:+.1f}%"
                        if avg_change_pct is not None
                        else "N/A"
                    )
                    if is_wallet_indicator:
                        summary = (
                            f"Para o indicador {forecast_indicator}, a projecção aponta para {trend_pt} "
                            f"no horizonte de {wallet_forecast_months} meses, com confiança {conf_pt}. "
                            f"Em média, a variação mensal estimada é de {avg_pct_label} "
                            f"({format_compact(avg_change_abs)} por mês). "
                            f"{r2_sentence}"
                        )
                    else:
                        summary = (
                            f"Para o indicador {forecast_indicator}, a projecção aponta para {trend_pt} "
                            f"no horizonte de {forecast_horizon} anos, com confiança {conf_pt}. "
                            f"Em média, a variação anual estimada é de {avg_pct_label} "
                            f"({format_compact(avg_change_abs)} por ano). "
                            f"{r2_sentence}"
                        )
                else:
                    r2_sentence = f"Historical fit is strong (R²={r2:.0%}). " if (r2 is not None and r2 >= 0.75) else ""
                    avg_pct_label = (
                        f"{avg_change_pct:+.1f}%"
                        if avg_change_pct is not None
                        else "N/A"
                    )
                    if is_wallet_indicator:
                        summary = (
                            f"For {forecast_indicator}, the projection indicates an expected {trend_en} "
                            f"over the {wallet_forecast_months}-month horizon, with {conf_en} confidence. "
                            f"Average estimated monthly change is {avg_pct_label} "
                            f"({format_compact(avg_change_abs)} per month). "
                            f"{r2_sentence}"
                        )
                    else:
                        summary = (
                            f"For {forecast_indicator}, the projection indicates an expected {trend_en} "
                            f"over the {forecast_horizon}-year horizon, with {conf_en} confidence. "
                            f"Average estimated annual change is {avg_pct_label} "
                            f"({format_compact(avg_change_abs)} per year). "
                            f"{r2_sentence}"
                        )

                st.info(summary)
                with st.expander("Detalhes técnicos" if st.session_state.lang == "PT" else "Technical details"):
                    st.write(
                        f"**Model:** {model_meta['model_label']} · "
                        f"**Walk-forward sMAPE:** {holdout_smape_label} · "
                        f"**Walk-forward MAE:** {holdout_mae_label} · "
                        f"**R²:** {r2_label} · "
                        f"**{T('indicator')}:** {tipo_label} · "
                        f"**Data points:** {len(monthly_series)} · "
                        f"**Eval points:** {model_meta.get('n_eval', 'N/A')}"
                    )
    else:
        st.warning(T("insufficient_data"))

    # --- Province-level Forecast ---
    if has_province and 'Province' in src_df.columns:
        st.subheader(
            f"{T('province_forecast')} — {forecast_indicator}",
            help=(
                "Compara trajectórias por província para o mesmo indicador, no mesmo horizonte."
                if st.session_state.lang == "PT"
                else "Compares province trajectories for the same indicator under the same horizon."
            ),
        )

        provinces = [p for p in selected_prov if p in src_df['Province'].unique()]

        if provinces:
            if is_wallet_indicator:
                prov_plot_parts = []
                summary_rows = []
                period_order = []
                for prov in provinces:
                    prov_data = src_df[src_df["Province"] == prov]
                    prov_monthly = build_monthly_series(prov_data, metric_col)
                    if len(prov_monthly) >= 3:
                        prov_combined, _, _, _ = select_best_forecast_model(
                            prov_monthly, n_future_years=forecast_horizon_years, indicator_name=forecast_indicator
                        )
                        if prov_combined is None:
                            continue
                        prov_pred = prov_combined[prov_combined["Tipo"] == pred_tag].sort_values("t").head(wallet_forecast_months).copy()
                        prov_hist = prov_combined[prov_combined["Tipo"] == hist_tag].copy()
                        prov_view = pd.concat([prov_hist, prov_pred], ignore_index=True).sort_values("t")
                        prov_view["Tipo_Display"] = prov_view["Tipo"].replace({hist_tag: hist_label, pred_tag: pred_label})
                        prov_view["Período"] = prov_view["t"].apply(t_to_period_label)
                        prov_view["t_order"] = prov_view["t"]
                        prov_view[T("province")] = prov
                        recent_hist = prov_view[prov_view["Tipo"] == hist_tag].tail(12)
                        prov_plot_parts.append(pd.concat([recent_hist, prov_view[prov_view["Tipo"] == pred_tag]], ignore_index=True))
                        period_order.extend(prov_view["t"].tolist())

                        hist_tail = prov_view[prov_view["Tipo"] == hist_tag].sort_values("t")
                        pred_tail = prov_view[prov_view["Tipo"] == pred_tag].sort_values("t")
                        if not hist_tail.empty and not pred_tail.empty:
                            current = float(hist_tail.iloc[-1]["Value"])
                            projected = float(pred_tail.iloc[-1]["Value"])
                            growth_pct = ((projected - current) / current * 100) if current > 0 else 0.0
                            summary_rows.append(
                                {
                                    T("province"): prov,
                                    ("Último período observado" if st.session_state.lang == "PT" else "Latest observed period"): hist_tail.iloc[-1]["Período"],
                                    ("Valor observado" if st.session_state.lang == "PT" else "Observed value"): format_compact(current),
                                    ("Fim da projecção" if st.session_state.lang == "PT" else "End forecast period"): pred_tail.iloc[-1]["Período"],
                                    ("Valor projetado" if st.session_state.lang == "PT" else "Forecast value"): format_compact(projected),
                                    T("growth_pct"): f"{growth_pct:+.1f}%",
                                }
                            )

                if prov_plot_parts:
                    all_prov = pd.concat(prov_plot_parts, ignore_index=True).sort_values(["t_order", T("province")])
                    period_labels = [t_to_period_label(t) for t in sorted(set(period_order))]
                    fig_prov_fc = px.line(
                        all_prov,
                        x="Período",
                        y="Value",
                        color=T("province"),
                        line_dash="Tipo_Display",
                        markers=True,
                        category_orders={"Período": period_labels},
                        title=f"{T('province_forecast')}: {forecast_indicator}",
                        line_dash_map={hist_label: "solid", pred_label: "dash"},
                    )
                    fig_prov_fc.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-35)
                    plot_chart(fig_prov_fc, use_container_width=True)

                    st.subheader(
                        T("forecast_summary"),
                        help=(
                            "Compara o último mês observado com o mês final projectado por província."
                            if st.session_state.lang == "PT"
                            else "Compares the latest observed month with the final projected month by province."
                        ),
                    )
                    if summary_rows:
                        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
                else:
                    st.info(T("insufficient_data"))
            else:
                prov_results = []
                for prov in provinces:
                    prov_data = src_df[src_df['Province'] == prov]
                    prov_monthly = build_monthly_series(prov_data, metric_col)
                    if len(prov_monthly) >= 3:
                        prov_combined, prov_r2, _, prov_meta = select_best_forecast_model(
                            prov_monthly, n_future_years=forecast_horizon_years, indicator_name=forecast_indicator
                        )
                        if prov_combined is not None:
                            prov_yearly = aggregate_forecast_yearly(prov_combined, forecast_indicator, hist_label, pred_label)
                            prov_yearly["Model"] = prov_meta["model_label"]
                            prov_yearly[T("province")] = prov
                            prov_results.append(prov_yearly)

                if prov_results:
                    all_prov = pd.concat(prov_results, ignore_index=True)

                    fig_prov_fc = px.line(
                        all_prov, x='Ano', y='Valor', color=T("province"),
                        line_dash='Tipo', markers=True,
                        title=f"{T('province_forecast')}: {forecast_indicator}",
                        line_dash_map={hist_label: 'solid', pred_label: 'dash'}
                    )
                    fig_prov_fc.update_layout(xaxis=dict(dtick=1), yaxis=dict(rangemode='tozero'))
                    plot_chart(fig_prov_fc, use_container_width=True)

                    st.subheader(
                        T("forecast_summary"),
                        help=(
                            "Compara o valor observado mais recente com o valor projectado no fim do horizonte por província."
                            if st.session_state.lang == "PT"
                            else "Compares latest observed value against projected end-of-horizon value by province."
                        ),
                    )
                    summary_rows = []
                    for prov in provinces:
                        prov_data_fc = all_prov[all_prov[T("province")] == prov]
                        hist = prov_data_fc[prov_data_fc['Tipo'] == hist_label]
                        pred = prov_data_fc[prov_data_fc['Tipo'] == pred_label]
                        if not hist.empty and not pred.empty:
                            current = hist.iloc[-1]['Valor']
                            projected = pred.iloc[-1]['Valor']
                            growth_pct = ((projected - current) / current * 100) if current > 0 else 0
                            summary_rows.append({
                                T("province"): prov,
                                f'Actual ({int(hist.iloc[-1]["Ano"])})': f"{current:,.0f}",
                                f'{T("forecast")} ({int(pred.iloc[-1]["Ano"])})': f"{projected:,.0f}",
                                T("growth_pct"): f"{growth_pct:.1f}%"
                            })

                    if summary_rows:
                        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # --- Custom Growth Simulator (CAGR-seeded) ---
    st.markdown("---")
    st.subheader(
        T("manual_simulator"),
        help=(
            "Ferramenta de sensibilidade: aplica uma taxa anual manual sobre o último valor histórico para testar cenários."
            if st.session_state.lang == "PT"
            else "Sensitivity tool: applies a manual annual rate to the latest historical value for scenario testing."
        ),
    )
    st.markdown(T("manual_sim_desc"))

    yearly_totals = src_df.groupby('Year')[metric_col].sum().reset_index().sort_values('Year')

    default_cagr = 15
    if len(yearly_totals) >= 2:
        first_val = yearly_totals.iloc[0][metric_col]
        last_val = yearly_totals.iloc[-1][metric_col]
        n_years = yearly_totals.iloc[-1]['Year'] - yearly_totals.iloc[0]['Year']
        if first_val > 0 and n_years > 0:
            cagr = ((last_val / first_val) ** (1 / n_years) - 1) * 100
            default_cagr = int(max(0, min(50, round(cagr))))

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        growth = st.slider(T("annual_rate"), 0, 50, default_cagr, key="manual_growth",
                           help=f"CAGR: {default_cagr}%") / 100
    with sim_col2:
        horizon_manual = st.slider(T("projection_years"), 1, 10, 5, key="manual_horizon")

    if not yearly_totals.empty:
        base_year = int(yearly_totals.iloc[-1]['Year'])
        base_value = yearly_totals.iloc[-1][metric_col]

        sim_years = list(range(base_year, base_year + horizon_manual + 1))
        sim_vals = [base_value * (1 + growth) ** (y - base_year) for y in sim_years]

        sim_df = pd.DataFrame({T("year"): sim_years, T("value"): sim_vals})
        fig_sim = px.line(sim_df, x=T("year"), y=T("value"), markers=True,
                          title=f"{forecast_indicator} — {growth*100:.0f}%/{T('year').lower()}")
        fig_sim.update_layout(xaxis=dict(dtick=1), yaxis=dict(rangemode='tozero'))
        plot_chart(fig_sim, use_container_width=True)

        st.metric(
            f"{T('projection_for')} {base_year + horizon_manual}",
            format_compact(sim_vals[-1]),
            delta=f"{((sim_vals[-1] - base_value) / base_value * 100):.1f}% {T('total_growth')}" if base_value > 0 else None
        )
    render_page_caveats(
        [
            "Previsões incluem apenas indicadores de fluxo (volume e valor) e séries de Carteira Móvel.",
        ]
        if st.session_state.lang == "PT"
        else [
            "Forecasts include flow indicators only (volume/value) plus Mobile Wallet series.",
        ]
    )

# ==========================================
# PAGE 9: INSIGHTS / OPPORTUNITIES
# ==========================================
with tab_decision:
    st.title(T("title_decision"))
    st.caption(T("caption_decision"))
    st.caption(tab_story("decision"))
    st.write(
        "Esta página resume os principais sinais para apoiar priorização, planeamento e comunicação dos resultados."
        if st.session_state.lang == "PT"
        else "This page summarizes the main signals to support prioritization, planning, and communication."
    )

    # Data freshness and governance context.
    st.subheader("Actualização e Governação dos Dados" if st.session_state.lang == "PT" else "Data Freshness and Governance")
    fresh_col1, fresh_col2, fresh_col3, fresh_col4 = st.columns(4)

    latest_banking_year = int(max(all_years)) if all_years else None
    latest_ime_period = "N/A"
    if not ime_sub_df.empty:
        sub_2025 = ime_sub_df.copy()
        sub_2025["Month_Num"] = sub_2025["Month"].map(
            {
                "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6,
                "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12,
            }
        )
        sub_2025 = sub_2025.dropna(subset=["Month_Num"])
        if not sub_2025.empty:
            mx = sub_2025.sort_values(["Year", "Month_Num"]).iloc[-1]
            latest_ime_period = f"{localize_month(mx['Month'])} {int(mx['Year'])}"

    latest_fi_period = "N/A"
    if not fi_indicators_df.empty and "Period" in fi_indicators_df.columns:
        latest_fi_period = str(fi_indicators_df["Period"].dropna().astype(str).max())
    latest_access_period = "N/A"
    if not access_points_df.empty and {"Year", "Quarter"}.issubset(access_points_df.columns):
        ap_year = pd.to_numeric(access_points_df["Year"], errors="coerce")
        ap_quarter = access_points_df["Quarter"]
        if ap_year.notna().any():
            latest_idx = ap_year.idxmax()
            latest_access_period = f"{int(ap_year.loc[latest_idx])}{str(ap_quarter.loc[latest_idx]).strip()}"

    fresh_col1.metric(
        "Core Banking Series" if st.session_state.lang == "EN" else "Série Bancária Base",
        str(latest_banking_year) if latest_banking_year is not None else "N/A",
    )
    fresh_col2.metric(
        "Mobile Wallet District Series" if st.session_state.lang == "EN" else "Série Distrital de Carteira Móvel",
        latest_ime_period,
    )
    fresh_col3.metric(
        "Access Points Release" if st.session_state.lang == "EN" else "Publicação de Pontos de Acesso",
        latest_access_period,
    )
    fresh_col4.metric(
        "Inclusion Release" if st.session_state.lang == "EN" else "Publicação de Inclusão",
        latest_fi_period,
    )
    st.caption(
        "Publication cadence considered: monthly (electronic banking) and quarterly (official inclusion/access bulletins)."
        if st.session_state.lang == "EN"
        else "Cadência considerada de publicação: mensal (banca electrónica) e trimestral (boletins oficiais de inclusão/acesso)."
    )

    st.markdown("---")
    st.subheader(
        "Comparador distrital para priorização de investimento"
        if st.session_state.lang == "PT"
        else "District comparator for investment prioritization",
        help=(
            "Compara dois distritos em indicadores operacionais e de transacção para triagem relativa."
            if st.session_state.lang == "PT"
            else "Compares two districts on operational and transaction indicators for relative screening."
        ),
    )
    st.caption(
        "Comparação directa entre dois distritos no último período disponível por indicador. A leitura apoia triagem relativa, não substitui due diligence local."
        if st.session_state.lang == "PT"
        else "Direct comparison between two districts on the latest available period by indicator. This supports relative screening, not local due diligence."
    )

    pair_frames = []
    for dfx in [acc_df, card_df, atm_df, pos_df, ime_sub_df, ime_agents_df, ime_txn_district_df]:
        if {"Province", "District"}.issubset(dfx.columns):
            pair_frames.append(dfx[["Province", "District"]].dropna().astype(str))
    if pair_frames:
        district_pairs = (
            pd.concat(pair_frames, ignore_index=True)
            .drop_duplicates()
            .sort_values(["Province", "District"])
            .reset_index(drop=True)
        )
    else:
        district_pairs = pd.DataFrame(columns=["Province", "District"])

    if district_pairs.empty:
        st.info("Sem dados distritais para comparar." if st.session_state.lang == "PT" else "No district data available for comparison.")
    else:
        default_pair_a = ("Província de Maputo", "Cidade de Maputo")
        default_pair_b = ("Sofala", "Cidade da Beira")

        prov_options = sorted(district_pairs["Province"].dropna().astype(str).unique().tolist())
        comp_col1, comp_col2 = st.columns(2)
        with comp_col1:
            province_a = st.selectbox(
                "Província A" if st.session_state.lang == "PT" else "Province A",
                prov_options,
                index=(prov_options.index(default_pair_a[0]) if default_pair_a[0] in prov_options else 0),
                key="cmp_province_a",
            )
            dist_options_a = sorted(
                district_pairs[district_pairs["Province"] == province_a]["District"].astype(str).unique().tolist()
            )
            district_a = st.selectbox(
                "Distrito A" if st.session_state.lang == "PT" else "District A",
                dist_options_a,
                index=(dist_options_a.index(default_pair_a[1]) if default_pair_a[0] == province_a and default_pair_a[1] in dist_options_a else 0),
                key="cmp_district_a",
            )
        with comp_col2:
            province_b = st.selectbox(
                "Província B" if st.session_state.lang == "PT" else "Province B",
                prov_options,
                index=(prov_options.index(default_pair_b[0]) if default_pair_b[0] in prov_options else min(1, len(prov_options) - 1)),
                key="cmp_province_b",
            )
            dist_options_b = sorted(
                district_pairs[district_pairs["Province"] == province_b]["District"].astype(str).unique().tolist()
            )
            district_b = st.selectbox(
                "Distrito B" if st.session_state.lang == "PT" else "District B",
                dist_options_b,
                index=(dist_options_b.index(default_pair_b[1]) if default_pair_b[0] == province_b and default_pair_b[1] in dist_options_b else 0),
                key="cmp_district_b",
            )

        pair_a = (province_a, district_a)
        pair_b = (province_b, district_b)
        label_a = f"{province_a} - {district_a}"
        label_b = f"{province_b} - {district_b}"
        if pair_a == pair_b:
            st.warning("Seleccionar dois distritos diferentes." if st.session_state.lang == "PT" else "Select two different districts.")

        if pair_a != pair_b:
            stock_year = selected_year if selected_year in set(acc_df["Year"].unique()) else int(max(acc_df["Year"]))
            acc_cmp = last_month_snapshot(acc_df[acc_df["Year"] == stock_year]).copy()
            card_cmp = last_month_snapshot(card_df[card_df["Year"] == stock_year]).copy()
            atm_cmp = last_month_snapshot(atm_df[atm_df["Year"] == stock_year]).copy()
            pos_cmp = last_month_snapshot(pos_df[pos_df["Year"] == stock_year]).copy()

            ime_year_cmp = int(pd.to_numeric(ime_txn_district_df["Year"], errors="coerce").dropna().max()) if not ime_txn_district_df.empty else None
            tx_cmp = ime_txn_district_df[ime_txn_district_df["Year"] == ime_year_cmp].copy() if ime_year_cmp else pd.DataFrame()
            sub_cmp = ime_sub_df[ime_sub_df["Year"] == ime_year_cmp].copy() if ime_year_cmp else pd.DataFrame()
            ag_cmp = ime_agents_df[ime_agents_df["Year"] == ime_year_cmp].copy() if ime_year_cmp else pd.DataFrame()
            if not tx_cmp.empty:
                tx_cmp["Month_Ord"] = tx_cmp["Month"].astype(str).map(MONTH_RANK)
                latest_m = tx_cmp["Month_Ord"].max()
                tx_cmp = tx_cmp[tx_cmp["Month_Ord"] == latest_m].copy()
            if not sub_cmp.empty:
                sub_cmp = sub_cmp[sub_cmp["Month"].astype(str) == "Dezembro"].copy()
            if not ag_cmp.empty:
                ag_cmp = ag_cmp[ag_cmp["Month"].astype(str) == "Dezembro"].copy()

            def _dist_sum(df: pd.DataFrame, value_col: str) -> dict[str, float]:
                if df.empty or value_col not in df.columns:
                    return {label_a: 0.0, label_b: 0.0}
                tmp = (
                    df[
                        ((df["Province"] == pair_a[0]) & (df["District"] == pair_a[1]))
                        | ((df["Province"] == pair_b[0]) & (df["District"] == pair_b[1]))
                    ]
                    .assign(_Label=lambda x: x["Province"] + " - " + x["District"])
                    .groupby("_Label", as_index=False)[value_col]
                    .sum()
                    .set_index("_Label")[value_col]
                    .to_dict()
                )
                return {label_a: float(tmp.get(label_a, 0.0)), label_b: float(tmp.get(label_b, 0.0))}

            metric_rows: list[dict[str, object]] = []
            for label, values in [
                ("Subscrições de Carteira Móvel", _dist_sum(sub_cmp, "Subscribers")),
                ("Agentes de Carteira Móvel", _dist_sum(ag_cmp, "Agents")),
                ("Contas Bancárias", _dist_sum(acc_cmp, "Total_Accounts")),
                ("Cartões Bancários", _dist_sum(card_cmp, "Total_Cards")),
                ("ATM", _dist_sum(atm_cmp, "ATMs_Number")),
                ("POS", _dist_sum(pos_cmp, "POSs_Number")),
            ]:
                metric_rows.extend(
                    [
                        {"Metric": label, "District": label_a, "Value": values[label_a]},
                        {"Metric": label, "District": label_b, "Value": values[label_b]},
                    ]
                )

            for tx_name in ["Depósitos", "Levantamentos", "Transferências", "Pagamentos"]:
                tx_part = tx_cmp[tx_cmp["Transaction_Type"] == tx_name].copy() if not tx_cmp.empty else pd.DataFrame()
                vol_vals = _dist_sum(tx_part, "Volume")
                val_vals = _dist_sum(tx_part, "Value")
                metric_rows.extend(
                    [
                        {"Metric": f"Carteiras Móveis - {tx_name} (Volume)", "District": label_a, "Value": vol_vals[label_a]},
                        {"Metric": f"Carteiras Móveis - {tx_name} (Volume)", "District": label_b, "Value": vol_vals[label_b]},
                        {"Metric": f"Carteiras Móveis - {tx_name} (Valor)", "District": label_a, "Value": val_vals[label_a]},
                        {"Metric": f"Carteiras Móveis - {tx_name} (Valor)", "District": label_b, "Value": val_vals[label_b]},
                    ]
                )

            inclusion_context = {}
            acc_dist_values = _dist_sum(acc_cmp, "Total_Accounts")
            for lbl, pair in [(label_a, pair_a), (label_b, pair_b)]:
                dist_acc = float(acc_dist_values.get(lbl, 0.0))
                dist_pop = lookup_district_denominator(pair[0], pair[1], stock_year)
                inclusion_context[lbl] = (dist_acc / dist_pop) if dist_pop > 0 else 0.0
            metric_rows.extend(
                [
                    {"Metric": "Inclusão (contas por pessoa elegível, contexto distrital)", "District": label_a, "Value": inclusion_context[label_a]},
                    {"Metric": "Inclusão (contas por pessoa elegível, contexto distrital)", "District": label_b, "Value": inclusion_context[label_b]},
                ]
            )

            cmp_df = pd.DataFrame(metric_rows)
            flow_metric_order = [
                "Carteiras Móveis - Depósitos (Volume)",
                "Carteiras Móveis - Depósitos (Valor)",
                "Carteiras Móveis - Levantamentos (Volume)",
                "Carteiras Móveis - Levantamentos (Valor)",
                "Carteiras Móveis - Transferências (Volume)",
                "Carteiras Móveis - Transferências (Valor)",
                "Carteiras Móveis - Pagamentos (Volume)",
                "Carteiras Móveis - Pagamentos (Valor)",
            ]
            core_metric_order = [
                "Subscrições de Carteira Móvel",
                "Agentes de Carteira Móvel",
                "Contas Bancárias",
                "Cartões Bancários",
                "ATM",
                "POS",
                "Inclusão (contas por pessoa elegível, contexto distrital)",
            ]
            metric_order = flow_metric_order + core_metric_order
            order_map = {m: i for i, m in enumerate(metric_order)}

            flow_chart_df = cmp_df[
                ~cmp_df["Metric"].isin(
                    {
                        "Inclusão (contas por pessoa elegível, contexto distrital)",
                        "ATM",
                        "POS",
                        "Contas Bancárias",
                        "Cartões Bancários",
                    }
                )
            ].copy()
            flow_chart_df["order"] = flow_chart_df["Metric"].map(order_map).fillna(999)
            flow_chart_df = flow_chart_df.sort_values(["order", "District"]).drop(columns=["order"])
            fig_flow_compare = px.bar(
                flow_chart_df,
                x="Metric",
                y="Value",
                color="District",
                barmode="group",
                text=[format_compact(v) for v in flow_chart_df["Value"]],
                title=(
                    "Comparação directa por indicador (fluxo primeiro)"
                    if st.session_state.lang == "PT"
                    else "Direct indicator comparison (flow first)"
                ),
            )
            fig_flow_compare.update_layout(yaxis=dict(rangemode="tozero"), xaxis_tickangle=-25)
            plot_chart(fig_flow_compare, use_container_width=True)

            wide = cmp_df.pivot_table(index="Metric", columns="District", values="Value", aggfunc="sum", fill_value=0).reset_index()
            if label_a in wide.columns and label_b in wide.columns:
                wide["order"] = wide["Metric"].map(order_map).fillna(999)
                wide = wide.sort_values("order").drop(columns=["order"])
                wide["Delta"] = wide[label_a] - wide[label_b]
                wide["Delta_%"] = wide.apply(
                    lambda r: ((r["Delta"] / r[label_b]) * 100) if r[label_b] > 0 else None,
                    axis=1,
                )
                show_wide = wide.copy()
                show_wide[label_a] = show_wide[label_a].apply(format_compact)
                show_wide[label_b] = show_wide[label_b].apply(format_compact)
                show_wide["Delta"] = show_wide["Delta"].apply(format_compact)
                show_wide["Delta_%"] = show_wide["Delta_%"].apply(lambda v: "N/A" if pd.isna(v) else f"{v:+.1f}%")
                st.dataframe(show_wide, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader(
        "Maiores oportunidades identificadas" if st.session_state.lang == "PT" else "Main opportunities identified",
        help=(
            "Pontuação composta para priorização relativa entre províncias, com pesos explícitos."
            if st.session_state.lang == "PT"
            else "Composite score for relative province prioritization with explicit weights."
        ),
    )
    st.caption(
        "Weighted score (0-100): demand potential 35, digital momentum 25, monetization signal 25, infrastructure gap 15."
        if st.session_state.lang == "EN"
        else "Pontuação ponderada (0-100): potencial de procura 35, momento digital 25, sinal de monetização 25, lacuna de infraestrutura 15."
    )
    st.caption(
        (
            "ℹ️ Definições: momento digital = crescimento de subscrições de Carteira Móvel ao longo do ano; "
            "lacuna de infraestrutura = menor densidade de ATM+POS por 100 mil habitantes."
        )
        if st.session_state.lang == "PT"
        else (
            "ℹ️ Definitions: digital momentum = growth of Mobile Wallet subscriptions over the year; "
            "infrastructure gap = lower ATM+POS density per 100k population."
        )
    )
    st.caption(
        (
            f"Contexto adicional de mercado móvel: [INCM Acervo]({INCM_SOURCE_TELECOM_URL}) (2025 T2). "
            "Uso contextual; não substitui indicadores oficiais de inclusão do Banco de Moçambique."
        )
        if st.session_state.lang == "PT"
        else (
            f"Additional mobile-market context: [INCM Acervo]({INCM_SOURCE_TELECOM_URL}) (2025 Q2). "
            "Context use only; does not replace official Bank of Mozambique inclusion indicators."
        )
    )

    opp_year = selected_year
    opp_df = build_scope_opportunity_df(opp_year)

    if opp_df.empty:
        st.info("Opportunity score not available for current filters." if st.session_state.lang == "EN" else "Pontuação de oportunidade indisponível para os filtros actuais.")
    else:
        show_cols = [
            "Province",
            "Opportunity_Score",
            "Demand_Potential_Score",
            "Digital_Momentum_Score",
            "Monetization_Signal_Score",
            "Infrastructure_Gap_Score",
        ]
        table_df = opp_df[show_cols].copy()
        table_df = table_df.rename(
            columns={
                "Province": T("province"),
                "Opportunity_Score": "Opportunity Score" if st.session_state.lang == "EN" else "Pontuação",
                "Demand_Potential_Score": "Demand" if st.session_state.lang == "EN" else "Procura",
                "Digital_Momentum_Score": "Digital" if st.session_state.lang == "EN" else "Digital",
                "Monetization_Signal_Score": "Monetization" if st.session_state.lang == "EN" else "Monetização",
                "Infrastructure_Gap_Score": "Infrastructure Gap" if st.session_state.lang == "EN" else "Lacuna de Infraestrutura",
            }
        )
        st.dataframe(table_df.round(1), use_container_width=True, hide_index=True)

        comp_df = opp_df.copy()
        comp_df = comp_df.rename(
            columns={
                "Demand_Potential_Score": "Demand" if st.session_state.lang == "EN" else "Procura",
                "Digital_Momentum_Score": "Digital",
                "Monetization_Signal_Score": "Monetization" if st.session_state.lang == "EN" else "Monetização",
                "Infrastructure_Gap_Score": "Infrastructure Gap" if st.session_state.lang == "EN" else "Lacuna de Infraestrutura",
            }
        )
        comp_long = comp_df.melt(
            id_vars=["Province"],
            value_vars=[
                "Demand" if st.session_state.lang == "EN" else "Procura",
                "Digital",
                "Monetization" if st.session_state.lang == "EN" else "Monetização",
                "Infrastructure Gap" if st.session_state.lang == "EN" else "Lacuna de Infraestrutura",
            ],
            var_name="Component",
            value_name="Score",
        )
        province_order = opp_df.sort_values("Opportunity_Score", ascending=False)["Province"].astype(str).tolist()
        comp_long["Province"] = pd.Categorical(comp_long["Province"].astype(str), categories=province_order, ordered=True)
        comp_long = comp_long.sort_values(["Province", "Component"])
        component_defs = (
            {
                "Procura": "Menor penetração de contas por população elegível = maior espaço de expansão.",
                "Digital": "Crescimento de subscrições de Carteira Móvel ao longo do ano.",
                "Monetização": "Maior valor transaccionado por subscrição de Carteira Móvel.",
                "Lacuna de Infraestrutura": "Menor densidade de ATM+POS por 100 mil habitantes.",
            }
            if st.session_state.lang == "PT"
            else {
                "Demand": "Lower account penetration vs eligible population = higher expansion room.",
                "Digital": "Growth of Mobile Wallet subscriptions over the year.",
                "Monetization": "Higher transaction value per Mobile Wallet subscription.",
                "Infrastructure Gap": "Lower ATM+POS density per 100k population.",
            }
        )
        comp_long["Definition"] = comp_long["Component"].map(component_defs)
        fig_opp = px.bar(
            comp_long,
            x="Province",
            y="Score",
            color="Component",
            barmode="stack",
            category_orders={"Province": province_order},
            custom_data=["Definition"],
            hover_data={"Score": ":.1f", "Definition": False},
            title="Score decomposition by province" if st.session_state.lang == "EN" else "Decomposição da pontuação por província",
        )
        definition_label = "Definição" if st.session_state.lang == "PT" else "Definition"
        fig_opp.update_traces(
            hovertemplate=(
                f"{T('province')}: %{{x}}<br>"
                "Componente: %{fullData.name}<br>"
                "Score: %{y:.1f}<br>"
                f"{definition_label}: %{{customdata[0]}}<extra></extra>"
            ),
            selector=dict(type="bar"),
            offsetgroup="opportunity_stack",
        )
        fig_opp.update_layout(barmode="stack", yaxis=dict(rangemode="tozero"))
        plot_chart(fig_opp, use_container_width=True)

        st.markdown(
            "**Top 3 opportunity rationale**" if st.session_state.lang == "EN" else "**Racional das 3 maiores oportunidades**"
        )
        for _, row in opp_df.head(3).iterrows():
            reason = build_opportunity_reason(row, lang=st.session_state.lang)
            st.write(
                f"- {row['Province']} (score {row['Opportunity_Score']:.1f}): {reason}"
            )

    st.markdown("---")
    st.subheader(
        "Evolução do indicador em cenários alternativos"
        if st.session_state.lang == "PT"
        else "Indicator evolution under alternative scenarios",
        help=(
            "Compara trajectórias Conservador/Base/Acelerado para leitura de intervalo de planeamento."
            if st.session_state.lang == "PT"
            else "Compares Conservative/Base/Accelerated paths as a planning range."
        ),
    )
    st.caption(
        "A trajectória Base segue o padrão histórico; Conservador e Acelerado ajustam esse ritmo para leitura de intervalo."
        if st.session_state.lang == "PT"
        else "The Base path follows historical pattern; Conservative and Accelerated adjust that pace for range reading."
    )
    st.caption(
        "ℹ️ A lógica de construção destas trajectórias está alinhada com a página de Previsões."
        if st.session_state.lang == "PT"
        else "ℹ️ The trajectory-building logic here is aligned with the Forecasts page."
    )
    sc_col1, sc_col2 = st.columns(2)
    with sc_col1:
        sc_horizon = st.slider(
            "Scenario horizon (years)" if st.session_state.lang == "EN" else "Horizonte do cenário (anos)",
            1,
            10,
            5,
            key="scenario_horizon",
        )
    indicator_labels = {
        "mobile_tx_value": "Mobile Transactions (Value)" if st.session_state.lang == "EN" else "Transacções Mobile Banking (Valor)",
        "digital_tx_volume": "Digital Transactions (Volume)" if st.session_state.lang == "EN" else "Transacções Digitais (Volume)",
        "wallet_tx_value": "Mobile Wallet Transactions (Value)" if st.session_state.lang == "EN" else "Transacções de Carteira Móvel (Valor)",
    }
    with sc_col2:
        indicator_choice = st.selectbox(
            "Headline indicator" if st.session_state.lang == "EN" else "Indicador principal",
            list(indicator_labels.values()),
            key="scenario_indicator",
        )
    indicator_id = next(k for k, v in indicator_labels.items() if v == indicator_choice)
    if indicator_id == "mobile_tx_value":
        indicator_name = "Transacções Mobile Banking (Valor)"
        accounts_geo = apply_geo_only(acc_df)
        monthly_input = build_indicator_monthly_series(
            indicator_id,
            accounts_df=accounts_geo,
            mobile_df=mob_df,
            internet_df=net_df,
        )
    elif indicator_id == "digital_tx_volume":
        indicator_name = "Transacções Mobile Banking (Volume)"
        accounts_geo = apply_geo_only(acc_df)
        monthly_input = build_indicator_monthly_series(
            indicator_id,
            accounts_df=accounts_geo,
            mobile_df=mob_df,
            internet_df=net_df,
        )
    else:
        indicator_name = "Transacções de Carteira Móvel (Valor)"
        ime_scope = apply_geo_only(ime_txn_district_df.copy())
        monthly_input = build_monthly_series(ime_scope, "Value")
    yearly_base, model_meta = build_baseline_forecast_yearly(
        monthly_input,
        indicator_name=indicator_name,
        horizon_years=sc_horizon,
        hist_label=T("historic"),
        pred_label=T("forecast"),
    )
    if yearly_base.empty:
        st.info("Insufficient data to compute scenario paths." if st.session_state.lang == "EN" else "Dados insuficientes para calcular cenários.")
    else:
        hist_base = yearly_base[yearly_base["Tipo"] == T("historic")].sort_values("Ano")
        pred_base = yearly_base[yearly_base["Tipo"] == T("forecast")].sort_values("Ano")
        start_value = float(hist_base.iloc[-1]["Valor"]) if not hist_base.empty else 0.0

        sc_names = {
            "conservative": "Conservative" if st.session_state.lang == "EN" else "Conservador",
            "base": "Base",
            "accelerated": "Accelerated" if st.session_state.lang == "EN" else "Acelerado",
        }
        scenario_frames = []
        for key, mult in SCENARIO_MULTIPLIERS.items():
            sc_df = scenario_from_baseline(
                yearly_base,
                hist_label=T("historic"),
                pred_label=T("forecast"),
                multiplier=mult,
                scenario_name=sc_names[key],
            )
            scenario_frames.append(sc_df)
        all_sc = pd.concat(scenario_frames, ignore_index=True)
        fig_sc = px.line(
            all_sc,
            x="Ano",
            y="Valor",
            color="Cenario",
            markers=True,
            title="Scenario paths from baseline forecast" if st.session_state.lang == "EN" else "Trajectórias de cenário a partir da previsão base",
        )
        if not hist_base.empty:
            fig_sc.add_trace(
                go.Scatter(
                    x=hist_base["Ano"],
                    y=hist_base["Valor"],
                    mode="lines+markers",
                    name=T("historic"),
                    line=dict(color="#636EFA", width=3),
                )
            )
        fig_sc.update_layout(xaxis=dict(dtick=1), yaxis=dict(rangemode="tozero"))
        plot_chart(fig_sc, use_container_width=True)

        focus_choice = st.selectbox(
            "Scenario focus" if st.session_state.lang == "EN" else "Cenário em foco",
            list(sc_names.values()),
            key="scenario_focus",
            help=(
                "Selecciona qual trajectória será resumida nos cartões."
                if st.session_state.lang == "PT"
                else "Selects which trajectory is summarized in the cards."
            ),
        )
        focus_df = all_sc[all_sc["Cenario"] == focus_choice].copy()
        end_v, avg_pct = summarize_scenario(focus_df, start_value)
        s1, s2, s3 = st.columns(3)
        s1.metric(
            "End value" if st.session_state.lang == "EN" else "Valor no fim do horizonte",
            format_compact(end_v),
        )
        s2.metric(
            "Average annual change" if st.session_state.lang == "EN" else "Variação média anual",
            f"{avg_pct:+.1f}%",
        )
        holdout_smape = model_meta.get("holdout_smape")
        holdout_mae = model_meta.get("holdout_mae")
        if holdout_smape is None:
            robustness = "Sem validação walk-forward" if st.session_state.lang == "PT" else "No walk-forward validation"
        elif holdout_smape <= 10:
            robustness = "Robustez estatística: alta" if st.session_state.lang == "PT" else "Statistical robustness: high"
        elif holdout_smape <= 20:
            robustness = "Robustez estatística: moderada" if st.session_state.lang == "PT" else "Statistical robustness: moderate"
        else:
            robustness = "Robustez estatística: baixa" if st.session_state.lang == "PT" else "Statistical robustness: low"
        s3.metric(
            "Sinal de robustez" if st.session_state.lang == "PT" else "Robustness signal",
            robustness,
        )
        with st.expander("Detalhe estatístico" if st.session_state.lang == "PT" else "Statistical detail"):
            st.write(
                f"Modelo seleccionado: {model_meta.get('model_label', 'N/A')} · Walk-forward sMAPE: "
                f"{'N/A' if holdout_smape is None else f'{holdout_smape:.1f}%'} · "
                f"Walk-forward MAE: {'N/A' if holdout_mae is None else format_compact(holdout_mae)}"
            )

    st.markdown("---")
    st.subheader(
        "Leitura integrada dos sinais" if st.session_state.lang == "PT" else "Integrated reading of signals",
        help=(
            "Síntese do recorte actual combinando inclusão, intensidade digital e infraestrutura."
            if st.session_state.lang == "PT"
            else "Current-scope synthesis combining inclusion, digital intensity, and infrastructure."
        ),
    )

    denominator_pop = denominator_population(census_df[census_df["Province"].isin(selected_prov)], selected_year)
    accounts_pc = (f_acc_snap["Total_Accounts"].sum() / denominator_pop) if denominator_pop > 0 else 0.0
    infra_pc = ((f_atm_snap["ATMs_Number"].sum() + f_pos_snap["POSs_Number"].sum()) / denominator_pop * 100_000) if denominator_pop > 0 else 0.0
    subs_metric = "Quantidade de subscritores"
    mob_sub = mob_df[(mob_df["Year"] == selected_year) & (mob_df["Metric"] == subs_metric)]["Value"].sum()
    net_sub = net_df[(net_df["Year"] == selected_year) & (net_df["Metric"] == subs_metric)]["Value"].sum()
    digital_share = (mob_sub / (mob_sub + net_sub) * 100) if (mob_sub + net_sub) > 0 else 0.0

    top_txt = ""
    if "opp_df" in locals() and not opp_df.empty:
        top_txt = ", ".join(opp_df.head(3)["Province"].astype(str).tolist())
    if st.session_state.lang == "PT":
        paragraph = (
            f"No recorte actual, a inclusão observada é de {accounts_pc:.2f} contas por pessoa elegível, "
            f"com intensidade digital de {digital_share:.1f}% e infraestrutura de {infra_pc:.1f} pontos por 100 mil habitantes. "
            + (f"As maiores oportunidades concentram-se em: {top_txt}." if top_txt else "")
        )
    else:
        paragraph = (
            f"For the current scope, observed inclusion is {accounts_pc:.2f} accounts per eligible person, "
            f"with digital intensity of {digital_share:.1f}% and infrastructure density of {infra_pc:.1f} points per 100k population. "
            + (f"Top opportunities are concentrated in: {top_txt}." if top_txt else "")
        )
    st.write(paragraph)
    a1, a2, a3 = st.columns(3)
    a1.metric("Contas per capita" if st.session_state.lang == "PT" else "Accounts per capita", f"{accounts_pc:.2f}")
    a2.metric("Intensidade digital (%)" if st.session_state.lang == "PT" else "Digital intensity (%)", f"{digital_share:.1f}%")
    a3.metric("ATM+POS por 100 mil" if st.session_state.lang == "PT" else "ATM+POS per 100k", f"{infra_pc:.1f}")

    st.markdown("---")
    st.caption(
        "Perguntas determinísticas e respectivos visuais dinâmicos foram movidos para a página `📊 Visão Geral + Q&A`."
        if st.session_state.lang == "PT"
        else "Deterministic questions with dynamic visuals were moved to the `📊 Overview + Q&A` page."
    )
    render_page_caveats(
        [
            "A métrica de inclusão no comparador distrital usa denominador distrital (Censo 2017 ajustado ao cenário de elegibilidade).",
        ]
        if st.session_state.lang == "PT"
        else [
            "Inclusion metric in the district comparator uses a district denominator (Census 2017 adjusted to the selected eligibility scenario).",
        ]
    )

# ==========================================
# FOOTER
# ==========================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: grey; padding: 1rem 0;'>"
    f"{T('footer')} · "
    "<a href='mailto:valtercheque@gmail.com'>valtercheque@gmail.com</a>"
    "</div>",
    unsafe_allow_html=True
)
