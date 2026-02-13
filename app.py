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

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Dashboard Bancário de Moçambique", layout="wide")

# ── Language toggle (PT default, EN available) ──────────────────────────────
if "lang" not in st.session_state:
    st.session_state.lang = "PT"

_TRANSLATIONS = {
    # Sidebar
    "sidebar_title": {"PT": "Filtros de Navegação", "EN": "Navigation Filters"},
    "sidebar_caption": {
        "PT": "ℹ️ Use os filtros abaixo para segmentar os dados por ano, zona geográfica, província e distrito.",
        "EN": "ℹ️ Use the filters below to segment data by year, geographic zone, province and district."
    },
    "year": {"PT": "Ano", "EN": "Year"},
    "zones": {"PT": "Zonas", "EN": "Zones"},
    "provinces": {"PT": "Províncias", "EN": "Provinces"},
    "districts": {"PT": "Distritos", "EN": "Districts"},
    "help_year": {"PT": "Selecione o ano para análise.", "EN": "Select the year for analysis."},
    "help_zones": {"PT": "Filtre por zona geográfica: Norte, Centro ou Sul de Moçambique.", "EN": "Filter by geographic zone: North, Centre or South of Mozambique."},
    "help_prov": {"PT": "Selecione as províncias que deseja visualizar.", "EN": "Select the provinces you wish to view."},
    "help_dist": {"PT": "Opcional: refine a análise ao nível distrital.", "EN": "Optional: drill down to district level."},
    # Tab names
    "tab_demo": {"PT": "🗺️ Contexto Demográfico", "EN": "🗺️ Demographic Context"},
    "tab_overview": {"PT": "📊 Visão Geral", "EN": "📊 Overview"},
    "tab_accounts": {"PT": "🏦 Contas", "EN": "🏦 Accounts"},
    "tab_cards": {"PT": "💳 Cartões", "EN": "💳 Cards"},
    "tab_infra": {"PT": "📡 Infraestrutura", "EN": "📡 Infrastructure"},
    "tab_digital": {"PT": "📱 Canais Digitais", "EN": "📱 Digital Channels"},
    "tab_txn": {"PT": "💸 Transações", "EN": "💸 Transactions"},
    "tab_trends": {"PT": "📈 Tendências Históricas", "EN": "📈 Historical Trends"},
    "tab_heatmap": {"PT": "🔥 Mapa de Calor", "EN": "🔥 Heatmap"},
    "tab_forecast": {"PT": "🔮 Previsões", "EN": "🔮 Forecasts"},
    # Page titles
    "title_demo": {"PT": "Contexto Demográfico de Moçambique", "EN": "Mozambique Demographic Context"},
    "title_overview": {"PT": "Estado do Sistema Financeiro", "EN": "Financial System Status"},
    "title_accounts": {"PT": "Análise Detalhada de Contas", "EN": "Detailed Account Analysis"},
    "title_cards": {"PT": "Análise Detalhada de Cartões", "EN": "Detailed Card Analysis"},
    "title_infra": {"PT": "Infraestrutura Física", "EN": "Physical Infrastructure"},
    "title_digital": {"PT": "Canais Digitais — Mobile Banking e Internet Banking", "EN": "Digital Channels — Mobile Banking & Internet Banking"},
    "title_txn": {"PT": "Volume e Valor de Transações", "EN": "Transaction Volume & Value"},
    "title_trends": {"PT": "Tendências Históricas", "EN": "Historical Trends"},
    "title_heatmap": {"PT": "Mapa de Calor — Indicadores por Província", "EN": "Heatmap — Indicators by Province"},
    "title_forecast": {"PT": "Previsões e Simulação de Crescimento", "EN": "Forecasts & Growth Simulation"},
    # Common labels
    "month": {"PT": "Mês", "EN": "Month"},
    "value": {"PT": "Valor", "EN": "Value"},
    "province": {"PT": "Província", "EN": "Province"},
    "district": {"PT": "Distrito", "EN": "District"},
    "total_accounts": {"PT": "Total de Contas", "EN": "Total Accounts"},
    "total_cards": {"PT": "Total de Cartões", "EN": "Total Cards"},
    "monthly_trend_accounts": {"PT": "Tendência Mensal de Contas", "EN": "Monthly Account Trend"},
    "monthly_trend_cards": {"PT": "Tendência Mensal de Cartões", "EN": "Monthly Card Trend"},
    "annual_by_province": {"PT": "Total Anual por Província", "EN": "Annual Total by Province"},
    "indicator": {"PT": "Indicador", "EN": "Indicator"},
    "metric": {"PT": "Métrica", "EN": "Metric"},
    "channel": {"PT": "Canal", "EN": "Channel"},
    "comparison_metric": {"PT": "Métrica para Comparação", "EN": "Comparison Metric"},
    "detailed_metric": {"PT": "Métrica Detalhada", "EN": "Detailed Metric"},
    "monthly_comparison": {"PT": "Comparação Mensal", "EN": "Monthly Comparison"},
    "annual_comparison": {"PT": "Comparação Anual", "EN": "Annual Comparison"},
    "monthly_trend": {"PT": "Tendência Mensal", "EN": "Monthly Trend"},
    "annual_and_growth": {"PT": "Total Anual e Crescimento", "EN": "Annual Total & Growth"},
    "yoy_growth": {"PT": "Crescimento Anual (%)", "EN": "Year-on-Year Growth (%)"},
    "txn_category": {"PT": "Categoria de Transação", "EN": "Transaction Category"},
    "monthly_volume": {"PT": "Volume Mensal", "EN": "Monthly Volume"},
    "monthly_value": {"PT": "Valor Mensal (MZN)", "EN": "Monthly Value (MZN)"},
    "annual_dual": {"PT": "Volume e Valor Anual", "EN": "Annual Volume & Value"},
    "volume": {"PT": "Volume", "EN": "Volume"},
    "trend_indicator": {"PT": "Indicador de Tendência", "EN": "Trend Indicator"},
    "sub_metric": {"PT": "Sub-métrica", "EN": "Sub-metric"},
    "annual_evolution": {"PT": "Evolução Anual", "EN": "Annual Evolution"},
    "province_trends": {"PT": "Tendência por Província", "EN": "Province Trends"},
    "heatmap_indicator": {"PT": "Indicador do Mapa de Calor", "EN": "Heatmap Indicator"},
    "annual_growth_prov": {"PT": "Crescimento Anual (%) por Província", "EN": "Annual Growth (%) by Province"},
    # Forecasting
    "forecast_horizon": {"PT": "Horizonte de Previsão (anos)", "EN": "Forecast Horizon (years)"},
    "forecast_indicator": {"PT": "Indicador para Previsão", "EN": "Forecast Indicator"},
    "national_forecast": {"PT": "Previsão Nacional", "EN": "National Forecast"},
    "province_forecast": {"PT": "Previsão por Província", "EN": "Forecast by Province"},
    "forecast_summary": {"PT": "Resumo das Previsões por Província", "EN": "Province Forecast Summary"},
    "manual_simulator": {"PT": "Simulador Manual de Crescimento", "EN": "Manual Growth Simulator"},
    "manual_sim_desc": {
        "PT": "Ajuste a taxa de crescimento manualmente para simular cenários alternativos. O valor inicial é baseado na taxa de crescimento anual composta (CAGR) dos dados históricos.",
        "EN": "Adjust the growth rate manually to simulate alternative scenarios. The default value is based on the historical Compound Annual Growth Rate (CAGR)."
    },
    "annual_rate": {"PT": "Taxa Anual (%)", "EN": "Annual Rate (%)"},
    "projection_years": {"PT": "Anos de Projecção", "EN": "Projection Years"},
    "projection_for": {"PT": "Projecção para", "EN": "Projection for"},
    "total_growth": {"PT": "crescimento total", "EN": "total growth"},
    "historic": {"PT": "Histórico", "EN": "Historic"},
    "forecast": {"PT": "Previsão", "EN": "Forecast"},
    "model_good": {"PT": "✅ Ajuste do modelo: **Bom** — o modelo explica a maior parte da variação nos dados.", "EN": "✅ Model fit: **Good** — the model explains most of the variance in the data."},
    "model_moderate": {"PT": "⚠️ Ajuste do modelo: **Moderado** — as previsões devem ser interpretadas com cautela.", "EN": "⚠️ Model fit: **Moderate** — forecasts should be interpreted with caution."},
    "model_weak": {"PT": "❌ Ajuste do modelo: **Fraco** — os dados apresentam padrões não lineares complexos. Use o simulador manual como alternativa.", "EN": "❌ Model fit: **Weak** — data shows complex non-linear patterns. Use the manual simulator as an alternative."},
    "insufficient_data": {"PT": "Dados insuficientes para previsão (necessário pelo menos 3 observações mensais).", "EN": "Insufficient data for forecasting (at least 3 monthly observations required)."},
    "stock_label": {"PT": "stock (fim de período)", "EN": "stock (end of period)"},
    "flow_label": {"PT": "fluxo (soma anual)", "EN": "flow (annual sum)"},
    # Methodology
    "methodology": {
        "PT": (
            "📐 **Metodologia** — As previsões são calculadas através de **regressão polinomial de grau 2** "
            "aplicada à série temporal mensal de cada indicador. Para indicadores de *stock* (contas, cartões, ATMs, POS), "
            "utiliza-se o valor de fim de período; para indicadores de *fluxo* (transações), utiliza-se a soma anual. "
            "A banda de confiança a 95% (±1,96σ) reflecte a dispersão dos resíduos do modelo."
        ),
        "EN": (
            "📐 **Methodology** — Forecasts use **degree-2 polynomial regression** on monthly time series. "
            "For *stock* indicators (accounts, cards, ATMs, POS), end-of-period values are used; "
            "for *flow* indicators (transactions), annual sums are used. "
            "The 95% confidence band (±1.96σ) reflects the dispersion of model residuals."
        ),
    },
    # Forecast page caption
    "forecast_caption": {
        "PT": "ℹ️ Previsões baseadas em regressão polinomial sobre dados mensais, com bandas de confiança. O simulador manual permite testar cenários de crescimento personalizado.",
        "EN": "ℹ️ Forecasts based on polynomial regression over monthly data, with confidence bands. The manual simulator allows testing custom growth scenarios."
    },
    # Page captions
    "caption_overview": {
        "PT": "ℹ️ Resumo dos principais indicadores do sistema financeiro para o ano e províncias selecionadas. Os deltas mostram a variação face ao ano anterior.",
        "EN": "ℹ️ Summary of key financial system indicators for the selected year and provinces. Deltas show year-on-year change."
    },
    "caption_accounts": {
        "PT": "ℹ️ Detalhes sobre contas bancárias: tendência mensal, distribuição por faixa etária e moeda. Filtrado pelo ano e províncias selecionadas.",
        "EN": "ℹ️ Bank account details: monthly trend, age distribution, and currency split. Filtered by the selected year and provinces."
    },
    "caption_cards": {
        "PT": "ℹ️ Evolução mensal, distribuição por faixa etária e tipo de cartão (crédito, débito, pré-pago). Filtrado pelo ano e províncias selecionadas.",
        "EN": "ℹ️ Monthly evolution, age group distribution, and card type (credit, debit, prepaid). Filtered by the selected year and provinces."
    },
    "caption_infra": {
        "PT": "ℹ️ Distribuição geográfica de ATMs e terminais POS. Use os filtros da barra lateral para refinar por zona, província ou distrito.",
        "EN": "ℹ️ Geographic distribution of ATMs and POS terminals. Use sidebar filters to drill down by zone, province or district."
    },
    "caption_digital": {
        "PT": "ℹ️ Selecione o canal e a métrica para ver a evolução mensal e anual. A comparação directa Mobile vs Internet aparece no primeiro gráfico.",
        "EN": "ℹ️ Select the channel and metric to view monthly and annual trends. The direct Mobile vs Internet comparison appears in the first chart."
    },
    "caption_txn": {
        "PT": "ℹ️ Selecione o tipo de transação no menu abaixo para comparar volume (quantidade) e valor (MZN) mensal e anual.",
        "EN": "ℹ️ Select the transaction type below to compare monthly and annual volume (count) and value (MZN)."
    },
    "caption_trends": {
        "PT": "ℹ️ Evolução multi-anual dos principais indicadores. Selecione o indicador no menu abaixo.",
        "EN": "ℹ️ Multi-year evolution of key indicators. Select the indicator in the menu below."
    },
    "caption_heatmap": {
        "PT": "ℹ️ Visualização matricial por província e ano. Cores mais intensas indicam valores mais elevados. O segundo mapa mostra a taxa de crescimento anual.",
        "EN": "ℹ️ Matrix view by province and year. Darker colours indicate higher values. The second map shows annual growth rates."
    },
    "caption_demo": {
        "PT": "ℹ️ Dados demográficos do Censo 2017 (INE) combinados com dados bancários para medir a inclusão financeira por província.",
        "EN": "ℹ️ Census 2017 demographics (INE) combined with banking data to measure financial inclusion by province."
    },
    # Demographic Context page
    "census_source": {
        "PT": "📋 **Fonte demográfica:** IV Recenseamento Geral da População e Habitação, 2017 — Instituto Nacional de Estatística (INE). População de referência: 1 de Agosto de 2017 (27,9 milhões).",
        "EN": "📋 **Demographic source:** IV General Census of Population and Housing, 2017 — National Statistics Institute (INE). Reference population: 1 August 2017 (27.9 million)."
    },
    "population_by_province": {"PT": "População por Província (Censo 2017)", "EN": "Population by Province (Census 2017)"},
    "gender_split": {"PT": "Distribuição por Género", "EN": "Gender Distribution"},
    "urban_rural": {"PT": "Urbano vs Rural", "EN": "Urban vs Rural"},
    "age_structure": {"PT": "Estrutura Etária", "EN": "Age Structure"},
    "financial_inclusion": {"PT": "Indicadores de Inclusão Financeira", "EN": "Financial Inclusion Indicators"},
    "accounts_per_capita": {"PT": "Contas per Capita", "EN": "Accounts per Capita"},
    "cards_per_capita": {"PT": "Cartões per Capita", "EN": "Cards per Capita"},
    "atm_per_100k": {"PT": "ATMs por 100 mil hab.", "EN": "ATMs per 100k pop."},
    "pos_per_100k": {"PT": "POS por 100 mil hab.", "EN": "POS per 100k pop."},
    "penetration_map": {"PT": "Mapa de Penetração Bancária", "EN": "Banking Penetration Map"},
    "underbanked_gap": {"PT": "Hiato de Inclusão — População vs Contas Bancárias", "EN": "Inclusion Gap — Population vs Bank Accounts"},
    "gender_parity": {"PT": "Índice de Paridade de Género", "EN": "Gender Parity Index"},
    "gender_parity_desc": {
        "PT": "Proporção de contas femininas vs proporção feminina na população. Valores < 1 indicam menor acesso feminino ao sistema financeiro.",
        "EN": "Female account share vs female population share. Values < 1 indicate lower female access to financial services."
    },
    "phone_vs_mobile_banking": {"PT": "Posse de Telemóvel vs Mobile Banking", "EN": "Phone Ownership vs Mobile Banking"},
    "internet_vs_internet_banking": {"PT": "Acesso à Internet vs Internet Banking", "EN": "Internet Access vs Internet Banking"},
    "connectivity_context": {"PT": "Conectividade e Canais Digitais", "EN": "Connectivity & Digital Channels"},
    "connectivity_desc": {
        "PT": "Comparação entre a posse de telemóvel e uso de internet (Censo 2017) com a adopção de canais bancários digitais — indicando o potencial de crescimento por província.",
        "EN": "Comparison between phone ownership and internet usage (Census 2017) with digital banking adoption — indicating growth potential by province."
    },
    # Existing page labels that were hardcoded
    "gender_distribution": {"PT": "Distribuição por Género", "EN": "Gender Distribution"},
    "accounts_distribution": {"PT": "Distribuição de Contas", "EN": "Account Distribution"},
    "accounts_by_age": {"PT": "Contas por Faixa Etária", "EN": "Accounts by Age Group"},
    "currency_distribution": {"PT": "Distribuição de Moeda", "EN": "Currency Distribution"},
    "product_adoption_age": {"PT": "Adoção de Produto por Idade", "EN": "Product Adoption by Age"},
    "card_type": {"PT": "Tipo de Cartão", "EN": "Card Type"},
    "atm_distribution": {"PT": "Distribuição de ATMs", "EN": "ATM Distribution"},
    "pos_distribution": {"PT": "Distribuição de POS", "EN": "POS Distribution"},
    "num_atms": {"PT": "Número de ATMs", "EN": "Number of ATMs"},
    "num_pos": {"PT": "Número de POS", "EN": "Number of POS"},
    "txn_type": {"PT": "Tipo de Transação", "EN": "Transaction Type"},
    "help_txn": {"PT": "Escolha entre ATM, POS, Mobile Banking ou Internet Banking.", "EN": "Choose between ATM, POS, Mobile Banking or Internet Banking."},
    "help_comparison": {"PT": "Métricas comuns a ambos os canais.", "EN": "Metrics common to both channels."},
    "help_channel": {"PT": "Escolha o canal para análise detalhada.", "EN": "Choose the channel for detailed analysis."},
    "help_detail_metric": {"PT": "Métrica específica para análise mensal e anual.", "EN": "Specific metric for monthly and annual analysis."},
    "help_indicator": {"PT": "Selecione o indicador para visualizar.", "EN": "Select the indicator to view."},
    "help_sub_metric": {"PT": "Escolha a métrica específica para este canal.", "EN": "Choose the specific metric for this channel."},
    "help_heatmap": {"PT": "Escolha o indicador para o mapa de calor.", "EN": "Choose the indicator for the heatmap."},
    "growth_rate_heatmap": {"PT": "Mapa de Calor — Taxa de Crescimento (%)", "EN": "Heatmap — Growth Rate (%)"},
    "by_province_year": {"PT": "por Província e Ano", "EN": "by Province and Year"},
    "by_year": {"PT": "por Ano", "EN": "by Year"},
    "by_province_over_years": {"PT": "por Província ao Longo dos Anos", "EN": "by Province Over the Years"},
    "vol_monthly_title": {"PT": "Volume Mensal", "EN": "Monthly Volume"},
    "val_monthly_title": {"PT": "Valor Mensal (MZN)", "EN": "Monthly Value (MZN)"},
    "annual_evol_title": {"PT": "Evolução Anual", "EN": "Annual Evolution"},
    "accounts_by_gender": {"PT": "Contas por Género", "EN": "Accounts by Gender"},
    "cards_by_gender": {"PT": "Cartões por Género", "EN": "Cards by Gender"},
    "gender_label": {"PT": "Género", "EN": "Gender"},
    "age_group": {"PT": "Faixa Etária", "EN": "Age Group"},
    "currency_label": {"PT": "Moeda", "EN": "Currency"},
    "card_type_label": {"PT": "Tipo de Cartão", "EN": "Card Type"},
    "growth_pct": {"PT": "Crescimento (%)", "EN": "Growth (%)"},
    "per_by": {"PT": "por", "EN": "by"},
    # Census KPI labels for existing pages
    "census_kpis": {
        "PT": "📊 Indicadores per Capita (Censo 2017)",
        "EN": "📊 Per Capita Indicators (Census 2017)"
    },
    "census_note_short": {
        "PT": "ℹ️ *Dados demográficos: Censo 2017 (INE)*",
        "EN": "ℹ️ *Demographics: Census 2017 (INE)*"
    },
    # Footer
    "footer": {
        "PT": "Desenvolvido por <b>Valter Cheque</b>",
        "EN": "Developed by <b>Valter Cheque</b>"
    },
}


def T(key):
    """Return translated string for the current language."""
    lang = st.session_state.lang
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        return key
    if isinstance(entry, dict):
        return entry.get(lang, entry.get("PT", key))
    return entry  # raw string


# ── Data loading (cached so Streamlit doesn't re-read CSVs on every rerun) ──
@st.cache_data
def load_data():
    """Load all 9 CSV datasets + census, apply common transformations, and return
    a dict of DataFrames plus reference lists used across the dashboard."""

    file_paths = {
        "accounts": "accounts_2020_2024.csv",
        "cards": "cards_2020_2024.csv",
        "atm": "ATM_Infrastructure_2020_2024.csv",
        "transactions_vol": "transactions_vol_2020_2024.csv",
        "pos": "POS_Infrastructure_2020_2024.csv",
        "transactions_val": "transactions_val_2020_2024.csv",
        "mobile_banking": "Mobile_Banking_2020_2024.csv",
        "internet_banking": "Internet_Banking_2020_2024.csv",
        "pos_transactions": "POS_Transactions_2020_2024.csv"
    }

    # Provinces ordered geographically North → South
    regions = {
        "Zona Norte": ["Cabo Delgado", "Niassa", "Nampula"],
        "Zona Centro": ["Zambézia", "Sofala", "Tete", "Manica"],
        "Zona Sul": ["Inhambane", "Gaza", "Província de Maputo"]
    }

    # Categorical orderings used for consistent axis sorting
    age_order = ['0-16', '17-21', '22-60', '+60']
    month_order = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                   "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    gender_order = ['Mulheres', 'Homens', 'Outros']

    def process_df(df):
        """Standardise each DataFrame: clip negatives, map regions,
        and enforce categorical ordering on Age/Month/Gender."""
        num_cols = df.select_dtypes(include=['number']).columns
        df[num_cols] = df[num_cols].clip(lower=0)
        if 'Province' in df.columns:
            df['Province'] = df['Province'].fillna("Não Definido").astype(str)
            df['Region'] = df['Province'].map({p: r for r, ps in regions.items() for p in ps})
        if 'Age' in df.columns:
            df['Age'] = pd.Categorical(df['Age'].astype(str), categories=age_order, ordered=True)
        if 'Month' in df.columns:
            df['Month'] = pd.Categorical(df['Month'], categories=month_order, ordered=True)
        if 'Gender' in df.columns:
            df['Gender'] = pd.Categorical(df['Gender'].astype(str), categories=gender_order, ordered=True)
        return df

    dataframes = {name: process_df(pd.read_csv(path)) for name, path in file_paths.items()}

    # Load census data
    census_df = pd.read_csv("census_2017_provinces.csv")

    return dataframes, regions, age_order, month_order, census_df


# Unpack into friendly short names used throughout the dashboard
dataframes, regions_map, age_order, m_order, census_df = load_data()
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


# ── Data normalisation helpers ──────────────────────────────────────────────
def normalize_atm_txn(df, value_col):
    """Fix naming inconsistencies in ATM transaction data between 2020 and 2021+."""
    df = df.copy()
    df.loc[df['Metric'] == 'Transferências para', 'Metric'] = 'Transferências'
    df.loc[df['Sub_Metric'] == 'contas bancárias', 'Sub_Metric'] = 'para Contas Bancárias'
    mask_tel = df['Metric'].isin(['telemóveis', 'para telemóveis'])
    df.loc[mask_tel, 'Sub_Metric'] = 'para telemóveis'
    df.loc[mask_tel, 'Metric'] = 'Transferências'
    return df


# ── Census helpers ──────────────────────────────────────────────────────────
def get_census_province(province_name):
    """Match banking Province name to census Province name."""
    row = census_df[census_df['Province'] == province_name]
    if row.empty:
        # Try matching Maputo Cidade or Maputo Provincia
        if 'Maputo' in province_name and 'Cidade' in province_name:
            row = census_df[census_df['Province'] == 'Maputo Cidade']
        elif 'Maputo' in province_name:
            row = census_df[census_df['Province'].str.contains('Maputo', case=False)]
            row = row[~row['Province'].str.contains('Cidade', case=False)]
    return row.iloc[0] if not row.empty else None


# ── Forecasting helpers ─────────────────────────────────────────────────────
STOCK_INDICATORS = {"Contas Bancárias", "Cartões Bancários", "ATMs", "POS"}
FLOW_INDICATORS = {
    "Mobile Banking", "Internet Banking",
    "Transações ATM (Volume)", "Transações ATM (Valor)",
    "Transações POS (Volume)", "Transações POS (Valor)",
    "Transações Mobile Banking (Volume)", "Transações Mobile Banking (Valor)",
    "Transações Internet Banking (Volume)", "Transações Internet Banking (Valor)",
}

MONTH_NUM = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
    "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
    "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12,
}


def build_monthly_series(df, metric_col, indicator_name):
    """Build a monthly time series with a fractional-year time index."""
    if 'Month' not in df.columns:
        yearly = df.groupby('Year')[metric_col].sum().reset_index()
        yearly.columns = ['Year', 'Value']
        yearly['t'] = yearly['Year'].astype(float)
        yearly['Month_Num'] = 6
        return yearly.sort_values('t').reset_index(drop=True)

    monthly = df.groupby(['Year', 'Month'], observed=False)[metric_col].sum().reset_index()
    monthly.columns = ['Year', 'Month', 'Value']
    monthly['Month_Num'] = monthly['Month'].map(MONTH_NUM).astype(float)
    monthly = monthly.dropna(subset=['Month_Num', 'Value'])
    monthly = monthly[monthly['Value'] > 0]
    monthly['t'] = monthly['Year'].astype(float) + (monthly['Month_Num'] - 1) / 12
    return monthly.sort_values('t').reset_index(drop=True)


def poly_forecast(monthly_series, n_future_years=5, degree=2):
    """Fit a polynomial regression on monthly data and forecast future months."""
    if len(monthly_series) < 3:
        return None, None, None, None

    t = monthly_series[['t']].values
    y = monthly_series['Value'].values

    poly = PolynomialFeatures(degree=degree, include_bias=False)
    t_poly = poly.fit_transform(t)

    model = LinearRegression()
    model.fit(t_poly, y)

    r2 = model.score(t_poly, y)
    y_pred_hist = model.predict(t_poly)
    residual_std = np.std(y - y_pred_hist)

    hist_df = monthly_series[['t', 'Value']].copy()
    hist_df['Tipo'] = T("historic")
    hist_df['Year_Label'] = monthly_series['t'].apply(lambda x: int(x))

    last_t = monthly_series['t'].max()
    last_year = int(last_t)
    future_ts = []
    for yr_offset in range(1, n_future_years + 1):
        for m in range(12):
            future_ts.append(last_year + yr_offset + m / 12)
    future_t = np.array(future_ts).reshape(-1, 1)
    future_poly = poly.transform(future_t)
    future_vals = model.predict(future_poly).clip(min=0)

    pred_df = pd.DataFrame({
        't': future_t.flatten(),
        'Value': future_vals,
        'Tipo': T("forecast"),
        'Year_Label': [int(x) for x in future_t.flatten()]
    })

    combined = pd.concat([hist_df, pred_df], ignore_index=True)

    # Add confidence bands
    combined['Upper'] = (combined['Value'] + 1.96 * residual_std).clip(lower=0)
    combined['Lower'] = (combined['Value'] - 1.96 * residual_std).clip(lower=0)

    return combined, r2, residual_std, (poly, model)


def aggregate_forecast_yearly(combined_df, indicator_name):
    """Aggregate the monthly forecast back to yearly values."""
    if combined_df is None or combined_df.empty:
        return pd.DataFrame()

    hist_label = T("historic")
    if indicator_name in STOCK_INDICATORS:
        idx = combined_df.groupby('Year_Label')['t'].idxmax()
        yearly = combined_df.loc[idx, ['Year_Label', 'Value', 'Tipo', 'Upper', 'Lower']].copy()
    else:
        yearly = combined_df.groupby(['Year_Label', 'Tipo']).agg(
            Value=('Value', 'sum'),
            Upper=('Upper', 'sum'),
            Lower=('Lower', 'sum')
        ).reset_index()

    yearly = yearly.rename(columns={'Year_Label': 'Ano', 'Value': 'Valor'})
    yearly = yearly.sort_values('Ano')
    return yearly


# ── Dashboard tabs ──────────────────────────────────────────────────────────
# 10 pages: demographics first, then original 9
tabs = st.tabs([
    T("tab_demo"), T("tab_overview"), T("tab_accounts"), T("tab_cards"), T("tab_infra"),
    T("tab_digital"), T("tab_txn"), T("tab_trends"),
    T("tab_heatmap"), T("tab_forecast")
])

# ==========================================
# PAGE 1: CONTEXTO DEMOGRÁFICO (CENSUS)
# ==========================================
with tabs[0]:
    st.title(T("title_demo"))
    st.caption(T("caption_demo"))
    st.info(T("census_source"))

    # --- Population overview bar chart ---
    st.subheader(T("population_by_province"))
    census_filtered = census_df[census_df['Province'].isin(
        [p for p in census_df['Province'] if any(p in prov or prov in p for prov in selected_prov)]
    )]
    # If no match via substring, show all
    if census_filtered.empty:
        census_filtered = census_df.copy()

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

    # Compute per-capita from the latest year banking data
    latest_year = max(all_years)
    latest_acc = acc_df[acc_df['Year'] == latest_year]
    latest_card = card_df[card_df['Year'] == latest_year]
    latest_atm = atm_df[atm_df['Year'] == latest_year]
    latest_pos = pos_df[pos_df['Year'] == latest_year]

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
        # Match banking data province name
        prov_acc = latest_acc[latest_acc['Province'].str.contains(prov_name.split()[0], case=False, na=False)]
        if prov_acc.empty and 'Maputo' in prov_name:
            if 'Cidade' in prov_name:
                prov_acc = latest_acc[latest_acc['Province'].str.contains('Maputo', case=False, na=False)]
            else:
                prov_acc = latest_acc[latest_acc['Province'] == 'Província de Maputo']
        total_a = prov_acc['Total_Accounts'].sum() if not prov_acc.empty else 0
        gap_rows.append({
            T("province"): prov_name,
            'Population (Census 2017)': row['Population_Total'],
            f'{T("total_accounts")} ({latest_year})': total_a,
            T("accounts_per_capita"): round(total_a / row['Population_Total'], 3) if row['Population_Total'] > 0 else 0
        })

    gap_df = pd.DataFrame(gap_rows).sort_values(T("accounts_per_capita"), ascending=False)

    fig_gap = go.Figure()
    fig_gap.add_trace(go.Bar(
        x=gap_df[T("province")],
        y=gap_df['Population (Census 2017)'],
        name='População (Censo 2017)' if st.session_state.lang == 'PT' else 'Population (Census 2017)',
        marker_color='#636EFA'
    ))
    fig_gap.add_trace(go.Bar(
        x=gap_df[T("province")],
        y=gap_df[f'{T("total_accounts")} ({latest_year})'],
        name=f'{T("total_accounts")} ({latest_year})',
        marker_color='#EF553B'
    ))
    fig_gap.update_layout(barmode='group', xaxis_title=T("province"), yaxis_title=T("value"), height=450)
    st.plotly_chart(fig_gap, use_container_width=True)

    # Per capita bar chart
    fig_pc = px.bar(
        gap_df, x=T("province"), y=T("accounts_per_capita"),
        color=T("accounts_per_capita"), color_continuous_scale='RdYlGn',
        text=[f"{v:.2f}" for v in gap_df[T("accounts_per_capita")]],
    )
    fig_pc.update_layout(
        title=T("accounts_per_capita"),
        yaxis_title=T("accounts_per_capita"),
        coloraxis_showscale=False, height=400
    )
    st.plotly_chart(fig_pc, use_container_width=True)

    # --- Gender Parity Index ---
    st.markdown("---")
    st.subheader(T("gender_parity"))
    st.markdown(T("gender_parity_desc"))

    gpi_rows = []
    for _, row in census_filtered.iterrows():
        prov_name = row['Province']
        prov_acc_data = latest_acc[latest_acc['Province'].str.contains(prov_name.split()[0], case=False, na=False)]
        if prov_acc_data.empty and 'Maputo' in prov_name:
            if 'Cidade' in prov_name:
                prov_acc_data = latest_acc[latest_acc['Province'].str.contains('Maputo', case=False, na=False)]
            else:
                prov_acc_data = latest_acc[latest_acc['Province'] == 'Província de Maputo']
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

    # YoY comparison metrics
    prev_year = selected_year - 1
    prev_acc = dataframes["accounts"][(dataframes["accounts"]['Year'] == prev_year) & (dataframes["accounts"]['Province'].isin(selected_prov))]
    prev_card = dataframes["cards"][(dataframes["cards"]['Year'] == prev_year) & (dataframes["cards"]['Province'].isin(selected_prov))]
    prev_atm = dataframes["atm"][(dataframes["atm"]['Year'] == prev_year) & (dataframes["atm"]['Province'].isin(selected_prov))]

    curr_acc_total = f_acc['Total_Accounts'].sum()
    prev_acc_total = prev_acc['Total_Accounts'].sum()
    curr_card_total = f_card['Total_Cards'].sum()
    prev_card_total = prev_card['Total_Cards'].sum()
    curr_atm_total = f_atm['ATMs_Number'].sum()
    prev_atm_total = prev_atm['ATMs_Number'].sum()

    def calc_delta(curr, prev):
        if prev > 0:
            pct = ((curr - prev) / prev) * 100
            return f"{pct:+.1f}%"
        return None

    c1, c2, c3 = st.columns(3)
    c1.metric(T("total_accounts"), f"{curr_acc_total:,.0f}", delta=calc_delta(curr_acc_total, prev_acc_total))
    c2.metric(T("total_cards"), f"{curr_card_total:,.0f}", delta=calc_delta(curr_card_total, prev_card_total))
    c3.metric("Total ATMs", f"{curr_atm_total:,.0f}", delta=calc_delta(curr_atm_total, prev_atm_total))

    # Per-capita KPIs from census
    st.markdown(f"###### {T('census_kpis')}")
    total_pop_sel = census_df[census_df['Province'].isin(
        [p for p in census_df['Province'] if any(p in prov or prov in p for prov in selected_prov)]
    )]['Population_Total'].sum()
    if total_pop_sel > 0:
        ov_k1, ov_k2, ov_k3 = st.columns(3)
        ov_k1.metric(T("accounts_per_capita"), f"{curr_acc_total / total_pop_sel:.2f}")
        ov_k2.metric(T("cards_per_capita"), f"{curr_card_total / total_pop_sel:.2f}")
        ov_k3.metric(T("atm_per_100k"), f"{curr_atm_total / total_pop_sel * 100_000:.1f}")
        st.caption(T("census_note_short"))

    st.subheader(T("gender_distribution"))
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        gen_acc = f_acc.groupby('Gender', observed=False)['Total_Accounts'].sum().reset_index()
        gen_acc.columns = [T("gender_label"), T("total_accounts")]
        st.plotly_chart(px.pie(gen_acc, values=T("total_accounts"), names=T("gender_label"),
                               title=T("accounts_by_gender"), hole=0.4), use_container_width=True)
    with g_col2:
        gen_card = f_card.groupby('Gender', observed=False)['Total_Cards'].sum().reset_index()
        gen_card.columns = [T("gender_label"), T("total_cards")]
        st.plotly_chart(px.pie(gen_card, values=T("total_cards"), names=T("gender_label"),
                               title=T("cards_by_gender"), hole=0.4), use_container_width=True)

    st.subheader(f"{T('accounts_distribution')} {title_suffix}")
    prov_summary = f_acc.groupby(geo_axis)['Total_Accounts'].sum().sort_values(ascending=False).reset_index()
    prov_summary.columns = [geo_axis_label, T("total_accounts")]
    st.plotly_chart(px.bar(prov_summary, x=geo_axis_label, y=T("total_accounts"), color=geo_axis_label), use_container_width=True)

# ==========================================
# PAGE 3: CONTAS
# ==========================================
with tabs[2]:
    st.title(T("title_accounts"))
    st.caption(T("caption_accounts"))

    st.subheader(T("monthly_trend_accounts"))
    month_acc = f_acc.groupby('Month', observed=False)['Total_Accounts'].sum().reset_index()
    month_acc.columns = [T("month"), T("total_accounts")]
    fig_month_acc = px.line(month_acc, x=T("month"), y=T("total_accounts"), markers=True)
    fig_month_acc.update_layout(yaxis=dict(rangemode='tozero'))
    st.plotly_chart(fig_month_acc, use_container_width=True)

    st.subheader(T("accounts_by_age"))
    age_acc = f_acc.groupby('Age', observed=False)['Total_Accounts'].sum().reset_index()
    age_acc.columns = [T("age_group"), T("total_accounts")]
    st.plotly_chart(px.bar(age_acc, y=T("age_group"), x=T("total_accounts"), orientation='h', color=T("age_group")), use_container_width=True)

    st.subheader(f"{T('currency_distribution')} {title_suffix}")
    curr_data = f_acc.groupby([geo_axis, 'Account_Currency'])['Total_Accounts'].sum().reset_index()
    curr_data.columns = [geo_axis_label, T("currency_label"), T("total_accounts")]
    st.plotly_chart(px.bar(curr_data, x=geo_axis_label, y=T("total_accounts"), color=T("currency_label"), barmode='group'), use_container_width=True)

# ==========================================
# PAGE 4: CARTÕES
# ==========================================
with tabs[3]:
    st.title(T("title_cards"))
    st.caption(T("caption_cards"))

    st.subheader(T("monthly_trend_cards"))
    month_card = f_card.groupby('Month', observed=False)['Total_Cards'].sum().reset_index()
    month_card.columns = [T("month"), T("total_cards")]
    fig_month_card = px.line(month_card, x=T("month"), y=T("total_cards"), markers=True)
    fig_month_card.update_layout(yaxis=dict(rangemode='tozero'))
    st.plotly_chart(fig_month_card, use_container_width=True)

    st.subheader(T("product_adoption_age"))
    age_card = f_card.groupby(['Age', 'Card_Type'], observed=False)['Total_Cards'].sum().reset_index()
    age_card.columns = [T("age_group"), T("card_type_label"), T("total_cards")]
    st.plotly_chart(px.bar(age_card, y=T("age_group"), x=T("total_cards"), color=T("card_type_label"), orientation='h'), use_container_width=True)

    st.subheader(f"{T('card_type')} {title_suffix}")
    card_type_geo = f_card.groupby([geo_axis, 'Card_Type'])['Total_Cards'].sum().reset_index()
    card_type_geo.columns = [geo_axis_label, T("card_type_label"), T("total_cards")]
    st.plotly_chart(px.bar(card_type_geo, x=geo_axis_label, y=T("total_cards"), color=T("card_type_label"), barmode='group'), use_container_width=True)

# ==========================================
# PAGE 5: INFRAESTRUTURA
# ==========================================
with tabs[4]:
    st.title(T("title_infra"))
    st.caption(T("caption_infra"))

    # Per-capita infrastructure from census
    if total_pop_sel > 0:
        curr_pos_total = f_pos['POSs_Number'].sum()
        inf_k1, inf_k2 = st.columns(2)
        inf_k1.metric(T("atm_per_100k"), f"{curr_atm_total / total_pop_sel * 100_000:.1f}")
        inf_k2.metric(T("pos_per_100k"), f"{curr_pos_total / total_pop_sel * 100_000:.1f}")
        st.caption(T("census_note_short"))

    col_i1, col_i2 = st.columns(2)
    with col_i1:
        atm_sum = f_atm.groupby(geo_axis)['ATMs_Number'].sum().reset_index()
        atm_sum.columns = [geo_axis_label, T("num_atms")]
        st.plotly_chart(px.bar(atm_sum, x=geo_axis_label, y=T("num_atms"), title=T("atm_distribution")), use_container_width=True)
    with col_i2:
        pos_sum = f_pos.groupby(geo_axis)['POSs_Number'].sum().reset_index()
        pos_sum.columns = [geo_axis_label, T("num_pos")]
        st.plotly_chart(px.bar(pos_sum, x=geo_axis_label, y=T("num_pos"), title=T("pos_distribution")), use_container_width=True)

# ==========================================
# PAGE 6: CANAIS DIGITAIS (ENHANCED)
# ==========================================
with tabs[5]:
    st.title(T("title_digital"))
    st.caption(T("caption_digital"))

    common_metrics = sorted(set(mob_df['Metric'].unique()) & set(net_df['Metric'].unique()))
    if not common_metrics:
        common_metrics = sorted(mob_df['Metric'].unique())

    digital_metric = st.selectbox(
        T("comparison_metric"), common_metrics, key="digital_metric",
        help=T("help_comparison")
    )

    st.subheader(f"Mobile vs Internet — {digital_metric} ({selected_year})")
    f_mob = mob_df[(mob_df['Year'] == selected_year) & (mob_df['Metric'] == digital_metric)]
    f_net = net_df[(net_df['Year'] == selected_year) & (net_df['Metric'] == digital_metric)]
    m_mob = f_mob.groupby('Month', observed=False)['Value'].sum().reset_index().assign(Canal='Mobile Banking')
    m_net = f_net.groupby('Month', observed=False)['Value'].sum().reset_index().assign(Canal='Internet Banking')
    m_mob.rename(columns={'Month': T("month"), 'Value': T("value")}, inplace=True)
    m_net.rename(columns={'Month': T("month"), 'Value': T("value")}, inplace=True)
    comp_dig = pd.concat([m_mob, m_net])
    fig_comp_dig = px.line(comp_dig, x=T("month"), y=T("value"), color='Canal', markers=True,
                           title=f"{T('monthly_comparison')}: {digital_metric}")
    fig_comp_dig.update_layout(yaxis=dict(rangemode='tozero'))
    st.plotly_chart(fig_comp_dig, use_container_width=True)

    mob_yr = mob_df[mob_df['Metric'] == digital_metric].groupby('Year')['Value'].sum().reset_index().assign(Canal='Mobile Banking')
    net_yr = net_df[net_df['Metric'] == digital_metric].groupby('Year')['Value'].sum().reset_index().assign(Canal='Internet Banking')
    comp_yr = pd.concat([mob_yr, net_yr])
    comp_yr.rename(columns={'Year': T("year"), 'Value': T("value")}, inplace=True)
    fig_comp_yr = px.bar(comp_yr, x=T("year"), y=T("value"), color='Canal', barmode='group',
                          text_auto='.3s', title=f"{T('annual_evolution')}: {digital_metric}")
    fig_comp_yr.update_layout(xaxis=dict(dtick=1))
    st.plotly_chart(fig_comp_yr, use_container_width=True)

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

# ==========================================
# PAGE 7: TRANSAÇÕES
# ==========================================
with tabs[6]:
    st.title(T("title_txn"))
    st.caption(T("caption_txn"))

    vol_norm = normalize_atm_txn(vol_df, 'Total_Transactions')
    val_norm = normalize_atm_txn(val_df, 'Transactions_Amount')

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

    vol_monthly.rename(columns={'Month': T("month")}, inplace=True)
    val_monthly.rename(columns={'Month': T("month")}, inplace=True)

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        fig_vol_m = px.bar(vol_monthly, x=T("month"), y=T("volume"),
                           title=f"{T('vol_monthly_title')} — {txn_title}")
        fig_vol_m.update_layout(yaxis=dict(rangemode='tozero'))
        st.plotly_chart(fig_vol_m, use_container_width=True)
    with col_v2:
        fig_val_m = px.line(val_monthly, x=T("month"), y=T("value"), markers=True,
                            title=f"{T('val_monthly_title')} — {txn_title}")
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
            name=f'{T("value")} (MZN)', yaxis='y2', mode='lines+markers',
            marker_color='#EF553B', line=dict(width=3)))
        fig_annual.update_layout(
            title=f"{T('annual_evol_title')} — {txn_title}",
            xaxis=dict(title=T("year"), dtick=1),
            yaxis=dict(title=T("volume"), side='left'),
            yaxis2=dict(title=f'{T("value")} (MZN)', side='right', overlaying='y'),
            legend=dict(x=0.01, y=0.99), height=450)
        st.plotly_chart(fig_annual, use_container_width=True)

# ==========================================
# PAGE 8: TENDÊNCIAS HISTÓRICAS
# ==========================================
with tabs[7]:
    st.title(T("title_trends"))
    st.caption(T("caption_trends"))

    trend_indicator = st.selectbox(
        T("indicator"),
        ["Contas Bancárias", "Cartões Bancários", "ATMs", "POS",
         "Mobile Banking", "Internet Banking"],
        key="trend_indicator",
        help=T("help_indicator")
    )

    if trend_indicator == "Contas Bancárias":
        geo_trend = apply_geo_only(acc_df); trend_col = 'Total_Accounts'; trend_label = T("total_accounts")
    elif trend_indicator == "Cartões Bancários":
        geo_trend = apply_geo_only(card_df); trend_col = 'Total_Cards'; trend_label = T("total_cards")
    elif trend_indicator == "ATMs":
        geo_trend = apply_geo_only(atm_df); trend_col = 'ATMs_Number'; trend_label = T("num_atms")
    elif trend_indicator == "POS":
        geo_trend = apply_geo_only(pos_df); trend_col = 'POSs_Number'; trend_label = T("num_pos")
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
# PAGE 9: MAPA DE CALOR
# ==========================================
with tabs[8]:
    st.title(T("title_heatmap"))
    st.caption(T("caption_heatmap"))

    heatmap_metric = st.selectbox(T("indicator"), [
        "Contas Bancárias", "Cartões Bancários", "ATMs", "POS"
    ], key="heatmap_metric",
        help=T("help_heatmap")
    )

    if heatmap_metric == "Contas Bancárias":
        hm_data = apply_geo_only(acc_df).groupby(['Year', 'Province'])['Total_Accounts'].sum().reset_index()
        val_col = 'Total_Accounts'
    elif heatmap_metric == "Cartões Bancários":
        hm_data = apply_geo_only(card_df).groupby(['Year', 'Province'])['Total_Cards'].sum().reset_index()
        val_col = 'Total_Cards'
    elif heatmap_metric == "ATMs":
        hm_data = apply_geo_only(atm_df).groupby(['Year', 'Province'])['ATMs_Number'].sum().reset_index()
        val_col = 'ATMs_Number'
    else:
        hm_data = apply_geo_only(pos_df).groupby(['Year', 'Province'])['POSs_Number'].sum().reset_index()
        val_col = 'POSs_Number'

    if not hm_data.empty:
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
# PAGE 10: PREVISÕES (POLYNOMIAL + MONTHLY)
# ==========================================
with tabs[9]:
    st.title(T("title_forecast"))
    st.caption(T("forecast_caption"))

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
            df = normalize_atm_txn(vol_df, 'Total_Transactions')
            return df, 'Total_Transactions'
        else:
            df = normalize_atm_txn(val_df, 'Transactions_Amount')
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

    monthly_series = build_monthly_series(src_df, metric_col, forecast_indicator)

    hist_label = T("historic")
    pred_label = T("forecast")

    if len(monthly_series) >= 3:
        combined, r2, res_std, pipeline = poly_forecast(
            monthly_series, n_future_years=forecast_horizon, degree=2
        )

        if combined is not None:
            yearly_fc = aggregate_forecast_yearly(combined, forecast_indicator)

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

                st.info(
                    f"**R²:** {r2:.3f} · "
                    f"**{T('indicator')}:** {tipo_label} · "
                    f"**Data points:** {len(monthly_series)}"
                )

                if r2 >= 0.8:
                    st.success(T("model_good"))
                elif r2 >= 0.5:
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
                prov_monthly = build_monthly_series(prov_data, metric_col, forecast_indicator)
                if len(prov_monthly) >= 3:
                    prov_combined, prov_r2, _, _ = poly_forecast(
                        prov_monthly, n_future_years=forecast_horizon, degree=2
                    )
                    if prov_combined is not None:
                        prov_yearly = aggregate_forecast_yearly(prov_combined, forecast_indicator)
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
            f"{sim_vals[-1]:,.0f}",
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
