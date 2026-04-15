import streamlit as st
import pandas as pd
import pdfplumber
from datetime import datetime
import re

# ==========================================
# 1. CONFIGURAÇÃO E ESTILIZAÇÃO (CSS)
# ==========================================
st.set_page_config(page_title="Focus ERP - Inteligência Comercial", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .viability-box { background-color: #f8f9fa; border-radius: 12px; padding: 25px; border-left: 10px solid #1a73e8; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-top: 20px; }
    .metric-label { font-size: 13px; color: #666; font-weight: bold; text-transform: uppercase; margin-bottom: 2px; }
    .metric-value { font-size: 22px; font-weight: bold; color: #111; margin-bottom: 10px; }
    
    /* Régua de Cores de Status Conforme Quadro Resumo Analise */
    .status-aprovado { background-color: #28a745; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .status-ressalva { background-color: #007bff; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .status-reprovado { background-color: #ffc107; color: black; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .status-reprovado-escuro { background-color: #ff8c00; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .status-critico { background-color: #dc3545; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. INICIALIZAÇÃO DE ESTADOS (SESSION STATE)
# ==========================================
if 'usuarios' not in st.session_state: 
    st.session_state.usuarios = {"admin": "1234"}
if 'logado' not in st.session_state: st.session_state.logado = False
if 'user_atual' not in st.session_state: st.session_state.user_atual = None
if 'carrinho' not in st.session_state: st.session_state.carrinho = []
if 'historico_pedidos' not in st.session_state: st.session_state.historico_pedidos = []
if 'previa_pdf' not in st.session_state: st.session_state.previa_pdf = []

# Matérias-Primas Iniciais baseadas nos cabeçalhos técnicos [cite: 32, 44, 46]
if 'mp_precos' not in st.session_state:
    st.session_state.mp_precos = {
        "Cobre (kg)": 88.00, "PVC Marfim (kg)": 9.50, "Alumínio (kg)": 18.50,
        "Skin/Cores (kg)": 25.96, "Capa PP (kg)": 11.99, "PVC HEPR (kg)": 18.60, "Embalagem (un)": 16.70
    }

# ==========================================
# 3. TRATAMENTO DA BASE DE DADOS (1.268 ITENS)
# ==========================================
def carregar_base_protegida():
    try:
        # Carrega o CSV real 
        df = pd.read_csv("base_dados_produtos_viabilidade.csv", sep=";")
        
        # REDE DE PROTEÇÃO: Se a coluna não existir, cria com 0 para evitar o KeyError
        cols_esperadas = {
            'Cobre_kg': 0.0, 'Aluminio_kg': 0.0, 'PVC_kg': 0.0, 
            'Skin_kg': 0.0, 'Capa_PP_kg': 0.0, 'HEPR_kg': 0.0, 
            'Embalagem_un': 0.0, 'Preco_Unit': 0.0
        }
        
        for col, val_default in cols_esperadas.items():
            if col not in df.columns:
                df[col] = val_default
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        return df
    except Exception as e:
        st.error(f"Erro crítico no CSV: {e}")
        return pd.DataFrame()

def calcular_custo_dinamico(row):
    mp = st.session_state.mp_precos
    total = (row['Cobre_kg'] * mp['Cobre (kg)']) + \
            (row['Aluminio_kg'] * mp['Alumínio (kg)']) + \
            (row['PVC_kg'] * mp['PVC Marfim (kg)']) + \
            (row['HEPR_kg'] * mp['PVC HEPR (kg)']) + \
            (row['Capa_PP_kg'] * mp['Capa PP (kg)']) + \
            (row['Skin_kg'] * mp['Skin/Cores (kg)']) + \
            (row['Embalagem_un'] * mp['Embalagem (un)'])
    return round(total, 2)

# ==========================================
# 4. LOGIN
# ==========================================
if not st.session_state.logado:
    st.title("🔐 Focus ERP - Acesso")
    u, p = st.text_input("Usuário"), st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u in st.session_state.usuarios and st.session_state.usuarios[u] == p:
            st.session_state.logado, st.session_state.user_atual = True, u
            st.rerun()
    st.stop()

df_mestre = carregar_base_protegida()
if df_mestre.empty:
    st.error("Base de dados vazia ou arquivo não encontrado.")
    st.stop()

# ==========================================
# 5. INTERFACE PRINCIPAL
# ==========================================
st.sidebar.title(f"👤 {st.session_state.user_atual.upper()}")
if st.sidebar.button("Logoff"):
    st.session_state.logado = False
    st.rerun()

tabs = st.tabs(["🛒 Novo Pedido", "📑 Histórico", "⛓️ Engenharia (Custos)", "👥 Admin"])

# --- ABA 1: NOVO PEDIDO (PDF + MANUAL) ---
with tabs[0]:
    st.title("🚀 Novo Pedido Comercial")
    cliente = st.text_input("Nome do Cliente")

    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.subheader("📄 Importar PDF")
        pdf_f = st.file_uploader("Subir Orçamento", type="pdf")
        if pdf_f and st.button("🔍 Analisar PDF"):
            with pdfplumber.open(pdf_f) as pdf:
                texto = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                for _, r in df_mestre.iterrows():
                    # Busca por Bitola ou Código no texto [cite: 1, 31, 44]
                    if str(r['Código']) in texto:
                        st.session_state.carrinho.append({
                            "Código": r['Código'], "Item": r.get('Nome do produto', 'Item'), 
                            "Qtd": 1.0, "Custo": calcular_custo_dinamico(r), "Preço": r['Preco_Unit']
                        })
            st.success("Análise concluída!")

    with col_p2:
        st.subheader("📦 Cadastro Manual")
        opcoes = df_mestre['Código'].astype(str) + " - " + df_mestre.get('Nome do produto', '')
        sel = st.selectbox("Escolha o Produto", options=opcoes)
        qtd = st.number_input("Qtd", min_value=1.0, value=1.0)
        
        cod_limpo = sel.split(" - ")[0]
        it_ref = df_mestre[df_mestre['Código'].astype(str) == cod_limpo].iloc[0]
        preco_man = st.number_input("Preço Sugerido (R$)", value=float(it_ref['Preco_Unit']))
        
        if st.button("➕ Inserir no Pedido"):
            st.session_state.carrinho.append({
                "Código": it_ref['Código'], "Item": it_ref.get('Nome do produto', 'Item'), 
                "Qtd": qtd, "Custo": calcular_custo_dinamico(it_ref), "Preço": preco_man
            })
            st.rerun()

    if st.session_state.carrinho:
        st.subheader("📋 Itens Selecionados")
        df_edit = st.data_editor(pd.DataFrame(st.session_state.carrinho), use_container_width=True, key="main_edit")
        st.session_state.carrinho = df_edit.to_dict('records')

        # Parâmetros conforme QUADRO RESUMO [cite: 49, 50, 51, 52]
        st.divider()
        c1, c2, c3 = st.columns(3)
        p_comis = c1.number_input("Comissão Total (%)", value=3.15)
        p_frete = c1.number_input("Frete CIF (%)", value=3.0)
        p_desc = c2.number_input("Desconto à Vista (%)", value=0.0)
        p_taxa = c2.number_input("Taxas Operação (%)", value=3.5)
        p_st = c3.number_input("S.T. (Repasse %)", value=0.0)
        p_trib = c3.number_input("Impostos/DIFAL (%)", value=12.0)

        # Cálculos Finais [cite: 46, 47, 49, 52]
        v_bruto = sum([x['Qtd'] * x['Preço'] for x in st.session_state.carrinho])
        v_custo_mp = sum([x['Qtd'] * x['Custo'] for x in st.session_state.carrinho])
        f_base = v_bruto * (1 - p_desc/100)
        v_st = f_base * (p_st/100)
        total_rb = f_base + v_st
        
        deducoes = f_base * ((p_comis + p_frete + p_taxa + p_trib)/100)
        receita_liq = f_base - deducoes
        lucro_liq = receita_liq - v_custo_mp
        margem = (lucro_liq / f_base * 100) if f_base > 0 else 0

        # Régua de Status [cite: 53, 65, 67]
        if margem >= 12: st_div = '<div class="status-aprovado">✅ APROVADO</div>'
        elif 9 <= margem < 12: st_div = '<div class="status-ressalva">⚠️ APROVADO COM RESSALVA</div>'
        elif 5 <= margem < 9: st_div = '<div class="status-reprovado">❌ REPROVADO</div>'
        elif 0 <= margem < 5: st_div = '<div class="status-reprovado-escuro">🚫 MARGEM BAIXA</div>'
        else: st_div = '<div class="status-critico">🚨 REPROVADO CRÍTICO</div>'

        st.markdown(f"""
            <div class="viability-box">
                <div style='display: flex; justify-content: space-around;'>
                    <div><p class="metric-label">Venda Bruta (RB)</p><p class="metric-value">R$ {total_rb:,.2f}</p></div>
                    <div><p class="metric-label">Lucro Líquido</p><p class="metric-value">R$ {lucro_liq:,.2f}</p></div>
                    <div><p class="metric-label">Margem Real</p><p class="metric-value">{margem:.2f}%</p></div>
                </div>
                <div style='margin-top: 20px;'>{st_div}</div>
            </div>""", unsafe_allow_html=True)
        
        if st.button("💾 Finalizar e Salvar"):
            st.session_state.historico_pedidos.append({"Data": datetime.now().strftime("%d/%m/%Y"), "Cliente": cliente, "Total": total_rb, "Margem": f"{margem:.2f}%"})
            st.session_state.carrinho = []
            st.success("Pedido registrado!")
            st.rerun()

# --- ABA 3: ENGENHARIA (TODOS OS 1.268 ITENS) ---
with tabs[2]:
    st.title("⛓️ Relatório Técnico de Engenharia")
    st.subheader("📊 Custos Atuais de Matéria-Prima")
    st.table(pd.DataFrame([st.session_state.mp_precos]))

    agrupar = st.checkbox("Agrupar Visualização por Família")
    df_eng = df_mestre.copy()
    df_eng['Custo Total'] = df_eng.apply(calcular_custo_dinamico, axis=1)

    def style_base(row):
        if row['Custo Total'] <= 0: return ['background-color: orange'] * len(row)
        if row['Cobre_kg'] <= 0 and row['Aluminio_kg'] <= 0: return ['background-color: #ff4d4d'] * len(row)
        return [''] * len(row)

    if agrupar and 'Grupo' in df_eng.columns:
        st.dataframe(df_eng.groupby('Grupo').agg({'Custo Total': 'mean'}).reset_index(), use_container_width=True)
    else:
        st.write(f"Exibindo **{len(df_eng)}** itens.")
        st.dataframe(df_eng.style.apply(style_base, axis=1), use_container_width=True)

    # Supervisor - Alterar MPs [cite: 46]
    st.divider()
    with st.expander("🔑 Área Supervisor: Reajustar Matéria-Prima"):
        if st.text_input("Senha Supervisor", type="password", key="pwd_mp") == "1234":
            c1, c2 = st.columns(2)
            n_cobre = c1.number_input("Novo Cobre (kg)", value=st.session_state.mp_precos['Cobre (kg)'])
            n_pvc = c2.number_input("Novo PVC (kg)", value=st.session_state.mp_precos['PVC Marfim (kg)'])
            if st.button("🔄 Atualizar Cotações"):
                st.session_state.mp_precos.update({"Cobre (kg)": n_cobre, "PVC Marfim (kg)": n_pvc})
                st.success("Toda a base recalculada!")
                st.rerun()

# --- ABA 4: ADMIN (REAJUSTE GLOBAL DE PREÇOS) ---
with tabs[3]:
    st.title("🔐 Administração e Preços")
    st.subheader("📋 Tabela Geral de Preços")
    st.dataframe(df_mestre[['Código', 'Preco_Unit']], use_container_width=True)
    
    st.divider()
    st.subheader("⚠️ Alteração Global de Tabela")
    if st.text_input("Senha Administrador", type="password", key="pwd_admin") == "1234":
        metodo = st.radio("Ajustar por", ["Porcentagem (%)", "Valor Fixo (R$)"])
        valor = st.number_input("Valor do Ajuste", value=0.0)
        
        if st.button("Confirmar Reajuste em Massa"):
            if metodo == "Porcentagem (%)":
                df_mestre['Preco_Unit'] = df_mestre['Preco_Unit'] * (1 + valor/100)
            else:
                df_mestre['Preco_Unit'] = df_mestre['Preco_Unit'] + valor
            
            # Salva no CSV 
            df_mestre.to_csv("base_dados_produtos_viabilidade.csv", sep=";", index=False)
            st.success("Tabela atualizada e salva no CSV!")
            st.rerun()