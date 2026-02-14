"""
Mozambique Electronic Banking Dashboard
========================================
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

import json
from pathlib import Path

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
    STOCK_INDICATORS,
    aggregate_forecast_yearly,
    build_monthly_series,
    select_best_forecast_model,
)
from dashboard.translations import translate

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Dashboard Bancário de Moçambique", layout="wide")

# ── Language toggle (PT default, EN available) ──────────────────────────────
if "lang" not in st.session_state:
    st.session_state.lang = "PT"

PROVINCE_COORDS = {
    "Niassa": (-13.4, 36.1),
    "Cabo Delgado": (-12.5, 39.1),
    "Nampula": (-15.1, 39.3),
    "Zambézia": (-17.8, 36.9),
    "Tete": (-15.3, 33.2),
    "Manica": (-19.2, 33.4),
    "Sofala": (-19.1, 34.8),
    "Inhambane": (-22.3, 35.4),
    "Gaza": (-23.7, 33.3),
    "Província de Maputo": (-25.2, 32.8),
}


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
            "PT": "História: fotografia do sistema financeiro no ano selecionado e variação face ao ano anterior.",
            "EN": "Story: snapshot of the financial system in the selected year and change vs previous year.",
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
            "PT": "História: comportamento digital e de transações, em volume e valor.",
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
            "PT": "História: projeções de continuidade de tendência e simulação de cenários alternativos.",
            "EN": "Story: trend-continuation forecasts and alternative scenario simulation.",
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


@st.cache_data
def load_moz_adm1_geojson():
    candidates = [
        Path("geoBoundaries-MOZ-ADM1_simplified.geojson"),
        Path("geoBoundaries-MOZ-ADM1.geojson"),
        Path("mozambique_adm1.geojson"),
        Path("moz_adm1.geojson"),
    ]
    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f), str(path)
    return None, None


def normalize_geo_name(name: str) -> str:
    raw = str(name).strip()
    aliases = {
        "Maputo": "Província de Maputo",
        "Maputo Province": "Província de Maputo",
        "Maputo Província": "Província de Maputo",
        "Maputo City": "Província de Maputo",
        "Cidade de Maputo": "Província de Maputo",
        "Zambezia": "Zambézia",
    }
    return aliases.get(raw, raw)


def detect_geojson_name_field(geojson_obj: dict) -> str | None:
    features = geojson_obj.get("features", [])
    if not features:
        return None
    props = features[0].get("properties", {})
    for candidate in ["shapeName", "name", "NAME_1", "ADM1_PT", "province", "Province"]:
        if candidate in props:
            return candidate
    return None


# ── Data loading (cached so Streamlit doesn't re-read CSVs on every rerun) ──
@st.cache_data
def load_data():
    """Load all CSV datasets and census data (normalized)."""
    return load_dataframes()


# Unpack into friendly short names used throughout the dashboard
dataframes, census_df = load_data()
regions_map = REGIONS
acc_df, card_df, atm_df, vol_df, pos_df, val_df, mob_df, net_df, pos_txn_df = (
    dataframes["accounts"], dataframes["cards"], dataframes["atm"],
    dataframes["transactions_vol"], dataframes["pos"],
    dataframes["transactions_val"], dataframes["mobile_banking"],
    dataframes["internet_banking"], dataframes["pos_transactions"]
)

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

# Stock-metric snapshots: last month only (for KPIs, totals, per-capita)
f_acc_snap = last_month_snapshot(f_acc)
f_card_snap = last_month_snapshot(f_card)
f_atm_snap = last_month_snapshot(f_atm)
f_pos_snap = last_month_snapshot(f_pos)


# ── Dashboard tabs ──────────────────────────────────────────────────────────
# 8 pages: demographics, overview, combined product/usage pages, and analytics
tabs = st.tabs([
    T("tab_demo"),
    T("tab_overview"),
    f"{T('tab_accounts')} + {T('tab_cards')}",
    T("tab_infra"),
    f"{T('tab_digital')} + {T('tab_txn')}",
    T("tab_trends"),
    T("tab_heatmap"),
    T("tab_forecast"),
])

# ==========================================
# PAGE 1: CONTEXTO DEMOGRÁFICO (CENSUS)
# ==========================================
with tabs[0]:
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

    # --- Population overview bar chart ---
    st.subheader(T("population_by_province"))

    fig_pop = px.bar(
        census_filtered.sort_values('Population_Total', ascending=True),
        y='Province', x='Population_Total', orientation='h',
        color='Population_Total', color_continuous_scale='YlOrRd',
        text=[f"{v:,.0f}" for v in census_filtered.sort_values('Population_Total', ascending=True)['Population_Total']],
    )
    fig_pop.update_layout(
        xaxis_title=T("value"), yaxis_title=T("province"),
        coloraxis_showscale=False, height=450
    )
    st.plotly_chart(fig_pop, use_container_width=True)

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
        st.plotly_chart(fig_gen, use_container_width=True)

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
        st.plotly_chart(fig_ur, use_container_width=True)

    # --- Financial Inclusion KPI cards ---
    st.markdown("---")
    st.subheader(T("financial_inclusion"))

    # Compute per-capita from the latest year banking data (last month snapshot only)
    latest_year = max(all_years)
    latest_acc = acc_df[acc_df['Year'] == latest_year]
    latest_card = card_df[card_df['Year'] == latest_year]
    latest_atm = atm_df[atm_df['Year'] == latest_year]
    latest_pos = pos_df[pos_df['Year'] == latest_year]

    # Use last-month snapshot to avoid 12x inflation on stock metrics
    latest_acc = last_month_snapshot(latest_acc)
    latest_card = last_month_snapshot(latest_card)
    latest_atm = last_month_snapshot(latest_atm)
    latest_pos = last_month_snapshot(latest_pos)

    total_pop = census_filtered['Population_Total'].sum()
    total_acc_latest = latest_acc['Total_Accounts'].sum()
    total_card_latest = latest_card['Total_Cards'].sum()
    total_atm_latest = latest_atm['ATMs_Number'].sum()
    total_pos_latest = latest_pos['POSs_Number'].sum()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(T("accounts_per_capita"), f"{total_acc_latest / total_pop:.2f}" if total_pop > 0 else "N/A")
    kpi2.metric(T("cards_per_capita"), f"{total_card_latest / total_pop:.2f}" if total_pop > 0 else "N/A")
    kpi3.metric(T("atm_per_100k"), f"{total_atm_latest / total_pop * 100_000:.1f}" if total_pop > 0 else "N/A")
    kpi4.metric(T("pos_per_100k"), f"{total_pos_latest / total_pop * 100_000:.1f}" if total_pop > 0 else "N/A")

    st.caption(f"ℹ️ {'Dados bancários:' if st.session_state.lang == 'PT' else 'Banking data:'} {latest_year} · "
               f"{'Dados demográficos: Censo 2017 (INE)' if st.session_state.lang == 'PT' else 'Demographics: Census 2017 (INE)'}")

    # --- Underbanked Gap: Population vs Accounts per province ---
    st.markdown("---")
    st.subheader(T("underbanked_gap"))

    gap_rows = []
    for _, row in census_filtered.iterrows():
        prov_name = row['Province']
        # Province names now align between census and banking data
        prov_acc = latest_acc[latest_acc['Province'] == prov_name]
        total_a = prov_acc['Total_Accounts'].sum() if not prov_acc.empty else 0
        gap_rows.append({
            T("province"): prov_name,
            'Population (Census 2017)': row['Population_Total'],
            f'{T("total_accounts")} ({latest_year})': total_a,
            T("accounts_per_capita"): round(total_a / row['Population_Total'], 3) if row['Population_Total'] > 0 else 0
        })

    gap_df = pd.DataFrame(gap_rows).sort_values(T("accounts_per_capita"), ascending=False)

    map_rows = []
    for _, row in gap_df.iterrows():
        province_name = row[T("province")]
        coords = PROVINCE_COORDS.get(province_name)
        if coords is None:
            continue
        map_rows.append({
            "Province": province_name,
            "lat": coords[0],
            "lon": coords[1],
            "Accounts_Per_Capita": float(row[T("accounts_per_capita")]),
            "Population": float(row["Population (Census 2017)"]),
            "Accounts": float(row[f'{T("total_accounts")} ({latest_year})']),
        })
    map_df = pd.DataFrame(map_rows)
    moz_geojson, moz_geojson_path = load_moz_adm1_geojson()
    geo_name_field = detect_geojson_name_field(moz_geojson) if moz_geojson else None
    fig_map = None
    map_note = None
    if not map_df.empty and moz_geojson and geo_name_field:
        lookup = map_df.set_index("Province")[["Accounts_Per_Capita", "Population", "Accounts"]].to_dict("index")
        feature_names = []
        feature_vals = []
        feature_pop = []
        feature_acc = []
        for feat in moz_geojson.get("features", []):
            feat_name = str(feat.get("properties", {}).get(geo_name_field, "")).strip()
            norm_name = normalize_geo_name(feat_name)
            if norm_name in lookup:
                feature_names.append(feat_name)
                feature_vals.append(lookup[norm_name]["Accounts_Per_Capita"])
                feature_pop.append(lookup[norm_name]["Population"])
                feature_acc.append(lookup[norm_name]["Accounts"])
        choro_df = pd.DataFrame(
            {
                "feature_name": feature_names,
                "Accounts_Per_Capita": feature_vals,
                "Population": feature_pop,
                "Accounts": feature_acc,
            }
        )
        if not choro_df.empty:
            fig_map = px.choropleth_mapbox(
                choro_df,
                geojson=moz_geojson,
                locations="feature_name",
                featureidkey=f"properties.{geo_name_field}",
                color="Accounts_Per_Capita",
                color_continuous_scale="YlOrRd",
                mapbox_style="carto-positron",
                zoom=4.6,
                center={"lat": -18.7, "lon": 35.5},
                opacity=0.7,
                hover_data={
                    "feature_name": True,
                    "Population": ":,.0f",
                    "Accounts": ":,.0f",
                    "Accounts_Per_Capita": ":.2f",
                },
            )
            fig_map.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10))
            map_note = (
                f"Mapa provincial (GeoJSON): `{moz_geojson_path}`"
                if st.session_state.lang == "PT"
                else f"Province map (GeoJSON): `{moz_geojson_path}`"
            )
    elif not map_df.empty:
        pop_label = "População" if st.session_state.lang == "PT" else "Population"
        fig_map = go.Figure(
            go.Scattergeo(
                lat=map_df["lat"],
                lon=map_df["lon"],
                mode="markers",
                marker=dict(
                    size=(map_df["Accounts_Per_Capita"] * 30).clip(lower=8),
                    color=map_df["Accounts_Per_Capita"],
                    colorscale="YlOrRd",
                    colorbar=dict(title=T("accounts_per_capita"), thickness=12),
                    line=dict(width=0.5, color="#333333"),
                    sizemode="diameter",
                ),
                customdata=map_df[["Population", "Accounts", "Accounts_Per_Capita"]],
                hovertemplate=(
                    f"{T('province')}: %{{customdata[3]}}<br>"
                    f"{pop_label}: %{{customdata[0]:,.0f}}<br>"
                    f"{T('total_accounts')}: %{{customdata[1]:,.0f}}<br>"
                    f"{T('accounts_per_capita')}: %{{customdata[2]:.2f}}<extra></extra>"
                ),
            )
        )
        fig_map.data[0].customdata = map_df[["Population", "Accounts", "Accounts_Per_Capita", "Province"]]
        fig_map.update_geos(
            scope="africa",
            projection_type="mercator",
            showcountries=True,
            countrycolor="lightgray",
            showland=True,
            landcolor="rgb(247, 247, 247)",
            lonaxis_range=[30, 41],
            lataxis_range=[-27, -10],
        )
        fig_map.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10))
        map_note = (
            "Fallback map: marker view (no local province GeoJSON found)."
            if st.session_state.lang == "EN"
            else "Mapa alternativo: vista por marcadores (sem GeoJSON provincial local)."
        )

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
    st.plotly_chart(fig_pc, use_container_width=True)

    map_expander_title = (
        "🗺️ Ver no mapa (opcional)"
        if st.session_state.lang == "PT"
        else "🗺️ View on map (optional)"
    )
    with st.expander(map_expander_title, expanded=False):
        if fig_map is not None:
            st.plotly_chart(fig_map, use_container_width=True)
            if map_note:
                st.caption(map_note)

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
        st.plotly_chart(fig_gpi, use_container_width=True)

    # --- Connectivity context: Phone/Internet vs Digital Banking ---
    st.markdown("---")
    st.subheader(T("connectivity_context"))
    st.markdown(T("connectivity_desc"))

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
        st.plotly_chart(fig_phone, use_container_width=True)

    with conn_col2:
        fig_internet = px.bar(
            census_filtered.sort_values('Internet_Usage_Pct', ascending=True),
            y='Province', x='Internet_Usage_Pct', orientation='h',
            color='Internet_Usage_Pct', color_continuous_scale='Purples',
            text=[f"{v:.1f}%" for v in census_filtered.sort_values('Internet_Usage_Pct', ascending=True)['Internet_Usage_Pct']],
            title=T("internet_vs_internet_banking")
        )
        fig_internet.update_layout(xaxis_title="%", coloraxis_showscale=False, height=400)
        st.plotly_chart(fig_internet, use_container_width=True)

    st.caption(T("census_note_short"))


# ==========================================
# PAGE 2: VISÃO GERAL
# ==========================================
with tabs[1]:
    st.title(T("title_overview"))
    st.caption(T("caption_overview"))
    st.caption(tab_story("overview"))

    # YoY comparison metrics (last-month snapshots for stock metrics)
    prev_year = selected_year - 1
    if prev_year not in all_years:
        st.info(
            f"{prev_year} não está disponível para comparação direta."
            if st.session_state.lang == "PT"
            else f"{prev_year} is not available for direct comparison."
        )
    prev_acc = dataframes["accounts"][(dataframes["accounts"]['Year'] == prev_year) & (dataframes["accounts"]['Province'].isin(selected_prov))]
    prev_card = dataframes["cards"][(dataframes["cards"]['Year'] == prev_year) & (dataframes["cards"]['Province'].isin(selected_prov))]
    prev_atm = dataframes["atm"][(dataframes["atm"]['Year'] == prev_year) & (dataframes["atm"]['Province'].isin(selected_prov))]
    prev_acc = last_month_snapshot(prev_acc)
    prev_card = last_month_snapshot(prev_card)
    prev_atm = last_month_snapshot(prev_atm)

    curr_acc_total = f_acc_snap['Total_Accounts'].sum()
    prev_acc_total = prev_acc['Total_Accounts'].sum()
    curr_card_total = f_card_snap['Total_Cards'].sum()
    prev_card_total = prev_card['Total_Cards'].sum()
    curr_atm_total = f_atm_snap['ATMs_Number'].sum()
    prev_atm_total = prev_atm['ATMs_Number'].sum()

    def calc_delta(curr, prev):
        if prev > 0:
            pct = ((curr - prev) / prev) * 100
            return f"{pct:+.1f}%"
        return None

    c1, c2, c3 = st.columns(3)
    c1.metric(T("total_accounts"), format_compact(curr_acc_total), delta=calc_delta(curr_acc_total, prev_acc_total))
    c2.metric(T("total_cards"), format_compact(curr_card_total), delta=calc_delta(curr_card_total, prev_card_total))
    c3.metric("Total ATMs", format_compact(curr_atm_total), delta=calc_delta(curr_atm_total, prev_atm_total))

    # Per-capita KPIs from census
    st.markdown(f"###### {T('census_kpis')}")
    total_pop_sel = census_df[census_df['Province'].isin(selected_prov)]['Population_Total'].sum()
    if total_pop_sel > 0:
        ov_k1, ov_k2, ov_k3 = st.columns(3)
        ov_k1.metric(T("accounts_per_capita"), f"{curr_acc_total / total_pop_sel:.2f}")
        ov_k2.metric(T("cards_per_capita"), f"{curr_card_total / total_pop_sel:.2f}")
        ov_k3.metric(T("atm_per_100k"), f"{curr_atm_total / total_pop_sel * 100_000:.1f}")
        st.caption(T("census_note_short"))

    st.subheader(f"{T('gender_distribution')} ({selected_year})")
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        gen_acc = f_acc_snap.groupby('Gender', observed=False)['Total_Accounts'].sum().reset_index()
        gen_acc.columns = [T("gender_label"), T("total_accounts")]
        st.plotly_chart(px.pie(gen_acc, values=T("total_accounts"), names=T("gender_label"),
                               title=f"{T('accounts_by_gender')} ({selected_year})", hole=0.4), use_container_width=True)
    with g_col2:
        gen_card = f_card_snap.groupby('Gender', observed=False)['Total_Cards'].sum().reset_index()
        gen_card.columns = [T("gender_label"), T("total_cards")]
        st.plotly_chart(px.pie(gen_card, values=T("total_cards"), names=T("gender_label"),
                               title=f"{T('cards_by_gender')} ({selected_year})", hole=0.4), use_container_width=True)

    st.subheader(f"{T('accounts_distribution')} {title_suffix} ({selected_year})")
    prov_summary = f_acc_snap.groupby(geo_axis)['Total_Accounts'].sum().sort_values(ascending=False).reset_index()
    prov_summary.columns = [geo_axis_label, T("total_accounts")]
    st.plotly_chart(px.bar(prov_summary, x=geo_axis_label, y=T("total_accounts"), color=geo_axis_label), use_container_width=True)

# ==========================================
# PAGE 3: PRODUCTS (toggle Accounts/Cards)
# ==========================================
with tabs[2]:
    st.title(f"{T('title_accounts')} + {T('title_cards')}")
    st.caption(tab_story("products"))
    view_prompt = "Ver" if st.session_state.lang == "PT" else "View"
    opt_accounts = T("tab_accounts")
    opt_cards = T("tab_cards")
    products_view = single_choice_toggle(
        view_prompt,
        [opt_accounts, opt_cards],
        key="products_view_toggle",
    )

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
        month_acc.columns = [T("month"), T("total_accounts")]
        fig_month_acc = px.line(
            month_acc,
            x=T("month"),
            y=T("total_accounts"),
            markers=True,
            title=f"{T('monthly_trend_accounts')} ({selected_year})",
        )
        fig_month_acc.update_layout(yaxis=dict(rangemode='tozero'))
        st.plotly_chart(fig_month_acc, use_container_width=True)

        st.subheader(f"{T('accounts_by_age')} ({selected_year})")
        age_buckets = ["0-16", "17-21", "22-60", "+60"]
        age_acc_detail = f_acc_snap[f_acc_snap["Age"].isin(age_buckets)]
        if age_acc_detail.empty:
            msg_pt = (
                "Dados indisponíveis para este gráfico no ano selecionado. "
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
            st.plotly_chart(
                px.bar(age_acc, y=T("age_group"), x=T("total_accounts"), orientation='h', color=T("age_group")),
                use_container_width=True,
            )

        st.subheader(f"{T('currency_distribution')} {title_suffix} ({selected_year})")
        curr_data = f_acc_snap.groupby([geo_axis, 'Account_Currency'])['Total_Accounts'].sum().reset_index()
        curr_data.columns = [geo_axis_label, T("currency_label"), T("total_accounts")]
        st.plotly_chart(px.bar(curr_data, x=geo_axis_label, y=T("total_accounts"), color=T("currency_label"), barmode='group'), use_container_width=True)

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
        month_card.columns = [T("month"), T("total_cards")]
        fig_month_card = px.line(
            month_card,
            x=T("month"),
            y=T("total_cards"),
            markers=True,
            title=f"{T('monthly_trend_cards')} ({selected_year})",
        )
        fig_month_card.update_layout(yaxis=dict(rangemode='tozero'))
        st.plotly_chart(fig_month_card, use_container_width=True)

        st.subheader(f"{T('product_adoption_age')} ({selected_year})")
        age_buckets = ["0-16", "17-21", "22-60", "+60"]
        age_card_detail = f_card_snap[f_card_snap["Age"].isin(age_buckets)]
        if age_card_detail.empty:
            msg_pt = (
                "Dados indisponíveis para este gráfico no ano selecionado. "
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
            st.plotly_chart(
                px.bar(age_card, y=T("age_group"), x=T("total_cards"), color=T("card_type_label"), orientation='h'),
                use_container_width=True,
            )

        st.subheader(f"{T('card_type')} {title_suffix} ({selected_year})")
        card_type_geo = f_card_snap.groupby([geo_axis, 'Card_Type'])['Total_Cards'].sum().reset_index()
        card_type_geo.columns = [geo_axis_label, T("card_type_label"), T("total_cards")]
        st.plotly_chart(px.bar(card_type_geo, x=geo_axis_label, y=T("total_cards"), color=T("card_type_label"), barmode='group'), use_container_width=True)

# ==========================================
# PAGE 5: INFRAESTRUTURA
# ==========================================
with tabs[3]:
    st.title(T("title_infra"))
    st.caption(T("caption_infra"))
    st.caption(tab_story("infra"))
    curr_pos_total = f_pos_snap["POSs_Number"].sum()
    infra_ratio = (curr_pos_total / curr_atm_total) if curr_atm_total > 0 else 0
    i1, i2, i3 = st.columns(3)
    i1.metric(T("num_atms"), format_compact(curr_atm_total))
    i2.metric(T("num_pos"), format_compact(curr_pos_total))
    i3.metric("POS/ATM", f"{infra_ratio:.1f}")

    # Per-capita infrastructure from census (last-month snapshot)
    if total_pop_sel > 0:
        inf_k1, inf_k2 = st.columns(2)
        inf_k1.metric(T("atm_per_100k"), f"{curr_atm_total / total_pop_sel * 100_000:.1f}")
        inf_k2.metric(T("pos_per_100k"), f"{curr_pos_total / total_pop_sel * 100_000:.1f}")
        st.caption(T("census_note_short"))

    col_i1, col_i2 = st.columns(2)
    with col_i1:
        atm_sum = f_atm_snap.groupby(geo_axis)['ATMs_Number'].sum().reset_index()
        atm_sum.columns = [geo_axis_label, T("num_atms")]
        st.plotly_chart(
            px.bar(atm_sum, x=geo_axis_label, y=T("num_atms"), title=f"{T('atm_distribution')} ({selected_year})"),
            use_container_width=True,
        )
    with col_i2:
        pos_sum = f_pos_snap.groupby(geo_axis)['POSs_Number'].sum().reset_index()
        pos_sum.columns = [geo_axis_label, T("num_pos")]
        st.plotly_chart(
            px.bar(pos_sum, x=geo_axis_label, y=T("num_pos"), title=f"{T('pos_distribution')} ({selected_year})"),
            use_container_width=True,
        )

# ==========================================
# PAGE 5: USAGE (toggle Digital/Transactions)
# ==========================================
with tabs[4]:
    st.title(f"{T('title_digital')} + {T('title_txn')}")
    st.caption(tab_story("usage"))
    usage_view_prompt = "Ver" if st.session_state.lang == "PT" else "View"
    usage_opt_digital = T("tab_digital")
    usage_opt_txn = T("tab_txn")
    usage_view = single_choice_toggle(
        usage_view_prompt,
        [usage_opt_digital, usage_opt_txn],
        key="usage_view_toggle",
    )

    if usage_view == usage_opt_digital:
        st.caption(T("caption_digital"))
        mobile_context_pt = (
            "ℹ️ Contexto metodológico (Moçambique): o indicador de Mobile Banking pode incluir utilizadores de "
            "M-Pesa, mKesh, e-Mola e Conta Móvel. Como as plataformas são contabilizadas por conta/serviço, "
            "uma mesma pessoa pode ter registo em mais de uma plataforma."
        )
        mobile_context_en = (
            "ℹ️ Methodology context (Mozambique): the Mobile Banking indicator may include users from "
            "M-Pesa, mKesh, e-Mola, and Conta Móvel. Because platforms are counted by account/service, "
            "one person may appear in more than one platform."
        )
        st.info(mobile_context_pt if st.session_state.lang == "PT" else mobile_context_en)
        st.caption(
            "Fontes: Banco de Moçambique (interligação de carteiras móveis), Vodacom M-Pesa, mKesh/Tmcel e BCI Conta Móvel."
            if st.session_state.lang == "PT"
            else "Sources: Bank of Mozambique (mobile wallet interoperability), Vodacom M-Pesa, mKesh/Tmcel, and BCI Conta Móvel."
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
        m_mob.rename(columns={'Month': T("month"), 'Value': T("value")}, inplace=True)
        m_net.rename(columns={'Month': T("month"), 'Value': T("value")}, inplace=True)
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
        st.plotly_chart(fig_comp_dig, use_container_width=True)

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
        dig_monthly.rename(columns={'Month': T("month"), 'Value': T("value")}, inplace=True)
        fig_dig_monthly = px.line(dig_monthly, x=T("month"), y=T("value"), markers=True,
                                  title=f"{T('monthly_trend')} ({selected_year})")
        fig_dig_monthly.update_layout(yaxis=dict(rangemode='tozero'))
        st.plotly_chart(fig_dig_monthly, use_container_width=True)

        dig_yearly = dig_filtered.groupby('Year')['Value'].sum().reset_index().sort_values('Year')
        dig_yearly.rename(columns={'Year': T("year"), 'Value': T("value")}, inplace=True)

        if not dig_yearly.empty:
            dig_yearly[T("growth_pct")] = dig_yearly[T("value")].pct_change() * 100

            v2_col1, v2_col2 = st.columns(2)
            with v2_col1:
                fig_dig_bar = px.bar(dig_yearly, x=T("year"), y=T("value"), text_auto='.3s',
                                     title=T("annual_evolution"))
                fig_dig_bar.update_layout(xaxis=dict(dtick=1))
                st.plotly_chart(fig_dig_bar, use_container_width=True)
            with v2_col2:
                growth_dig = dig_yearly.dropna(subset=[T("growth_pct")]).copy()
                if not growth_dig.empty:
                    fig_dig_gr = px.bar(growth_dig, x=T("year"), y=T("growth_pct"), text_auto='.1f',
                                        title=T("yoy_growth"),
                                        color=T("growth_pct"), color_continuous_scale='RdYlGn')
                    fig_dig_gr.update_layout(xaxis=dict(dtick=1))
                    st.plotly_chart(fig_dig_gr, use_container_width=True)

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
        mob_choice_label = "Mobile Banking — Transações"
        net_choice_label = "Internet Banking — Transações"

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

        vol_monthly.rename(columns={'Month': T("month")}, inplace=True)
        val_monthly.rename(columns={'Month': T("month")}, inplace=True)

        col_v1, col_v2 = st.columns(2)
        with col_v1:
            fig_vol_m = px.bar(
                vol_monthly,
                x=T("month"),
                y=T("volume"),
                title=f"{T('vol_monthly_title')} — {txn_title} ({selected_year})",
            )
            fig_vol_m.update_layout(yaxis=dict(rangemode='tozero'))
            st.plotly_chart(fig_vol_m, use_container_width=True)
        with col_v2:
            fig_val_m = px.line(
                val_monthly,
                x=T("month"),
                y=T("value"),
                markers=True,
                title=f"{T('val_monthly_title')} — {txn_title} ({selected_year})",
            )
            fig_val_m.update_layout(yaxis=dict(rangemode='tozero'))
            st.plotly_chart(fig_val_m, use_container_width=True)

        vol_annual.rename(columns={'Year': T("year")}, inplace=True)
        val_annual.rename(columns={'Year': T("year")}, inplace=True)
        annual_merged = pd.merge(vol_annual, val_annual, on=T("year"), how='outer').sort_values(T("year"))

        if not annual_merged.empty and annual_merged[T("volume")].sum() > 0:
            fig_annual = go.Figure()
            fig_annual.add_trace(go.Bar(
                x=annual_merged[T("year")], y=annual_merged[T("volume")],
                name=T("volume"), yaxis='y', marker_color='#636EFA',
                text=[f"{v:,.0f}" for v in annual_merged[T("volume")]], textposition='outside'))
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
            st.plotly_chart(fig_annual, use_container_width=True)

# ==========================================
# PAGE 6: TENDÊNCIAS HISTÓRICAS
# ==========================================
with tabs[5]:
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
    st.plotly_chart(fig_trend_bar, use_container_width=True)

    if trend_indicator not in ["Mobile Banking", "Internet Banking"] and 'Province' in geo_trend.columns:
        prov_year_trend = geo_trend.groupby(['Year', 'Province'])[trend_col].sum().reset_index()
        prov_year_trend.columns = ['Year', T("province"), 'Total']
        fig_trend_prov = px.line(prov_year_trend, x='Year', y='Total', color=T("province"),
                                 markers=True,
                                 title=f"{trend_label} {T('by_province_over_years')}",
                                 labels={'Year': T("year"), 'Total': trend_label})
        fig_trend_prov.update_layout(xaxis=dict(dtick=1))
        st.plotly_chart(fig_trend_prov, use_container_width=True)

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
            st.plotly_chart(fig_trend_growth, use_container_width=True)

# ==========================================
# PAGE 7: MAPA DE CALOR
# ==========================================
with tabs[6]:
    st.title(T("title_heatmap"))
    st.caption(T("caption_heatmap"))
    st.caption(tab_story("heatmap"))

    heatmap_metric = st.selectbox(T("indicator"), [
        "Contas Bancárias", "Cartões Bancários", "ATMs", "POS"
    ], key="heatmap_metric",
        help=T("help_heatmap")
    )

    if heatmap_metric == "Contas Bancárias":
        hm_data = last_month_snapshot_all_years(apply_geo_only(acc_df)).groupby(['Year', 'Province'])['Total_Accounts'].sum().reset_index()
        val_col = 'Total_Accounts'
    elif heatmap_metric == "Cartões Bancários":
        hm_data = last_month_snapshot_all_years(apply_geo_only(card_df)).groupby(['Year', 'Province'])['Total_Cards'].sum().reset_index()
        val_col = 'Total_Cards'
    elif heatmap_metric == "ATMs":
        hm_data = last_month_snapshot_all_years(apply_geo_only(atm_df)).groupby(['Year', 'Province'])['ATMs_Number'].sum().reset_index()
        val_col = 'ATMs_Number'
    else:
        hm_data = last_month_snapshot_all_years(apply_geo_only(pos_df)).groupby(['Year', 'Province'])['POSs_Number'].sum().reset_index()
        val_col = 'POSs_Number'

    if not hm_data.empty:
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
        hm2.metric(
            "Top Província" if st.session_state.lang == "PT" else "Top Province",
            hm_top_prov,
        )
        hm3.metric(
            T("growth_pct"),
            f"{hm_avg_growth:+.1f}%" if hm_avg_growth is not None else "N/A",
        )

        pivot = hm_data.pivot_table(index='Province', columns='Year', values=val_col, aggfunc='sum', fill_value=0)

        fig_hm = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=pivot.index.tolist(),
            colorscale='YlOrRd',
            text=[[f"{v:,.0f}" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            hovertemplate=f"{T('province')}: %{{y}}<br>{T('year')}: %{{x}}<br>{T('value')}: %{{text}}<extra></extra>"
        ))
        fig_hm.update_layout(
            title=f"{heatmap_metric} {T('by_province_year')}",
            xaxis_title=T("year"), yaxis_title=T("province"), height=500
        )
        st.plotly_chart(fig_hm, use_container_width=True)

    st.subheader(T("growth_rate_heatmap"))
    if not hm_data.empty and len(pivot.columns) > 1:
        growth_pivot = pivot.pct_change(axis=1) * 100
        growth_pivot = growth_pivot.iloc[:, 1:]

        fig_growth = go.Figure(data=go.Heatmap(
            z=growth_pivot.values,
            x=[str(c) for c in growth_pivot.columns],
            y=growth_pivot.index.tolist(),
            colorscale='RdYlGn',
            zmid=0,
            text=[[f"{v:.1f}%" for v in row] for row in growth_pivot.values],
            texttemplate="%{text}",
            hovertemplate=f"{T('province')}: %{{y}}<br>{T('year')}: %{{x}}<br>{T('growth_pct')}: %{{text}}<extra></extra>"
        ))
        fig_growth.update_layout(
            title=f"{T('yoy_growth')} — {heatmap_metric} {T('by_province_year')}",
            xaxis_title=T("year"), yaxis_title=T("province"), height=500
        )
        st.plotly_chart(fig_growth, use_container_width=True)

# ==========================================
# PAGE 8: PREVISÕES (POLYNOMIAL + MONTHLY)
# ==========================================
with tabs[7]:
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
        forecast_indicator = st.selectbox(T("forecast_indicator"), [
            "Contas Bancárias", "Cartões Bancários", "ATMs", "POS",
            "Mobile Banking", "Internet Banking",
            "Transações ATM (Volume)", "Transações ATM (Valor)",
            "Transações POS (Volume)", "Transações POS (Valor)",
            "Transações Mobile Banking (Volume)", "Transações Mobile Banking (Valor)",
            "Transações Internet Banking (Volume)", "Transações Internet Banking (Valor)",
        ], key="forecast_indicator",
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
    if forecast_indicator == "Contas Bancárias":
        src_df = apply_geo_only(acc_df); metric_col = 'Total_Accounts'; has_province = True
    elif forecast_indicator == "Cartões Bancários":
        src_df = apply_geo_only(card_df); metric_col = 'Total_Cards'; has_province = True
    elif forecast_indicator == "ATMs":
        src_df = apply_geo_only(atm_df); metric_col = 'ATMs_Number'; has_province = True
    elif forecast_indicator == "POS":
        src_df = apply_geo_only(pos_df); metric_col = 'POSs_Number'; has_province = True
    elif forecast_indicator == "Mobile Banking":
        src_df = mob_df; metric_col = 'Value'
    elif forecast_indicator == "Internet Banking":
        src_df = net_df; metric_col = 'Value'
    elif forecast_indicator == "Transações ATM (Volume)":
        src_df, metric_col = get_atm_txn_forecast_data('vol')
    elif forecast_indicator == "Transações ATM (Valor)":
        src_df, metric_col = get_atm_txn_forecast_data('val')
    elif forecast_indicator == "Transações POS (Volume)":
        src_df = pos_txn_df[pos_txn_df['Metric'].str.contains('Volume', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transações POS (Valor)":
        src_df = pos_txn_df[pos_txn_df['Metric'].str.contains('Valor', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transações Mobile Banking (Volume)":
        src_df = mob_df[mob_df['Metric'].str.contains('Volume', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transações Mobile Banking (Valor)":
        src_df = mob_df[mob_df['Metric'].str.contains('Valor', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transações Internet Banking (Volume)":
        src_df = net_df[net_df['Metric'].str.contains('Volume', case=False, na=False)]; metric_col = 'Value'
    elif forecast_indicator == "Transações Internet Banking (Valor)":
        src_df = net_df[net_df['Metric'].str.contains('Valor', case=False, na=False)]; metric_col = 'Value'

    st.subheader(f"{T('national_forecast')} — {forecast_indicator}")

    monthly_series = build_monthly_series(src_df, metric_col)
    fc_type = T("stock_label") if forecast_indicator in STOCK_INDICATORS else T("flow_label")
    fc_type_short = (
        ("Stock" if st.session_state.lang == "EN" else "Stock")
        if forecast_indicator in STOCK_INDICATORS
        else ("Flow" if st.session_state.lang == "EN" else "Fluxo")
    )
    fc_latest = monthly_series["Value"].iloc[-1] if not monthly_series.empty else 0
    fc1, fc2, fc3 = st.columns(3)
    fc1.metric(T("forecast_horizon"), f"{forecast_horizon}")
    fc2.metric(T("indicator"), fc_type_short)
    fc3.metric(
        "Último valor observado" if st.session_state.lang == "PT" else "Last observed value",
        format_compact(fc_latest),
    )
    if forecast_indicator in STOCK_INDICATORS:
        stock_note = (
            "ℹ️ Decisão de negócio: para indicadores de stock, consideramos o fim de período. "
            "Racional: o stock representa posição num ponto no tempo; somar os 12 meses inflaciona o resultado. "
            "Regra aplicada: usamos o valor reportado em Dezembro como referência anual."
            if st.session_state.lang == "PT"
            else "ℹ️ Business rule: for stock indicators, we use end-of-period values. "
            "Rationale: stock is a point-in-time position, so summing all 12 months would overstate results. "
            "Applied rule: we use the December-reported value as the annual reference."
        )
        st.caption(stock_note)
    else:
        flow_note = (
            "ℹ️ Decisão de negócio: para indicadores de fluxo, usamos soma anual. "
            "Racional: fluxo mede atividade acumulada no período. "
            "Regra aplicada: agregamos os 12 meses do ano."
            if st.session_state.lang == "PT"
            else "ℹ️ Business rule: for flow indicators, we use annual aggregation. "
            "Rationale: flow measures accumulated activity over the period. "
            "Applied rule: we aggregate all 12 months of the year."
        )
        st.caption(flow_note)

    hist_label = T("historic")
    pred_label = T("forecast")

    if len(monthly_series) >= 3:
        combined, r2, res_std, model_meta = select_best_forecast_model(
            monthly_series, n_future_years=forecast_horizon, indicator_name=forecast_indicator
        )

        if combined is not None:
            yearly_fc = aggregate_forecast_yearly(combined, forecast_indicator, hist_label, pred_label)

            if not yearly_fc.empty:
                fig_fc = go.Figure()

                hist_yr = yearly_fc[yearly_fc['Tipo'] == hist_label]
                pred_yr = yearly_fc[yearly_fc['Tipo'] == pred_label]

                fig_fc.add_trace(go.Bar(
                    x=hist_yr['Ano'], y=hist_yr['Valor'],
                    name=hist_label, marker_color='#636EFA',
                    text=[f"{v:,.0f}" for v in hist_yr['Valor']],
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
                        text=[f"{v:,.0f}" for v in pred_yr['Valor']],
                        textposition='top center'
                    ))

                tipo_label = T("stock_label") if forecast_indicator in STOCK_INDICATORS else T("flow_label")
                fig_fc.update_layout(
                    title=f"{T('forecast')}: {forecast_indicator}",
                    xaxis=dict(title=T("year"), dtick=1),
                    yaxis=dict(title=T("value"), rangemode='tozero'),
                    legend=dict(x=0.01, y=0.99),
                    height=500
                )
                st.plotly_chart(fig_fc, use_container_width=True)

                holdout_label = (
                    "N/A" if model_meta["holdout_mape"] is None else f"{model_meta['holdout_mape']:.2f}%"
                )
                r2_label = "N/A" if r2 is None else f"{r2:.3f}"
                st.info(
                    f"**Model:** {model_meta['model_label']} · "
                    f"**Holdout MAPE:** {holdout_label} · "
                    f"**R²:** {r2_label} · "
                    f"**{T('indicator')}:** {tipo_label} · "
                    f"**Data points:** {len(monthly_series)}"
                )

                if model_meta["holdout_mape"] is not None:
                    if model_meta["holdout_mape"] <= 8:
                        st.success(T("model_good"))
                    elif model_meta["holdout_mape"] <= 15:
                        st.warning(T("model_moderate"))
                    else:
                        st.error(T("model_weak"))
                elif r2 is not None and r2 >= 0.8:
                    st.success(T("model_good"))
                elif r2 is not None and r2 >= 0.5:
                    st.warning(T("model_moderate"))
                else:
                    st.error(T("model_weak"))
    else:
        st.warning(T("insufficient_data"))

    # --- Province-level Forecast ---
    if has_province and 'Province' in src_df.columns:
        st.subheader(f"{T('province_forecast')} — {forecast_indicator}")

        provinces = [p for p in selected_prov if p in src_df['Province'].unique()]

        if provinces:
            prov_results = []
            for prov in provinces:
                prov_data = src_df[src_df['Province'] == prov]
                prov_monthly = build_monthly_series(prov_data, metric_col)
                if len(prov_monthly) >= 3:
                    prov_combined, prov_r2, _, prov_meta = select_best_forecast_model(
                        prov_monthly, n_future_years=forecast_horizon, indicator_name=forecast_indicator
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
                st.plotly_chart(fig_prov_fc, use_container_width=True)

                st.subheader(T("forecast_summary"))
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
    st.subheader(T("manual_simulator"))
    st.markdown(T("manual_sim_desc"))

    if forecast_indicator in STOCK_INDICATORS and 'Month' in src_df.columns:
        dec_data = src_df[src_df['Month'] == 'Dezembro'] if 'Month' in src_df.columns else src_df
        yearly_totals = dec_data.groupby('Year')[metric_col].sum().reset_index().sort_values('Year')
    else:
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
        st.plotly_chart(fig_sim, use_container_width=True)

        st.metric(
            f"{T('projection_for')} {base_year + horizon_manual}",
            format_compact(sim_vals[-1]),
            delta=f"{((sim_vals[-1] - base_value) / base_value * 100):.1f}% {T('total_growth')}" if base_value > 0 else None
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
