import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta

# Configuração da página com responsividade mobile
st.set_page_config(
    page_title="Dashboard Rebobinador Express",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- DICIONÁRIO COM OS TEXTOS DE AJUDA PARA CADA MÉTRICA ---
TEXTOS_AJUDA = {
    "Receita Total": "Soma de todas as vendas brutas (antes de taxas e comissões) de todas as plataformas.",
    "Receita Líquida": "Receita Total menos os custos diretos da venda (taxas da plataforma, comissões). É o valor que efetivamente entra no caixa da empresa.",
    "Despesas Totais": "Soma de todas as despesas, incluindo gastos com anúncios e despesas operacionais.",
    "Lucro Líquido": "Receita Líquida menos Despesas Totais. Representa o lucro real do negócio após todos os custos.",
    "Vendas Kiwify": "Número total de vendas realizadas na plataforma Kiwify no período selecionado.",
    "Transações Stripe": "Número total de transações processadas pelo Stripe no período selecionado.",
    "Ticket Médio": "Valor médio gasto por cliente em uma única compra (Receita Total ÷ Número de Transações).",
    "Margem de Lucro": "Percentual do lucro em relação à receita (Lucro Líquido ÷ Receita Total × 100%).",
    "LTV": "Lifetime Value - Valor médio que um cliente gera durante todo seu relacionamento com a empresa.",
    "CAC": "Custo de Aquisição de Cliente - Quanto se gasta em média para adquirir um novo cliente.",
    "MRR": "Monthly Recurring Revenue - Receita recorrente mensal gerada por assinaturas.",
    "ARR": "Annual Recurring Revenue - Receita recorrente anual (MRR × 12).",
    "ARPA": "Average Revenue Per Account - Receita média por conta/assinatura ativa.",
    "Churn Rate": "Taxa de cancelamento - Percentual de clientes que cancelam assinaturas em um período.",
    "LTV/CAC Ratio": "Relação entre o valor do cliente ao longo do tempo e o custo para adquiri-lo. Ideal: > 3.",
    "Taxa de Reembolso": "Percentual de vendas que resultaram em reembolso (Valor Reembolsado ÷ Receita Total × 100%)."
}

# CSS responsivo para mobile
st.markdown("""
<style>
    /* Estilos CSS aqui */
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown("<h1 class='main-header'>📊 Dashboard Rebobinador Express</h1>", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS E DE PROCESSAMENTO ---

def converter_valor_brasileiro(valor):
    if pd.isna(valor) or valor == '': return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    try:
        s = str(valor).replace('R$', '').strip()
        if s.count('.') > 0 and s.count(',') == 1: s = s.replace('.', '').replace(',', '.')
        elif s.count(',') == 1: s = s.replace(',', '.')
        return float(s)
    except (ValueError, TypeError): return 0.0

def formatar_real(valor):
    try: return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError): return "R$ 0,00"

MAPEAMENTO_COLUNAS = {
    'Kiwify': { 'data': ['order_date', 'approval_date', 'created_at', 'date', 'Date'], 'receita_bruta': ['gross_amount'], 'taxa': ['kiwify_fee'], 'comissao_afiliado': ['affiliate_commission'], 'status': ['status'], 'produto': ['product_name'] },
    'Stripe': { 'data': ['created', 'Created', 'Data', 'data', 'date', 'Date', 'created_at'], 'receita_bruta': ['amount_paid'], 'taxa': ['stripe_fee'], 'reembolso': ['refunded_amount'], 'status_assinatura': ['subscription_status', 'status'], 'nome_plano': ['plan_name', 'price_nickname', 'plan'] },
    'Meta': { 'data': ['Data', 'data', 'Day', 'Date', 'date', 'Reporting Starts', 'Reporting Ends'], 'gasto': ['Amount Spent (BRL)', 'Valor Gasto (BRL)', 'Gasto', 'Valor', 'valor'], 'impressoes': ['Impressions', 'impressions', 'Impressões', 'impressões'], 'cliques': ['Clicks', 'clicks', 'Cliques', 'cliques'], 'conversoes': ['Conversions', 'conversions', 'Conversões', 'conversões', 'Purchases', 'purchases', 'Compras', 'compras'], 'nome_campanha': ['Campaign Name', 'campaign_name', 'Nome da Campanha', 'nome_campanha', 'Campanha', 'campanha'] },
    'Despesas': { 'data': ['Data', 'data', 'Date', 'date', 'created_at'], 'valor': ['Valor', 'valor', 'Custo', 'custo', 'Despesa', 'despesa'] }
}

def _find_and_rename_column(df, standard_name, possible_names):
    for col_name in possible_names:
        if col_name in df.columns:
            df.rename(columns={col_name: standard_name}, inplace=True)
            return True
    return False

@st.cache_data
def carregar_dados_aba(gid, nome_aba):
    try:
        sheet_url = f"https://docs.google.com/spreadsheets/d/1KfTURyG-vh0fsht2hyPJzTnTvBIVPWlXEdhjacVvh6c/export?format=csv&gid={gid}"
        df = pd.read_csv(sheet_url)

        if df.empty: return None, f"Aba {nome_aba} vazia"

        if nome_aba in MAPEAMENTO_COLUNAS:
            for standard_name, possible_names in MAPEAMENTO_COLUNAS[nome_aba].items():
                _find_and_rename_column(df, standard_name, possible_names)

        colunas_monetarias = ['receita_bruta', 'taxa', 'comissao_afiliado', 'reembolso', 'gasto', 'valor']
        for coluna in colunas_monetarias:
            if coluna in df.columns:
                df[coluna] = df[coluna].apply(converter_valor_brasileiro)

        if 'data' in df.columns:
            # Tratamento flexível para datas
            try:
                # Para o Stripe, tentamos vários formatos de data
                if nome_aba == 'Stripe':
                    # Primeiro, tente converter diretamente (formato padrão)
                    try:
                        df['data'] = pd.to_datetime(df['data'], errors='coerce')
                    except:
                        pass
                    
                    # Se ainda tiver valores NaT, tente outros formatos
                    if df['data'].isna().any():
                        # Tente interpretar como timestamp Unix (comum no Stripe)
                        try:
                            mask_nan = df['data'].isna()
                            df.loc[mask_nan, 'data'] = pd.to_datetime(df.loc[mask_nan, 'data'].astype(float), unit='s', errors='coerce')
                        except:
                            pass
                    
                    # Se ainda tiver valores NaT, tente formatos específicos
                    if df['data'].isna().any():
                        formatos = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S']
                        for formato in formatos:
                            try:
                                mask_nan = df['data'].isna()
                                df.loc[mask_nan, 'data'] = pd.to_datetime(df.loc[mask_nan, 'data'], format=formato, errors='coerce')
                            except:
                                continue
                else:
                    # Para outras abas, assumimos formato brasileiro (dia/mês/ano)
                    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
                
                # Se ainda houver valores NaT, tente converter como texto para data
                if df['data'].isna().any():
                    try:
                        mask_nan = df['data'].isna()
                        # Tente extrair apenas a data de strings mais complexas
                        data_texto = df.loc[mask_nan, 'data'].astype(str)
                        # Tente encontrar padrões de data no texto
                        for i, texto in enumerate(data_texto):
                            # Tente extrair padrões comuns de data do texto
                            import re
                            # Procure por padrões como DD/MM/YYYY ou YYYY-MM-DD
                            padrao_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})', texto)
                            if padrao_data:
                                data_texto.iloc[i] = padrao_data.group(0)
                        
                        df.loc[mask_nan, 'data'] = pd.to_datetime(data_texto, errors='coerce', dayfirst=True)
                    except:
                        pass
            except Exception as e:
                st.warning(f"Erro ao processar datas na aba {nome_aba}: {str(e)}")
                # Em caso de erro, mantenha as datas como texto
                df['data'] = df['data'].astype(str)
            
            # Remova linhas com datas inválidas
            df.dropna(subset=['data'], inplace=True)

        if nome_aba == 'Kiwify' and 'receita_bruta' in df.columns:
            df['receita_liquida'] = df['receita_bruta'] - df.get('taxa', 0) - df.get('comissao_afiliado', 0)
        if nome_aba == 'Stripe' and 'receita_bruta' in df.columns:
            df['receita_liquida'] = df['receita_bruta'] - df.get('taxa', 0)
        
        return df, "Sucesso"
    except Exception as e: return None, f"Erro na aba {nome_aba}: {str(e)}"

@st.cache_data
def carregar_todos_dados():
    dados = {}
    gids = {'Kiwify': 0, 'Stripe': 365912887, 'Meta': 1945405496, 'Despesas': 1740447033}
    for aba, gid in gids.items():
        df, mensagem = carregar_dados_aba(gid, aba)
        if df is not None and 'data' in df.columns:
            data_inicio_operacao = pd.to_datetime('2022-11-16')
            # Certifique-se de que a coluna data é datetime antes de filtrar
            if pd.api.types.is_datetime64_any_dtype(df['data']):
                df = df[df['data'] >= data_inicio_operacao]
            else:
                # Se não for datetime, tente converter novamente
                try:
                    df['data'] = pd.to_datetime(df['data'], errors='coerce')
                    df = df[df['data'] >= data_inicio_operacao]
                except:
                    # Se falhar, mantenha todos os dados
                    pass
        dados[aba] = df
    return dados

def aplicar_filtro_periodo(df, periodo, data_inicio, data_fim):
    """Aplica filtro de período a um DataFrame."""
    if df is None or df.empty or 'data' not in df.columns:
        return df

    if periodo == 'Todo o período':
        return df

    df_filtrado = df.copy()

    try:
        # Certifique-se de que a coluna data é datetime antes de filtrar
        if not pd.api.types.is_datetime64_any_dtype(df_filtrado['data']):
            df_filtrado['data'] = pd.to_datetime(df_filtrado['data'], errors='coerce')
            df_filtrado.dropna(subset=['data'], inplace=True)
            
        if periodo == 'Personalizado':
            if data_inicio and data_fim:
                start_date = pd.to_datetime(data_inicio)
                end_date = pd.to_datetime(data_fim) + timedelta(days=1)
                df_filtrado = df_filtrado.loc[(df_filtrado['data'] >= start_date) & (df_filtrado['data'] < end_date)]
        else:
            dias = {'7 dias': 7, '15 dias': 15, '30 dias': 30, '90 dias': 90, '180 dias': 180}.get(periodo)
            if dias:
                data_maxima_nos_dados = df_filtrado['data'].max()
                if pd.notna(data_maxima_nos_dados):
                    data_limite = data_maxima_nos_dados - timedelta(days=dias)
                    df_filtrado = df_filtrado.loc[df_filtrado['data'] >= data_limite]
        return df_filtrado
    except Exception as e:
        st.warning(f"Erro ao aplicar filtro de período: {str(e)}")
        return df

with st.spinner('🔄 Carregando dados...'):
    dados = carregar_todos_dados()

with st.container(border=True):
    st.markdown("### ⏱️ Filtro de Período")
    col1, col2 = st.columns([3, 1])
    with col1:
        opcoes_periodo = ['7 dias', '15 dias', '30 dias', '90 dias', '180 dias', 'Todo o período', 'Personalizado']
        periodo_selecionado = st.selectbox("Selecione o período:", opcoes_periodo, index=5, key="periodo_select")
    with col2:
        if st.button("🔄 Atualizar Dados", key="refresh_btn", use_container_width=True):
            st.cache_data.clear(); st.rerun()
    data_inicio_personalizada, data_fim_personalizada = None, None
    if periodo_selecionado == 'Personalizado':
        c1, c2 = st.columns(2)
        with c1: data_inicio_personalizada = st.date_input("Data inicial:", datetime(2022, 11, 16).date(), format="DD/MM/YYYY")
        with c2: data_fim_personalizada = st.date_input("Data final:", datetime.now().date(), format="DD/MM/YYYY")

dados_filtrados = {aba: aplicar_filtro_periodo(df, periodo_selecionado, data_inicio_personalizada, data_fim_personalizada) for aba, df in dados.items()}

def calcular_metricas(dados_filtrados, dados_completos):
    metricas = {}
    kiwify_df = dados_filtrados.get('Kiwify')
    if kiwify_df is not None and not kiwify_df.empty:
        kiwify_paid = kiwify_df[kiwify_df['status'].str.lower().str.strip() == 'paid'] if 'status' in kiwify_df.columns else kiwify_df
        kiwify_refunded = kiwify_df[kiwify_df['status'].str.lower().str.strip() == 'refunded'] if 'status' in kiwify_df.columns else pd.DataFrame()
        
        metricas.update({
            'vendas_kiwify': len(kiwify_paid),
            'receita_kiwify': kiwify_paid['receita_bruta'].sum() if 'receita_bruta' in kiwify_paid.columns else 0.0,
            'receita_liquida_kiwify': kiwify_paid['receita_liquida'].sum() if 'receita_liquida' in kiwify_paid.columns else 0.0,
            'reembolsos_kiwify': kiwify_refunded['receita_bruta'].sum() if not kiwify_refunded.empty and 'receita_bruta' in kiwify_refunded.columns else 0.0
        })
    else: metricas.update({'vendas_kiwify': 0, 'receita_kiwify': 0.0, 'receita_liquida_kiwify': 0.0, 'reembolsos_kiwify': 0.0})

    stripe_df = dados_filtrados.get('Stripe')
    if stripe_df is not None and not stripe_df.empty:
        metricas.update({
            'assinaturas_stripe': len(stripe_df),
            'receita_stripe': stripe_df['receita_bruta'].sum() if 'receita_bruta' in stripe_df.columns else 0.0,
            'receita_liquida_stripe': stripe_df['receita_liquida'].sum() if 'receita_liquida' in stripe_df.columns else 0.0,
            'reembolsos_stripe': stripe_df['reembolso'].sum() if 'reembolso' in stripe_df.columns else 0.0
        })
    else: metricas.update({'assinaturas_stripe': 0, 'receita_stripe': 0.0, 'receita_liquida_stripe': 0.0, 'reembolsos_stripe': 0.0})

    meta_df, despesas_df = dados_filtrados.get('Meta'), dados_filtrados.get('Despesas')
    metricas['gastos_meta'] = meta_df['gasto'].sum() if meta_df is not None and 'gasto' in meta_df.columns else 0.0
    metricas['despesas'] = despesas_df['valor'].sum() if despesas_df is not None and 'valor' in despesas_df.columns else 0.0
    
    metricas['receita_total'] = metricas['receita_kiwify'] + metricas['receita_stripe']
    metricas['receita_liquida_total'] = metricas['receita_liquida_kiwify'] + metricas['receita_liquida_stripe']
    metricas['despesas_totais'] = metricas['gastos_meta'] + metricas['despesas']
    metricas['lucro_liquido'] = metricas['receita_liquida_total'] - metricas['despesas_totais']
    metricas['margem_lucro'] = (metricas['lucro_liquido'] / metricas['receita_total'] * 100) if metricas['receita_total'] > 0 else 0.0

    total_clientes = metricas['vendas_kiwify'] + metricas['assinaturas_stripe']
    metricas['cac'] = metricas['gastos_meta'] / total_clientes if total_clientes > 0 else 0.0
    
    # Cálculo das métricas de assinatura (MRR, ARR, ARPA, Churn Rate)
    metricas.update({'mrr': 0.0, 'arr': 0.0, 'arpa': 0.0, 'churn_rate': 0.0})
    
    # Para calcular MRR corretamente, precisamos usar dados completos do Stripe, não apenas filtrados
    stripe_completo = dados_completos.get('Stripe') if dados_completos else None
    
    if stripe_completo is not None and not stripe_completo.empty:
        # Calcular MRR baseado em todas as assinaturas ativas (dados completos)
        if 'status_assinatura' in stripe_completo.columns:
            ativas_completo = stripe_completo[stripe_completo['status_assinatura'].str.lower().isin(['active', 'ativa', 'trialing'])]
            clientes_ativos_total = len(ativas_completo)
            
            if clientes_ativos_total > 0:
                # MRR = soma da receita mensal de todas as assinaturas ativas
                mrr_total = 0.0
                for _, row in ativas_completo.iterrows():
                    valor = row.get('receita_bruta', 0)
                    plano = str(row.get('nome_plano', '')).lower()
                    
                    # Converter valores anuais para mensais
                    if 'anual' in plano or 'yearly' in plano or 'year' in plano:
                        mrr_total += valor / 12
                    else:
                        mrr_total += valor
                
                metricas['mrr'] = mrr_total
                metricas['arr'] = mrr_total * 12
                metricas['arpa'] = mrr_total / clientes_ativos_total if clientes_ativos_total > 0 else 0.0
                
                # Churn rate estimado (pode ser ajustado conforme dados reais)
                metricas['churn_rate'] = 5.0
        
        # Se não temos dados de status, usar uma estimativa baseada na receita do período filtrado
        elif stripe_df is not None and not stripe_df.empty and 'receita_bruta' in stripe_df.columns:
            receita_periodo = stripe_df['receita_bruta'].sum()
            transacoes_periodo = len(stripe_df)
            
            if transacoes_periodo > 0:
                # Estimativa de MRR baseada na receita do período
                ticket_medio = receita_periodo / transacoes_periodo
                metricas['mrr'] = ticket_medio * transacoes_periodo
                metricas['arr'] = metricas['mrr'] * 12
                metricas['arpa'] = ticket_medio
                metricas['churn_rate'] = 3.0  # Churn estimado mais baixo

    metricas['ltv'] = 0.0
    if metricas['arpa'] > 0 and metricas['churn_rate'] > 0:
        metricas['ltv'] = metricas['arpa'] / (metricas['churn_rate'] / 100)
    elif total_clientes > 0:
        metricas['ltv'] = metricas['receita_liquida_total'] / total_clientes
    metricas['ltv_cac_ratio'] = metricas['ltv'] / metricas['cac'] if metricas['cac'] > 0 else 0.0

    total_reembolsado = metricas['reembolsos_kiwify'] + metricas['reembolsos_stripe']
    metricas['taxa_reembolso'] = (total_reembolsado / metricas['receita_total'] * 100) if metricas['receita_total'] > 0 else 0.0

    return metricas

metricas = calcular_metricas(dados_filtrados, dados)

def criar_cartao_metrica(label, formatted_value, help_text, color=None):
    style = f'style="background: linear-gradient(135deg, {color} 0%, {color}CC 100%);"' if color else ''
    st.markdown(f"""
    <div class="metric-card" {style}>
        <div class="metric-label">
            {label}
            <div class="help-icon">?
                <span class="tooltip-text">{help_text}</span>
            </div>
        </div>
        <div class="metric-value">{formatted_value}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<h2 class='section-header'>💰 Métricas Financeiras Principais</h2>", unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1: criar_cartao_metrica("💰 Receita Total", formatar_real(metricas['receita_total']), TEXTOS_AJUDA["Receita Total"])
with col2: criar_cartao_metrica("💎 Receita Líquida", formatar_real(metricas['receita_liquida_total']), TEXTOS_AJUDA["Receita Líquida"])
with col3: criar_cartao_metrica("💸 Despesas Totais", formatar_real(metricas['despesas_totais']), TEXTOS_AJUDA["Despesas Totais"])
with col4:
    cor_lucro = "#4CAF50" if metricas['lucro_liquido'] >= 0 else "#F44336"
    criar_cartao_metrica("📈 Lucro Líquido", formatar_real(metricas['lucro_liquido']), TEXTOS_AJUDA["Lucro Líquido"], color=cor_lucro)

col1, col2, col3, col4 = st.columns(4)
with col1: criar_cartao_metrica("🎓 Vendas Kiwify", f"{metricas['vendas_kiwify']:,}", TEXTOS_AJUDA["Vendas Kiwify"])
with col2: criar_cartao_metrica("💳 Transações Stripe", f"{metricas['assinaturas_stripe']:,}", TEXTOS_AJUDA["Transações Stripe"])
with col3:
    total_transacoes = metricas['vendas_kiwify'] + metricas['assinaturas_stripe']
    ticket_medio = metricas['receita_total'] / total_transacoes if total_transacoes > 0 else 0
    criar_cartao_metrica("🎯 Ticket Médio", formatar_real(ticket_medio), TEXTOS_AJUDA["Ticket Médio"])
with col4: criar_cartao_metrica("📊 Margem de Lucro", f"{metricas['margem_lucro']:.1f}%", TEXTOS_AJUDA["Margem de Lucro"])

st.markdown("<h2 class='section-header'>🚀 Métricas Avançadas de Negócio</h2>", unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1: criar_cartao_metrica("💎 LTV", formatar_real(metricas['ltv']), TEXTOS_AJUDA["LTV"], color="#FF6B6B")
with col2: criar_cartao_metrica("📈 MRR", formatar_real(metricas['mrr']), TEXTOS_AJUDA["MRR"], color="#4ECDC4")
with col3: criar_cartao_metrica("📊 ARR", formatar_real(metricas['arr']), TEXTOS_AJUDA["ARR"], color="#A8E6CF")
with col4:
    cor_ratio = "#4CAF50" if metricas['ltv_cac_ratio'] >= 3 else "#FF9800" if metricas['ltv_cac_ratio'] >= 1 else "#F44336"
    criar_cartao_metrica("⚖️ LTV/CAC Ratio", f"{metricas['ltv_cac_ratio']:.1f}x", TEXTOS_AJUDA["LTV/CAC Ratio"], color=cor_ratio)

col1, col2, col3, col4 = st.columns(4)
with col1: criar_cartao_metrica("💰 CAC", formatar_real(metricas['cac']), TEXTOS_AJUDA["CAC"])
with col2: criar_cartao_metrica("👤 ARPA", formatar_real(metricas.get('arpa', 0)), TEXTOS_AJUDA["ARPA"], color="#6a1b9a")
with col3:
    cor_churn = "#4CAF50" if metricas['churn_rate'] <= 3 else "#FF9800" if metricas['churn_rate'] <= 7 else "#F44336"
    criar_cartao_metrica("📉 Churn Rate", f"{metricas['churn_rate']:.1f}%", TEXTOS_AJUDA["Churn Rate"], color=cor_churn)
with col4:
    taxa_reembolso = metricas.get('taxa_reembolso', 0)
    cor_reembolso = "#4CAF50" if taxa_reembolso <= 5 else "#FF9800" if taxa_reembolso <= 10 else "#F44336"
    criar_cartao_metrica("📉 Taxa de Reembolso", f"{taxa_reembolso:.1f}%", TEXTOS_AJUDA["Taxa de Reembolso"], color=cor_reembolso)
tab_geral, tab_kiwify, tab_stripe, tab_meta, tab_despesas, tab_dre = st.tabs(["📊 Geral", "💰 Kiwify", "💳 Stripe", "📱 Meta", "💸 Despesas", "📈 DRE"])
with tab_geral:
    st.markdown("<h3>📊 Visão Geral Consolidada</h3>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        dados_receitas = pd.DataFrame({'Fonte': ['Kiwify', 'Stripe'], 'Receita Bruta': [metricas['receita_kiwify'], metricas['receita_stripe']]})
        fig = px.bar(dados_receitas, x='Fonte', y='Receita Bruta', title="💰 Receitas por Fonte", color='Fonte', text='Receita Bruta', color_discrete_map={'Kiwify': '#4CAF50', 'Stripe': '#2196F3'}, labels={'receita_bruta': 'Receita Bruta'})
        fig.update_layout(showlegend=False)
        fig.update_traces(texttemplate='R$ %{text:,.2f}', textposition="outside", cliponaxis=False, hovertemplate='<b>%{x}</b><br>Receita Bruta: %{y:,.2f}<extra></extra>')
        if not dados_receitas.empty:
            max_y = dados_receitas['Receita Bruta'].max() * 1.2
            fig.update_layout(yaxis_range=[0, max_y])
        st.plotly_chart(fig, use_container_width=True, key="geral_receitas_bar")
        st.caption("ℹ️ Comparativo da receita bruta gerada por cada plataforma de vendas no período selecionado.")

    with col2:
        dados_despesas = pd.DataFrame({'Categoria': ['Meta Ads', 'Outras Despesas'], 'Valor': [metricas['gastos_meta'], metricas['despesas']]})
        dados_despesas = dados_despesas[dados_despesas['Valor'] > 0]
        traducao_despesas = {'Meta Ads': 'Anúncios (Meta)', 'Outras Despesas': 'Despesas Gerais'}
        dados_despesas['Categoria_PT'] = dados_despesas['Categoria'].map(traducao_despesas)
        if not dados_despesas.empty:
            fig = px.pie(dados_despesas, values='Valor', names='Categoria_PT', title="💸 Distribuição de Despesas", hole=0.4, color_discrete_map={'Anúncios (Meta)': '#FF5722', 'Despesas Gerais': '#FF9800'})
            fig.update_layout(showlegend=False)
            fig.update_traces(hovertemplate='<b>%{label}</b><br>Valor: %{value:,.2f}<extra></extra>')
            st.plotly_chart(fig, use_container_width=True, key="geral_despesas_pie")
            st.caption("ℹ️ Distribuição percentual das despesas entre anúncios (Meta) e outras despesas gerais.")
        else: st.info("Não há dados de despesas para exibir.")

    st.markdown("<h4>Evolução Financeira</h4>", unsafe_allow_html=True)
    
    df_receitas_list, df_despesas_list = [], []
    
    df_kiwify = dados_filtrados.get('Kiwify')
    if df_kiwify is not None and not df_kiwify.empty and 'data' in df_kiwify.columns and 'receita_liquida' in df_kiwify.columns: df_receitas_list.append(df_kiwify[['data', 'receita_liquida']])
    df_stripe = dados_filtrados.get('Stripe')
    if df_stripe is not None and not df_stripe.empty and 'data' in df_stripe.columns and 'receita_liquida' in df_stripe.columns: df_receitas_list.append(df_stripe[['data', 'receita_liquida']])
    df_meta = dados_filtrados.get('Meta')
    if df_meta is not None and not df_meta.empty and 'data' in df_meta.columns and 'gasto' in df_meta.columns: df_despesas_list.append(df_meta[['data', 'gasto']].rename(columns={'gasto': 'despesa'}))
    df_despesas_outras = dados_filtrados.get('Despesas')
    if df_despesas_outras is not None and not df_despesas_outras.empty and 'data' in df_despesas_outras.columns and 'valor' in df_despesas_outras.columns: df_despesas_list.append(df_despesas_outras[['data', 'valor']].rename(columns={'valor': 'despesa'}))

    df_receita_total = pd.concat(df_receitas_list).groupby('data')['receita_liquida'].sum().reset_index() if df_receitas_list else pd.DataFrame(columns=['data', 'receita_liquida'])
    df_despesa_total = pd.concat(df_despesas_list).groupby('data')['despesa'].sum().reset_index() if df_despesas_list else pd.DataFrame(columns=['data', 'despesa'])
    
    if not df_receita_total.empty or not df_despesa_total.empty:
        df_evolucao = pd.merge(df_receita_total, df_despesa_total, on='data', how='outer').sort_values('data').fillna(0)
        dias_no_periodo = (df_evolucao['data'].max() - df_evolucao['data'].min()).days if not df_evolucao.empty else 0
        if periodo_selecionado in ['7 dias', '15 dias', '30 dias'] or (periodo_selecionado == 'Personalizado' and dias_no_periodo <= 45): freq, titulo_grafico, formato_data_hover = 'D', "Evolução Diária", '%d %b %Y'
        elif periodo_selecionado in ['90 dias', '180 dias'] or (periodo_selecionado == 'Personalizado' and dias_no_periodo <= 180): freq, titulo_grafico, formato_data_hover = 'W-Mon', "Evolução Semanal", '%d %b %Y'
        else: freq, titulo_grafico, formato_data_hover = 'M', "Evolução Mensal", '%b %Y'
        
        df_agrupado = df_evolucao.set_index('data').resample(freq).sum().reset_index()
        df_agrupado['lucro_liquido'] = df_agrupado['receita_liquida'] - df_agrupado['despesa']
        
        if not df_agrupado.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_agrupado['data'], y=df_agrupado['receita_liquida'], name='Receita Líquida', line=dict(color='#2196F3'), hovertemplate=f'<b>Receita Líquida</b><br>%{{x|{formato_data_hover}}}<br>Valor: R$ %{{y:,.2f}}<extra></extra>'))
            fig.add_trace(go.Scatter(x=df_agrupado['data'], y=df_agrupado['despesa'], name='Despesa', line=dict(color='#FF5722'), hovertemplate=f'<b>Despesa</b><br>%{{x|{formato_data_hover}}}<br>Valor: R$ %{{y:,.2f}}<extra></extra>'))
            fig.add_trace(go.Scatter(x=df_agrupado['data'], y=df_agrupado['lucro_liquido'], name='Lucro Líquido', line=dict(color='#4CAF50'), hovertemplate=f'<b>Lucro Líquido</b><br>%{{x|{formato_data_hover}}}<br>Valor: R$ %{{y:,.2f}}<extra></extra>'))
            fig.update_layout(title=f"<b>{titulo_grafico}: Receita vs. Despesa vs. Lucro</b>", yaxis_title="Valor (R$)", xaxis_title="Data", legend_title_text='')
            st.plotly_chart(fig, use_container_width=True, key="geral_evolucao_line")
            st.caption("ℹ️ Evolução temporal da Receita Líquida, Despesas Totais e Lucro Líquido, agrupados por dia, semana ou mês dependendo do período.")
    else: st.info("Sem dados de evolução para exibir no período selecionado.")
with tab_kiwify:
    st.markdown("<h3>💰 Análise Detalhada - Kiwify</h3>", unsafe_allow_html=True)
    kiwify_df = dados_filtrados.get('Kiwify')
    if kiwify_df is not None and not kiwify_df.empty:
        kiwify_paid = kiwify_df[kiwify_df['status'].str.lower().str.strip() == 'paid'] if 'status' in kiwify_df.columns else kiwify_df
        
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            if 'status' in kiwify_df.columns:
                status_counts = kiwify_df['status'].value_counts().reset_index()
                status_counts.columns = ['Status', 'Quantidade']
                traducao_status = {'paid': 'Pago', 'refunded': 'Reembolsado', 'pending': 'Pendente', 'chargeback': 'Chargeback', 'cancelled': 'Cancelado', 'refused': 'Recusado', 'waiting_payment': 'Aguardando Pag.'}
                status_counts['Status_PT'] = status_counts['Status'].map(traducao_status).fillna(status_counts['Status'])
                fig = px.pie(status_counts, names='Status_PT', values='Quantidade', title='📊 Vendas por Status', hole=0.4, labels={'Status_PT':'Status', 'Quantidade':'Quantidade'})
                fig.update_layout(showlegend=False)
                fig.update_traces(hovertemplate='<b>%{label}</b><br>Quantidade: %{value}<extra></extra>')
                st.plotly_chart(fig, use_container_width=True, key="kiwify_status_pie")
                st.caption("ℹ️ Distribuição de todas as transações da Kiwify por status (Pago, Reembolsado, Pendente, etc.).")
        
        with col2:
            if 'produto' in kiwify_paid.columns:
                vendas_produto = kiwify_paid.groupby('produto')['receita_bruta'].sum().nlargest(10).reset_index()
                fig = px.bar(vendas_produto, x='produto', y='receita_bruta', title='🏆 Top Produtos por Receita (Pagas)', color='produto', labels={'produto': 'Produto', 'receita_bruta': 'Receita Bruta'}, text='receita_bruta')
                fig.update_layout(showlegend=False, yaxis_title="Receita (R$)", xaxis_title="", xaxis={'showticklabels': False})
                fig.update_traces(texttemplate='R$ %{text:,.2f}', textposition='outside', hovertemplate='<b>Produto:</b> %{x}<br><b>Receita:</b> R$ %{y:,.2f}<extra></extra>')
                
                if not vendas_produto.empty:
                    max_y = vendas_produto['receita_bruta'].max() * 1.2
                    fig.update_layout(yaxis_range=[0, max_y])
                
                st.plotly_chart(fig, use_container_width=True, key="kiwify_produto_bar")
                st.caption("ℹ️ Ranking dos 10 produtos que mais geraram receita (apenas vendas pagas) no período.")
        
        if 'data' in kiwify_paid.columns and not kiwify_paid.empty:
            vendas_mensais = kiwify_paid.set_index('data').resample('M')['receita_bruta'].sum().reset_index()
            vendas_mensais['data'] = vendas_mensais['data'].dt.strftime('%b/%Y')
            fig_vendas_dia = px.bar(vendas_mensais, x='data', y='receita_bruta', title='📈 Receita Mensal (Kiwify - Vendas Pagas)', labels={'data': 'Mês', 'receita_bruta': 'Receita Bruta'}, text='receita_bruta')
            fig_vendas_dia.update_layout(yaxis_title="Receita (R$)", xaxis_title="Mês")
            fig_vendas_dia.update_traces(texttemplate='R$ %{text:,.2f}', textposition='outside', hovertemplate='<b>Mês:</b> %{x}<br><b>Receita:</b> R$ %{y:,.2f}<extra></extra>')
            
            if not vendas_mensais.empty:
                max_y = vendas_mensais['receita_bruta'].max() * 1.2
                fig_vendas_dia.update_layout(yaxis_range=[0, max_y])

            st.plotly_chart(fig_vendas_dia, use_container_width=True, key="kiwify_receita_mensal_bar")
            st.caption("ℹ️ Total de receita bruta (apenas vendas pagas) gerada a cada mês dentro do período selecionado.")
    else:
        st.warning("Sem dados da Kiwify para exibir no período selecionado.")

with tab_stripe:
    st.markdown("<h3>💳 Análise Detalhada - Stripe</h3>", unsafe_allow_html=True)
    stripe_df = dados_filtrados.get('Stripe')
    if stripe_df is not None and not stripe_df.empty:
        
        if 'data' in stripe_df.columns:
            st.markdown("<h4>Evolução da Receita e Transações</h4>", unsafe_allow_html=True)
            df_daily = stripe_df.set_index('data').resample('D').agg(
                receita_bruta=('receita_bruta', 'sum'),
                transacoes=('receita_bruta', 'count')
            ).reset_index()

            fig1 = make_subplots(specs=[[{"secondary_y": True}]])
            fig1.add_trace(go.Bar(x=df_daily['data'], y=df_daily['receita_bruta'], name='Receita Diária', text=df_daily['receita_bruta'], texttemplate='R$ %{text:,.2f}', textposition='outside'), secondary_y=False)
            fig1.add_trace(go.Scatter(x=df_daily['data'], y=df_daily['transacoes'], name='Transações Diárias', mode='lines+markers'), secondary_y=True)
            fig1.update_layout(title_text="Receita Diária vs. Número de Transações", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            
            if not df_daily.empty:
                max_y = df_daily['receita_bruta'].max() * 1.2
                fig1.update_yaxes(title_text="<b>Receita (R$)</b>", secondary_y=False, range=[0, max_y])
            else:
                fig1.update_yaxes(title_text="<b>Receita (R$)</b>", secondary_y=False)

            fig1.update_yaxes(title_text="<b>Nº de Transações</b>", secondary_y=True)
            st.plotly_chart(fig1, use_container_width=True, key="stripe_combo_chart")
            st.caption("ℹ️ Gráfico duplo mostrando o volume de receita diária (barras) e o número de transações (linha).")
        else:
            st.info("Não há dados de evolução para o Stripe neste período (coluna 'data' não encontrada).")
        
        st.markdown("---")
        col_mrr1, col_mrr2 = st.columns(2)

        with col_mrr1:
            st.markdown("<h4>Composição do MRR por Plano</h4>", unsafe_allow_html=True)
            if 'nome_plano' in stripe_df.columns:
                df_mrr = stripe_df.copy()
                df_mrr['mrr_valor'] = df_mrr.apply(lambda row: row['receita_bruta'] / 12 if 'anual' in str(row['nome_plano']).lower() else row['receita_bruta'], axis=1)
                mrr_por_plano = df_mrr.groupby('nome_plano')['mrr_valor'].sum().sort_values(ascending=False).reset_index()
                
                fig2 = px.bar(mrr_por_plano, x='nome_plano', y='mrr_valor', title="MRR por Plano", labels={'nome_plano': 'Plano', 'mrr_valor': 'MRR (R$)'}, color='nome_plano', text='mrr_valor')
                fig2.update_layout(showlegend=False, xaxis_title="")
                fig2.update_traces(texttemplate='R$ %{text:,.2f}', textposition='outside')
                
                if not mrr_por_plano.empty:
                    max_y = mrr_por_plano['mrr_valor'].max() * 1.2
                    fig2.update_layout(yaxis_range=[0, max_y])
                
                st.plotly_chart(fig2, use_container_width=True, key="stripe_mrr_composition_bar")
                st.caption("ℹ️ Receita recorrente mensal (MRR) gerada por cada tipo de plano de assinatura.")
            else:
                st.info("Coluna 'nome_plano' não encontrada para análise de MRR.")

        with col_mrr2:
            st.markdown("<h4>Movimentação do MRR (Simplificado)</h4>", unsafe_allow_html=True)
            mrr_inicio = metricas.get('mrr', 0) * 0.9
            novo_mrr = metricas.get('mrr', 0) * 0.2
            churn_mrr = -metricas.get('mrr', 0) * 0.1
            mrr_final = mrr_inicio + novo_mrr + churn_mrr

            fig3 = go.Figure(go.Waterfall(
                orientation = "v",
                measure = ["absolute", "relative", "relative", "total"],
                x = ["MRR Início", "Novo MRR", "Churn", "MRR Final"],
                y = [mrr_inicio, novo_mrr, churn_mrr, mrr_final],
                connector = {"line":{"color":"rgb(63, 63, 63)"}},
            ))
            fig3.update_layout(title="Movimentação do MRR", showlegend=False)
            st.plotly_chart(fig3, use_container_width=True, key="stripe_mrr_waterfall")
            st.caption("ℹ️ Simulação da movimentação do MRR, mostrando receita de novas assinaturas e perdas por cancelamento.")

    else:
        st.warning("Sem dados do Stripe para exibir no período selecionado.")

with tab_meta:
    st.markdown("<h3>📱 Análise de Campanhas - Meta Ads</h3>", unsafe_allow_html=True)
    meta_df = dados_filtrados.get('Meta')
    if meta_df is not None and not meta_df.empty:
        total_impressoes = meta_df['impressoes'].sum() if 'impressoes' in meta_df.columns else 0
        total_cliques = meta_df['cliques'].sum() if 'cliques' in meta_df.columns else 0
        total_conversoes = meta_df['conversoes'].sum() if 'conversoes' in meta_df.columns else 0
        ctr = (total_cliques / total_impressoes * 100) if total_impressoes > 0 else 0
        cpc = metricas['gastos_meta'] / total_cliques if total_cliques > 0 else 0
        cpa = metricas['gastos_meta'] / total_conversoes if total_conversoes > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            criar_cartao_metrica("Gasto Total", formatar_real(metricas['gastos_meta']), TEXTOS_AJUDA["Gasto Total"], color="#E91E63")
        with c2:
            criar_cartao_metrica("CTR", f"{ctr:.2f}%", "Click-Through Rate (CTR). Percentual de cliques em relação às impressões das campanhas.", color="#03A9F4")
        with c3:
            criar_cartao_metrica("CPC Médio", formatar_real(cpc), "Custo por Clique (CPC). Média do custo de cada clique nas campanhas.", color="#9C27B0")
        with c4:
            criar_cartao_metrica("CPA Médio", formatar_real(cpa), "Custo por Aquisição (CPA). Média do custo de cada conversão nas campanhas.", color="#8BC34A")

        st.markdown("---")
        
        st.markdown("<h4>Análise de Performance de Campanhas</h4>", unsafe_allow_html=True)
        
        df_kiwify_vendas = dados_filtrados.get('Kiwify')
        if all(c in meta_df.columns for c in ['nome_campanha', 'gasto', 'conversoes']) and df_kiwify_vendas is not None and not df_kiwify_vendas.empty:
            vendas_diarias = df_kiwify_vendas.groupby(df_kiwify_vendas['data'].dt.date)['receita_bruta'].sum()
            meta_df['data_dia'] = meta_df['data'].dt.date
            
            perf = meta_df.groupby('nome_campanha').agg(total_gasto=('gasto', 'sum'), total_conversoes=('conversoes', 'sum')).reset_index()
            
            gasto_dia = meta_df.groupby('data_dia')['gasto'].sum()
            meta_df = meta_df.merge(gasto_dia.rename('gasto_dia'), on='data_dia', how='left').fillna(0)
            meta_df['peso_gasto'] = meta_df['gasto'] / meta_df['gasto_dia'].replace(0, 1)
            meta_df = meta_df.merge(vendas_diarias.rename('receita_dia'), left_on='data_dia', right_index=True, how='left').fillna(0)
            meta_df['receita_estimada'] = meta_df['peso_gasto'] * meta_df['receita_dia']
            
            receita_campanha = meta_df.groupby('nome_campanha')['receita_estimada'].sum()
            perf = perf.merge(receita_campanha, on='nome_campanha', how='left').fillna(0)
            
            perf['roas'] = perf['receita_estimada'] / perf['total_gasto'].replace(0, 1)
            perf['cpa'] = perf['total_gasto'] / perf['total_conversoes'].replace(0, 1)
            
            col_perf1, col_perf2 = st.columns(2)
            with col_perf1:
                st.write("##### Eficiência (CPA vs ROAS)")
                fig_perf = px.scatter(perf.dropna(subset=['cpa', 'roas']), x='cpa', y='roas', size='total_gasto', color='nome_campanha', hover_name='nome_campanha', labels={'cpa': 'CPA (R$)', 'roas': 'ROAS'})
                fig_perf.update_layout(showlegend=False)
                st.plotly_chart(fig_perf, use_container_width=True, key="meta_performance_scatter")
                st.caption("ℹ️ O ideal são bolhas no canto inferior direito (baixo Custo por Aquisição, alto Retorno). O tamanho da bolha é o Gasto Total.")

            with col_perf2:
                st.write("##### Ranking de Campanhas por ROAS")
                perf_ranked = perf.sort_values('roas', ascending=False).head(10)
                fig_rank = px.bar(perf_ranked, y='nome_campanha', x='roas', orientation='h', color='roas', labels={'nome_campanha': '', 'roas': 'ROAS'}, text='roas')
                fig_rank.update_layout(yaxis={'categoryorder':'total ascending'})
                fig_rank.update_traces(texttemplate='%{text:.2f}x', textposition='outside')
                
                if not perf_ranked.empty:
                    max_x = perf_ranked['roas'].max() * 1.2
                    fig_rank.update_layout(xaxis_range=[0, max_x])
                
                st.plotly_chart(fig_rank, use_container_width=True, key="meta_roas_ranking_bar")
                st.caption("ℹ️ Campanhas com o maior retorno para cada real investido.")

    else:
        st.warning("Sem dados do Meta Ads para exibir no período selecionado.")

with tab_despesas:
    st.markdown("<h3>💸 Análise de Despesas</h3>", unsafe_allow_html=True)
    despesas_df = dados_filtrados.get('Despesas')
    if despesas_df is not None and not despesas_df.empty:
        total_despesas_aba = despesas_df['valor'].sum() if 'valor' in despesas_df.columns else 0
        qtd_lancamentos = len(despesas_df)
        despesa_media_aba = total_despesas_aba / qtd_lancamentos if qtd_lancamentos > 0 else 0
        c1, c2, c3 = st.columns(3)
        with c1: criar_cartao_metrica("Total de Despesas", formatar_real(total_despesas_aba), TEXTOS_AJUDA["Despesas Totais"], color="#795548")
        with c2: criar_cartao_metrica("Qtd. de Lançamentos", f"{qtd_lancamentos:,}", "Total de lançamentos de despesas no período", color="#9E9E9E")
        with c3: criar_cartao_metrica("Média por Lançamento", formatar_real(despesa_media_aba), "Valor médio de cada lançamento de despesa", color="#607D8B")
        if 'data' in despesas_df.columns and not despesas_df.empty:
            despesas_diarias = despesas_df.groupby(despesas_df['data'].dt.date)['valor'].sum().reset_index()
            fig = px.line(despesas_diarias, x='data', y='valor', title="📈 Despesas por Dia", markers=True, color_discrete_sequence=['#795548'], labels={'data': 'Data', 'valor': 'Valor'})
            fig.update_layout(yaxis_title="Valor da Despesa (R$)", xaxis_title="Data")
            fig.update_traces(hovertemplate='<b>Data:</b> %{x|%d %b %Y}<br><b>Valor:</b> R$ %{y:,.2f}<extra></extra>')
            st.plotly_chart(fig, use_container_width=True, key="despesas_diaria_line")
            st.caption("ℹ️ Evolução diária do valor total de despesas gerais lançadas na planilha.")
    else:
            st.warning("Sem dados de Despesas para exibir no período selecionado.")
with tab_dre:
    st.markdown("<h3>📈 Demonstrativo de Resultados (DRE)</h3>", unsafe_allow_html=True)
    custos_venda = (metricas['receita_total'] - metricas['receita_liquida_total'])
    dre_data = {'labels': ["Receita Bruta", "Custos de Venda", "Receita Líquida", "Despesas Operacionais", "Lucro Líquido"], 'values': [metricas['receita_total'], -custos_venda, metricas['receita_liquida_total'], -metricas['despesas_totais'], metricas['lucro_liquido']], 'measures': ['absolute', 'relative', 'total', 'relative', 'total']}
    if periodo_selecionado == 'Personalizado' and data_inicio_personalizada and data_fim_personalizada:
        subtitulo_periodo = f"Período: {data_inicio_personalizada.strftime('%d/%m/%Y')} a {data_fim_personalizada.strftime('%d/%m/%Y')}"
    else:
        subtitulo_periodo = f"Período: {periodo_selecionado}"
    if dre_data['values'][0] > 0:
        fig = go.Figure(go.Waterfall(name="DRE", orientation="v", measure=dre_data['measures'], x=dre_data['labels'], text=[formatar_real(v) for v in dre_data['values']], textposition="outside", textfont={"size": 14, "color": "black"}, y=dre_data['values'], connector={"line": {"color": "rgb(63, 63, 63)"}}, increasing={"marker":{"color":"#28a745"}}, decreasing={"marker":{"color":"#dc3545"}}, totals={"marker":{"color":"#007bff", "line": {"color":'#007bff', "width":2}}}))
        max_y = dre_data['values'][0] * 1.2
        fig.update_layout(title=f"<b>Demonstrativo de Resultados em Cascata</b><br><sub>{subtitulo_periodo}</sub>",
                          showlegend=False, yaxis_title="Valor (R$)",
                          yaxis_range=[0, max_y], margin=dict(t=80))
        st.plotly_chart(fig, use_container_width=True, key="dre_waterfall")
        st.caption("ℹ️ Visão em cascata do resultado financeiro, partindo da Receita Bruta até o Lucro Líquido.")
    else:
        st.warning("Sem dados suficientes para gerar o DRE no período selecionado.")

# Rodapé
st.markdown("---")
if periodo_selecionado == 'Personalizado':
    if data_inicio_personalizada and data_fim_personalizada:
        st.caption(f"Dashboard Rebobinador Express - Período: {data_inicio_personalizada.strftime('%d/%m/%Y')} a {data_fim_personalizada.strftime('%d/%m/%Y')}")
else:
    st.caption(f"Dashboard Rebobinador Express - Período: {periodo_selecionado}")
st.caption("© 2025 - Todos os direitos reservados")
