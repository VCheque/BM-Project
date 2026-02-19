"""Translation catalog and helpers for the dashboard."""

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
    "help_year": {"PT": "Seleccione o ano para análise.", "EN": "Select the year for analysis."},
    "help_zones": {"PT": "Filtre por zona geográfica: Norte, Centro ou Sul de Moçambique.", "EN": "Filter by geographic zone: North, Centre or South of Mozambique."},
    "help_prov": {"PT": "Seleccione as províncias que deseja visualizar.", "EN": "Select the provinces you wish to view."},
    "help_dist": {"PT": "Opcional: refine a análise ao nível distrital.", "EN": "Optional: drill down to district level."},
    # Tab names
    "tab_home": {"PT": "🏠 Início", "EN": "🏠 Home"},
    "tab_demo": {"PT": "🗺️ Contexto Demográfico", "EN": "🗺️ Demographic Context"},
    "tab_overview": {"PT": "📊 Visão Geral + Q&A", "EN": "📊 Overview + Q&A"},
    "tab_ime": {"PT": "📱 Carteiras Móveis", "EN": "📱 Mobile Wallets"},
    "tab_accounts": {"PT": "🏦 Contas", "EN": "🏦 Accounts"},
    "tab_cards": {"PT": "💳 Cartões", "EN": "💳 Cards"},
    "tab_infra": {"PT": "📡 Infraestrutura", "EN": "📡 Infrastructure"},
    "tab_digital": {"PT": "📱 Canais Digitais", "EN": "📱 Digital Channels"},
    "tab_txn": {"PT": "💸 Transacções", "EN": "💸 Transactions"},
    "tab_trends": {"PT": "📈 Tendências Históricas", "EN": "📈 Historical Trends"},
    "tab_heatmap": {"PT": "🔥 Mapa de Calor", "EN": "🔥 Heatmap"},
    "tab_forecast": {"PT": "🔮 Previsões", "EN": "🔮 Forecasts"},
    "tab_decision": {"PT": "🎯 Insights Estratégicos / Oportunidades", "EN": "🎯 Strategic Insights / Opportunities"},
    # Page titles
    "title_home": {
        "PT": "Dashboard de Banca Electrónica e Carteiras Móveis de Moçambique",
        "EN": "Mozambique Electronic Banking and Mobile Wallet Dashboard",
    },
    "title_demo": {"PT": "Contexto Demográfico de Moçambique", "EN": "Mozambique Demographic Context"},
    "title_overview": {"PT": "Visão Geral + Q&A", "EN": "Overview + Q&A"},
    "title_ime": {"PT": "Carteiras Móveis", "EN": "Mobile Wallets"},
    "title_accounts": {"PT": "Análise Detalhada de Contas", "EN": "Detailed Account Analysis"},
    "title_cards": {"PT": "Análise Detalhada de Cartões", "EN": "Detailed Card Analysis"},
    "title_infra": {"PT": "Infraestrutura Física", "EN": "Physical Infrastructure"},
    "title_digital": {"PT": "Canais Digitais — Mobile Banking e Internet Banking", "EN": "Digital Channels — Mobile Banking & Internet Banking"},
    "title_txn": {"PT": "Volume e Valor de Transacções", "EN": "Transaction Volume & Value"},
    "title_trends": {"PT": "Tendências Históricas", "EN": "Historical Trends"},
    "title_heatmap": {"PT": "Mapa de Calor — Indicadores por Província", "EN": "Heatmap — Indicators by Province"},
    "title_forecast": {"PT": "Previsões e Simulação de Crescimento", "EN": "Forecasts & Growth Simulation"},
    "title_decision": {"PT": "Insights Estratégicos e Oportunidades", "EN": "Strategic Insights and Opportunities"},
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
    "txn_category": {"PT": "Categoria de Transacção", "EN": "Transaction Category"},
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
    "stock_label": {"PT": "stock (valor reportado em Dezembro)", "EN": "stock (December reported value)"},
    "flow_label": {"PT": "fluxo (soma anual)", "EN": "flow (annual sum)"},
    # Methodology
    "methodology": {
        "PT": (
            "As previsões são calculadas através de regressão polinomial de grau 2 aplicada à série temporal mensal "
            "de cada indicador. Para indicadores de stock (contas, cartões, ATMs, POS), utiliza-se o valor "
            "reportado em Dezembro; para indicadores de fluxo (transacções), utiliza-se a soma anual. "
            "A banda de confiança a 95% (±1,96σ) reflecte a dispersão dos resíduos do modelo."
        ),
        "EN": (
            "📐 **Methodology** — Forecasts use **degree-2 polynomial regression** on monthly time series. "
            "For *stock* indicators (accounts, cards, ATMs, POS), December reported values are used; "
            "for *flow* indicators (transactions), annual sums are used. "
            "The 95% confidence band (±1.96σ) reflects the dispersion of model residuals."
        ),
    },
    # Forecast page caption
    "forecast_caption": {
        "PT": "ℹ️ Previsões baseadas em regressão polinomial sobre dados mensais, com bandas de confiança. O simulador manual permite testar cenários de crescimento personalizado.",
        "EN": "ℹ️ Forecasts based on polynomial regression over monthly data, with confidence bands. The manual simulator allows testing custom growth scenarios."
    },
    "caption_decision": {
        "PT": "ℹ️ Esta página transforma os indicadores em leituras de priorização territorial, cenários e interpretação por público-alvo.",
        "EN": "ℹ️ This page converts indicators into territorial prioritization, scenario ranges, and audience-focused interpretation."
    },
    # Page captions
    "caption_overview": {
        "PT": "ℹ️ Síntese dos principais sinais e respostas determinísticas com visual dinâmico para leitura rápida.",
        "EN": "ℹ️ Snapshot of key signals plus deterministic Q&A with dynamic chart for fast reading."
    },
    "caption_home": {
        "PT": "ℹ️ Guia rápido sobre dados, metodologia e perguntas que cada página responde.",
        "EN": "ℹ️ Quick guide to data, methodology, and the key question each page answers."
    },
    "caption_ime": {
        "PT": "ℹ️ Rede de carteiras móveis por província e distrito, com foco em subscrições, agentes e transacções por tipo.",
        "EN": "ℹ️ Mobile wallet network by province and district, focused on subscriptions, agents, and transaction types."
    },
    "caption_accounts": {
        "PT": "ℹ️ Detalhes sobre contas bancárias: tendência mensal, distribuição por faixa etária e moeda. Filtrado pelo ano e províncias seleccionadas.",
        "EN": "ℹ️ Bank account details: monthly trend, age distribution, and currency split. Filtered by the selected year and provinces."
    },
    "caption_cards": {
        "PT": "ℹ️ Evolução mensal, distribuição por faixa etária e tipo de cartão (crédito, débito, pré-pago). Filtrado pelo ano e províncias seleccionadas.",
        "EN": "ℹ️ Monthly evolution, age group distribution, and card type (credit, debit, prepaid). Filtered by the selected year and provinces."
    },
    "caption_infra": {
        "PT": "ℹ️ Distribuição geográfica de ATMs e terminais POS. Use os filtros da barra lateral para refinar por zona, província ou distrito.",
        "EN": "ℹ️ Geographic distribution of ATMs and POS terminals. Use sidebar filters to drill down by zone, province or district."
    },
    "caption_digital": {
        "PT": "ℹ️ Seleccione o canal e a métrica para ver a evolução mensal e anual. A comparação directa Mobile vs Internet aparece no primeiro gráfico.",
        "EN": "ℹ️ Select the channel and metric to view monthly and annual trends. The direct Mobile vs Internet comparison appears in the first chart."
    },
    "caption_txn": {
        "PT": "ℹ️ Seleccione o tipo de transacção no menu abaixo para comparar volume (quantidade) e valor (MZN) mensal e anual.",
        "EN": "ℹ️ Select the transaction type below to compare monthly and annual volume (count) and value (MZN)."
    },
    "caption_trends": {
        "PT": "ℹ️ Evolução multi-anual dos principais indicadores. Seleccione o indicador no menu abaixo.",
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
        "PT": "📋 **Fonte demográfica:** IV Recenseamento Geral da População e Habitação, 2017 — Instituto Nacional de Estatística (INE).",
        "EN": "📋 **Demographic source:** IV General Census of Population and Housing, 2017 — National Statistics Institute (INE)."
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
    "currency_distribution": {"PT": "Distribuição de Contas por Moeda", "EN": "Account Distribution by Currency"},
    "product_adoption_age": {"PT": "Adoção de Produto por Idade", "EN": "Product Adoption by Age"},
    "card_type": {"PT": "Tipo de Cartão", "EN": "Card Type"},
    "atm_distribution": {"PT": "Distribuição de ATMs", "EN": "ATM Distribution"},
    "pos_distribution": {"PT": "Distribuição de POS", "EN": "POS Distribution"},
    "num_atms": {"PT": "Número de ATMs", "EN": "Number of ATMs"},
    "num_pos": {"PT": "Número de POS", "EN": "Number of POS"},
    "txn_type": {"PT": "Tipo de Transacção", "EN": "Transaction Type"},
    "help_txn": {"PT": "Escolha entre ATM, POS, Mobile Banking ou Internet Banking.", "EN": "Choose between ATM, POS, Mobile Banking or Internet Banking."},
    "help_comparison": {"PT": "Métricas comuns a ambos os canais.", "EN": "Metrics common to both channels."},
    "help_channel": {"PT": "Escolha o canal para análise detalhada.", "EN": "Choose the channel for detailed analysis."},
    "help_detail_metric": {"PT": "Métrica específica para análise mensal e anual.", "EN": "Specific metric for monthly and annual analysis."},
    "help_indicator": {"PT": "Seleccione o indicador para visualizar.", "EN": "Select the indicator to view."},
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


def translate(lang, key):
    """Return translated string for a given language code."""
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        return key
    if isinstance(entry, dict):
        return entry.get(lang, entry.get("PT", key))
    return entry
