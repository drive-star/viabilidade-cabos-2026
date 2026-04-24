import streamlit as st
import pandas as pd
import numpy as np
import pdfplumber
import re
from datetime import datetime
from fpdf import FPDF
import io
import os

# ==========================================
# 1. CONFIGURAÇÃO E IDENTIDADE VISUAL (CSS)
# ==========================================
st.set_page_config(page_title="Focus ERP - Master 2026", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .stApp { background-color: #f1f3f5; }
    .header-box { background-color: #444444; color: #ffffff; padding: 25px; border-radius: 10px; font-size: 32px; font-weight: bold; text-align: center; margin-bottom: 25px; border-bottom: 6px solid #1a73e8; }
    .sub-header { background-color: #666666; color: #ffffff; padding: 15px; border-radius: 6px; font-size: 22px; font-weight: bold; margin-top: 20px; margin-bottom: 15px; }
    .main-box { background-color: #ffffff; border-radius: 12px; padding: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 25px; }
    
    .legend-box { padding: 10px; border-radius: 5px; margin-bottom: 5px; font-size: 14px; font-weight: bold; color: white; }
    .bg-perfeito { background-color: #007bff; } 
    .bg-cautela { background-color: #28a745; }  
    .bg-revisar { background-color: #ffc107; color: black !important; } 
    .bg-critico { background-color: #dc3545; }  
    
    .status-final { padding: 25px; border-radius: 15px; text-align: center; font-weight: bold; font-size: 28px; color: white; margin-top: 20px; }
    
    html, body, [class*="st-"] { font-size: 19px !important; }
    .stDataFrame div[data-testid="stTable"] { font-size: 21px !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. INICIALIZAÇÃO E MOTORES
# ==========================================
if 'logado' not in st.session_state: st.session_state.logado = False
if 'user_atual' not in st.session_state: st.session_state.user_atual = None
if 'carrinho' not in st.session_state: st.session_state.carrinho = []
if 'historico' not in st.session_state: st.session_state.historico = []

if 'mp_precos' not in st.session_state:
    st.session_state.mp_precos = {
        "Cobre (kg)": 88.00, "Alumínio (kg)": 18.50, "PVC Marfim (kg)": 9.50,
        "PVC HEPR (kg)": 18.60, "Capa PP (kg)": 11.99, "PVC Atox (kg)": 18.50,
        "Skin/Cores (kg)": 25.96, "Embalagem (un)": 16.70
    }

def calcular_custo_tecnico(row):
    mp = st.session_state.mp_precos
    soma_mp = (row.get('Cobre_kg', 0) * mp["Cobre (kg)"]) + \
              (row.get('Aluminio_kg', 0) * mp["Alumínio (kg)"]) + \
              (row.get('PVC_kg', 0) * mp["PVC Marfim (kg)"]) + \
              (row.get('HEPR_kg', 0) * mp["PVC HEPR (kg)"]) + \
              (row.get('Capa_PP_kg', 0) * mp["Capa PP (kg)"]) + \
              (row.get('PVC_atox_kg', 0) * mp["PVC Atox (kg)"]) + \
              (row.get('Skin_kg', 0) * mp["Skin/Cores (kg)"]) + \
              (row.get('Embalagem_un', 0) * mp["Embalagem (un)"])
    nome = str(row.get('Nome do produto', '')).upper()
    is_roll = '100M' in nome or str(row.get('Unidade', '')).upper() == 'RL'
    return round(soma_mp if is_roll else soma_mp / 100.0, 4)

def styler_master(row):
    nome = str(row.get('Nome do produto', row.get('Descrição', ''))).upper()
    styles = [''] * len(row)
    if 'IMPÉRIO' in nome or 'IMPERIUM' in nome:
        styles = ['background-color: #FFC0CB; color: black; font-weight: bold'] * len(row)
    if 'Custo_Un' in row and row['Custo_Un'] <= 0:
        styles = ['background-color: #ff9900; color: white'] * len(row)
    if 'Preço_Un' in row and 'Custo_Un' in row:
        if row['Preço_Un'] < row['Custo_Un'] or row['Preço_Un'] <= 0:
            styles = ['background-color: #dc3545; color: white; font-weight: bold'] * len(row)
    return styles

def carregar_dados():
    try:
        df = pd.read_csv("base_dados_produtos_viabilidade.csv", sep=";")
        df.columns = df.columns.str.strip()
        # Padronização da coluna de busca
        nome_correto = 'GRUPO/FAMILIA (Abrev.)'
        if nome_correto not in df.columns:
            if 'Família' in df.columns:
                df = df.rename(columns={'Família': nome_correto})
            else:
                df[nome_correto] = "Geral"
        return df
    except: return pd.DataFrame()

def styler_master_2026(df):
    """Aplica Cores: Preços (Azul), Pesos (Cinza Itálico), Custo (Marrom)"""
    def apply_styles(row):
        styles = [''] * len(row)
        nome = str(row.get('Nome do produto', row.get('Descrição', ''))).upper()
        
        for i, col in enumerate(df.columns):
            # Prioridade 1: Destaque Rosa para Império
            if 'IMPÉRIO' in nome or 'IMPERIUM' in nome:
                styles[i] = 'background-color: #FFC0CB; color: black; font-weight: bold'
                continue
            
            # Prioridade 2: Cores por tipo de dado
            if 'Preço' in col or 'Preco' in col:
                styles[i] = 'background-color: #ADD8E6; color: black;' # Azul Claro
            elif 'Peso' in col:
                styles[i] = 'background-color: #D3D3D3; color: black; font-style: italic;' # Cinza Claro
            elif 'Custo' in col:
                styles[i] = 'background-color: #D2B48C; color: black;' # Marrom Claro
                
            # Prioridade 3: Alerta de Prejuízo (Vermelho)
            if 'Preço_Un' in row and 'Custo_Un' in row:
                if row['Preço_Un'] < row['Custo_Un'] or row['Preço_Un'] <= 0:
                    styles[i] = 'background-color: #dc3545; color: white; font-weight: bold'
        return styles
    return df.style.apply(apply_styles, axis=1)
# ==========================================
# 3. LOGIN
# ==========================================
if not st.session_state.logado:
    st.markdown('<div class="header-box">Focus ERP - Acesso</div>', unsafe_allow_html=True)
    u = st.text_input("Usuário", key="login_user")
    p = st.text_input("Senha", type="password", key="login_pass")
    if st.button("Entrar"):
        if (u == "admin" and p == "maxfio123") or (u == "venda" and p == "1234"):
            st.session_state.logado, st.session_state.user_atual = True, u; st.rerun()
    st.stop()

# ==========================================
# 4. INTERFACE PRINCIPAL
# ==========================================
df_base = carregar_dados()
tabs = st.tabs(["🛒 Orçamentos", "🏷️ Tabela Preços", "📑 Engenharia", "📜 Histórico", "⚙️ Admin"])

# --- ABA 1: ORÇAMENTOS E VIABILIDADE ---
with tabs[0]:
    st.markdown('<div class="header-box">🚀 SISTEMA DE VIABILIDADE E ORÇAMENTOS</div>', unsafe_allow_html=True)

    # 1. IDENTIFICAÇÃO DO CLIENTE E ORÇAMENTO
    with st.container():
        st.markdown('<div class="main-box">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 1, 1])
        cli = c1.text_input("Nome do Cliente", key="cli_v13")
        cnpj = c2.text_input("CNPJ / CPF", key="cnpj_v13")
        orc_n = c3.text_input("Nº Orçamento", key="orc_v13")
        data_at = datetime.now().strftime("%d/%m/%Y")
        st.write(f"📅 **Data:** {data_at}")
        st.markdown('</div>', unsafe_allow_html=True)

    # 2. ENTRADAS: MANUAL, PDF OU VOZ (RASCUNHO)
    with st.expander("➕ Adicionar Itens (Manual / PDF / Voz)", expanded=True):
        t_man, t_smart = st.tabs(["Inserção Manual", "Inteligente (PDF/Voz)"])
        
        with t_man:
            f_c1, f_c2 = st.columns([1.5, 2])
            # Uso da coluna solicitada: GRUPO/FAMILIA (Abrev.)
            grupos = ["Todas"] + sorted(list(df_base['GRUPO/FAMILIA (Abrev.)'].unique().astype(str)))
            v_fam = f_c1.selectbox("Grupo / Família (Abrev.)", grupos, key="fam_v13")
            
            df_f = df_base if v_fam == "Todas" else df_base[df_base['GRUPO/FAMILIA (Abrev.)'] == v_fam]
            sel_p = f_c2.selectbox("Selecione o Produto ou busque pelo Código", 
                                   df_f['Código'].astype(str) + " - " + df_f['Nome do produto'], key="prod_v13")
            
            row_it = df_base[df_base['Código'].astype(str) == sel_p.split(" - ")[0]].iloc[0]
            
            q1, q2, q3 = st.columns(3)
            qtd_m = q1.number_input("Quantidade", min_value=1.0, value=100.0, key="qtd_v13")
            prc_m = q2.number_input("Preço Tabela (R$)", value=row_it['Preco_Unit'], format="%.4f", key="prc_v13")
            
            if q3.button("📥 Inserir no Quadrante", use_container_width=True):
                st.session_state.carrinho.append({
                    "Código": row_it['Código'], "Descrição": row_it['Nome do produto'], 
                    "Peso_Un": row_it.get('Peso_Total_kg', 0), "Qtd": qtd_m, 
                    "Preço_Un": prc_m, "Custo_Un": calcular_custo_tecnico(row_it)
                })
                st.rerun()

        with t_smart:
            up_pdf = st.file_uploader("Upload de Pedido PDF", type=['pdf'], key="up_pdf_v13")
            up_audio = st.audio_input("Dite os itens do pedido", key="up_audio_v13")
            if up_pdf and st.button("🔍 Extrair PDF", key="btn_pdf_v13"):
                st.session_state.rascunho = extrair_pdf(up_pdf)
                st.rerun()

    # Processamento de Rascunho (PDF/Voz)
    if 'rascunho' in st.session_state and st.session_state.rascunho:
        st.warning("⚠️ Itens detectados. Confira e confirme abaixo.")
        df_rasc = st.data_editor(pd.DataFrame(st.session_state.rascunho), use_container_width=True, key="ed_rasc_v13")
        cr1, cr2 = st.columns(2)
        if cr1.button("✅ Confirmar Tudo", use_container_width=True):
            for _, r in df_rasc.iterrows():
                match = df_base[df_base['Código'].astype(str) == str(r['Código'])]
                st.session_state.carrinho.append({
                    "Código": r['Código'], "Descrição": r['Descrição'], "Qtd": r['Qtd'], "Preço_Un": r['Preço_Un'],
                    "Custo_Un": calcular_custo_tecnico(match.iloc[0]) if not match.empty else 0.0,
                    "Peso_Un": match.iloc[0].get('Peso_Total_kg', 0) if not match.empty else 0.0
                })
            st.session_state.rascunho = []; st.rerun()
        if cr2.button("🗑️ Descartar", use_container_width=True): st.session_state.rascunho = []; st.rerun()

    # 3. QUADRANTE DE CONFERÊNCIA COM RATEIO E EDICAO
    if st.session_state.carrinho:
        st.markdown('<div class="sub-header">🔎 QUADRANTE DE CONFERÊNCIA E RATEIO</div>', unsafe_allow_html=True)
        
        # Parâmetros de Rateio Global
        with st.expander("📊 Ajuste de Descontos/Acréscimos Globais", expanded=True):
            col_rateio1, col_rateio2 = st.columns(2)
            desc_glob = col_rateio1.number_input("Desconto Global (%)", value=0.0, key="desc_glob_v13")
            acre_glob = col_rateio2.number_input("Acréscimo Global (%)", value=0.0, key="acre_glob_v13")
            fator = 1 + (acre_glob - desc_glob) / 100

        df_cart = pd.DataFrame(st.session_state.carrinho)
        # Adiciona colunas de Rateio solicitadas
        df_cart['Ajuste (%)'] = acre_glob - desc_glob
        df_cart['Preço Real'] = df_cart['Preço_Un'] * fator
        df_cart['Total Item'] = df_cart['Qtd'] * df_cart['Preço Real']

        # Ordem: Peso (Cinza/Itálico) após Descrição
        df_cart = df_cart[['Código', 'Descrição', 'Peso_Un', 'Qtd', 'Preço_Un', 'Ajuste (%)', 'Preço Real', 'Total Item', 'Custo_Un']]

        df_ed = st.data_editor(
            df_cart, num_rows="dynamic", use_container_width=True, key="ed_main_v13",
            column_config={
                "Peso_Un": st.column_config.NumberColumn("Peso (kg)", format="%.3f", help="Peso em Cinza Claro / Itálico"),
                "Ajuste (%)": st.column_config.NumberColumn("Ajuste", format="%.2f%%", disabled=True),
                "Preço Real": st.column_config.NumberColumn("Preço Real", format="R$ %.4f", disabled=True),
                "Total Item": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True),
            }
        )
        st.session_state.carrinho = df_ed.to_dict('records')

        # 4. PARÂMETROS FINANCEIROS (Baseados no PDF Quadro Resumo)
        st.markdown('<div class="sub-header">📊 DEDUÇÕES E TAXAS DO PEDIDO</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="main-box">', unsafe_allow_html=True)
            d1, d2, d3, d4 = st.columns(4)
            c_ext = d1.number_input("Comissão Ext (%)", value=3.0, key="cext_v13")
            c_int = d1.number_input("Comissão Int (%)", value=0.65, key="cint_v13")
            t_op = d2.number_input("Taxa Op. (%)", value=3.5, key="top_v13")
            f_cif = d2.number_input("Frete CIF (%)", value=3.0, key="fcif_v13")
            desc_v = d3.number_input("Desc. Vista (%)", value=0.0, key="dvista_v13")
            t_card = d3.number_input("Taxa Cartão (%)", value=0.0, key="tcard_v13")
            imp = d4.number_input("Impostos (%)", value=12.0, key="imp_v13")
            st.markdown('</div>', unsafe_allow_html=True)

        # CÁLCULOS
        v_rb = sum([x['Qtd'] * x['Preço Real'] for x in st.session_state.carrinho])
        c_tot = sum([x['Qtd'] * x['Custo_Un'] for x in st.session_state.carrinho])
        p_tot = sum([x['Qtd'] * (x.get('Peso_Un', 0)/100) for x in st.session_state.carrinho])
        
        d_liq = v_rb * ((c_ext + c_int + t_op + f_cif + desc_v + t_card + imp) / 100)
        r_liq = v_rb - d_liq
        l_liq = r_liq - c_tot
        margem_f = (l_liq / v_rb * 100) if v_rb > 0 else 0

        # 5. QUADRO RESUMO ANALISE (Visual do PDF)
        st.markdown('<div class="sub-header">📈 QUADRO RESUMO ANALISE</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="main-box">', unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            r1.metric("CUSTO TOTAL", f"R$ {c_tot:,.2f}")
            r1.metric("DESPESA LÍQUIDA", f"R$ {d_liq:,.2f}")
            r2.metric("VENDA BRUTA (RB)", f"R$ {v_rb:,.2f}")
            r2.metric("RECEITA LÍQUIDA", f"R$ {r_liq:,.2f}")
            r3.metric("PESO TOTAL", f"{p_tot:,.2f} kg")
            r3.metric("LUCRO LÍQUIDO", f"R$ {l_liq:,.2f}")

            if margem_f >= 13: cl, tx = "bg-perfeito", "APROVADO PERFEITO"
            elif margem_f >= 9: cl, tx = "bg-cautela", "APROVADO CAUTELA"
            elif margem_f >= 8: cl, tx = "bg-revisar", "REVISAR"
            else: cl, tx = "bg-critico", "REPROVADO"
            st.markdown(f'<div class="status-final {cl}">{tx} | MARGEM: {margem_f:.2f}%</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # 6. FINALIZAÇÃO: IMPRESSÃO E LIBERAÇÃO ESPECIAL
        st.divider()
        cp, cs = st.columns(2)
        
        with cp:
            if st.button("🖨️ IMPRIMIR ORÇAMENTO", use_container_width=True):
                if cli:
                    pdf = FPDF()
                    pdf.add_page(); pdf.set_font("Arial", "B", 14)
                    pdf.cell(190, 10, f"ORÇAMENTO - {cli}", 1, 1, 'C'); pdf.ln(10)
                    pdf.set_font("Arial", "", 10)
                    for i in st.session_state.carrinho:
                        pdf.cell(190, 7, f"{i['Código']} - {i['Descrição']} | Qtd: {i['Qtd']} | Preço: R${i['Preço Real']:.2f}", 0, 1)
                    pdf.ln(10); pdf.set_font("Arial", "B", 12)
                    pdf.cell(190, 10, f"TOTAL: R$ {v_rb:,.2f}", 0, 1, 'R')
                    st.download_button("📥 Baixar PDF", pdf.output(dest='S'), f"Orc_{cli}.pdf")
                else: st.error("Informe o cliente!")

        with cs:
            tem_erro = any([x['Preço Real'] < x['Custo_Un'] for x in st.session_state.carrinho]) or margem_f < 8
            if not tem_erro:
                if st.button("💾 SALVAR E ABRIR NOVA TELA", use_container_width=True):
                    st.session_state.historico.append({"Data": data_at, "Cliente": cli, "Total": v_rb, "Status": "Aprovado"})
                    st.balloons(); st.success("Salvo!"); st.session_state.carrinho = []; st.rerun()
            else:
                st.error("⚠️ LIBERAÇÃO GERENCIAL NECESSÁRIA")
                with st.expander("🔑 AUTORIZAÇÃO POR SENHA"):
                    pw = st.text_input("Senha Master", type="password", key="pw_v13")
                    adm = st.text_input("Nome Responsável", key="adm_v13")
                    mot = st.text_area("Motivo", key="mot_v13")
                    if st.button("🔓 AUTORIZAR E SALVAR", use_container_width=True):
                        if pw == "maxfio123" and adm and mot:
                            st.session_state.historico.append({"Data": data_at, "Cliente": cli, "Total": v_rb, "Status": "LIBERADO", "Responsável": adm, "Motivo": mot})
                            st.success(f"Liberado por {adm}!"); st.session_state.carrinho = []; st.rerun()
                        else: st.error("Dados ou senha incorretos.")
            
# --- ABA 2: TABELA DE PREÇOS ---
with tabs[1]:
    st.markdown('<div class="header-box">🏷️ TABELA DE PREÇOS COMERCIAL</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 2])
    g_tab = c1.selectbox("Grupo / Família (Abrev.)", ["Todas"] + list(df_base['GRUPO/FAMILIA (Abrev.)'].unique()), key="g_tab")
    k_tab = c2.text_input("Código", key="k_tab")
    d_tab = c3.text_input("Descrição Parcial", key="d_tab")
    
    df_p = df_base.copy()
    if g_tab != "Todas": df_p = df_p[df_p['GRUPO/FAMILIA (Abrev.)'] == g_tab]
    if k_tab: df_p = df_p[df_p['Código'].astype(str).str.contains(k_tab)]
    if d_tab: df_p = df_p[df_p['Nome do produto'].str.contains(d_tab, case=False, na=False)]
    
    st.dataframe(styler_master_2026(df_p), use_container_width=True)

# --- ABA 3: ENGENHARIA ---
with tabs[2]:
    st.markdown('<div class="header-box">📑 ENGENHARIA DE CUSTOS TÉCNICOS</div>', unsafe_allow_html=True)
    e1, e2, e3 = st.columns([1, 1, 2])
    g_eng = e1.selectbox("Grupo / Família (Abrev.) ", ["Todas"] + list(df_base['GRUPO/FAMILIA (Abrev.)'].unique()), key="g_eng")
    k_eng = e2.text_input("Código ", key="k_eng")
    d_eng = e3.text_input("Descrição Parcial ", key="d_eng")
    
    df_e = df_base.copy()
    df_e['Custo_Un'] = df_e.apply(calcular_custo_tecnico, axis=1)
    
    if g_eng != "Todas": df_e = df_e[df_e['GRUPO/FAMILIA (Abrev.)'] == g_eng]
    if k_eng: df_e = df_e[df_e['Código'].astype(str).str.contains(k_eng)]
    if d_eng: df_e = df_e[df_e['Nome do produto'].str.contains(d_eng, case=False, na=False)]
    
    st.dataframe(styler_master_2026(df_e), use_container_width=True)

# --- ABA 4: HISTÓRICO ---
with tabs[3]:
    st.markdown('<div class="header-box">HISTÓRICO DE ANÁLISES</div>', unsafe_allow_html=True)
    if st.session_state.historico:
        st.table(pd.DataFrame(st.session_state.historico))

# --- ABA 5: ADMIN ---
with tabs[4]:
    st.title("⚙️ Administração e Auditoria de Custos")
    
    # 1. FORMULÁRIO DE ATUALIZAÇÃO
    if st.session_state.user_atual == "admin":
        with st.form("admin_mp_form_v2"):
            st.subheader("Ajuste de Preços de Matéria-Prima (R$/kg)")
            novos = {}
            cols = st.columns(3)
            for i, (k, v) in enumerate(st.session_state.mp_precos.items()):
                novos[k] = cols[i % 3].number_input(k, value=v, key=f"mp_adm_{i}")
            
            if st.form_submit_button("💾 Atualizar Engenharia e Salvar Histórico"):
                # --- LÓGICA DE SNAPSHOT (SALVA A VERSÃO ANTERIOR) ---
                if not df_base.empty:
                    df_snapshot = df_base.copy()
                    # Calcula os custos com os preços ANTES da alteração
                    df_snapshot['Custo_Técnico_Antigo'] = df_snapshot.apply(calcular_custo_tecnico, axis=1)
                    
                    registro_log = {
                        "Data_Alteracao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "Usuario": st.session_state.user_atual,
                        "Precos_MP_Antigos": st.session_state.mp_precos.copy(),
                        "Tabela_Snapshot": df_snapshot.to_csv(index=False).encode('utf-8-sig')
                    }
                    
                    if 'historico_custos' not in st.session_state:
                        st.session_state.historico_custos = []
                    
                    st.session_state.historico_custos.insert(0, registro_log) # Adiciona no topo
                
                # Atualiza para os novos preços
                st.session_state.mp_precos.update(novos)
                st.success("✅ Engenharia atualizada! Versão anterior arquivada no log abaixo.")
                st.rerun()

        st.divider()

        # 2. LISTA DE LOG E HISTÓRICO DE VERSÕES (AUDITORIA)
        st.subheader("📜 Log de Alterações e Versões Anteriores")
        
        if 'historico_custos' in st.session_state and st.session_state.historico_custos:
            for idx, log in enumerate(st.session_state.historico_custos):
                with st.expander(f"📌 Alteração em: {log['Data_Alteracao']} (Por: {log['Usuario']})"):
                    c1, c2 = st.columns([2, 1])
                    
                    with c1:
                        st.write("**Preços de MP nesta versão:**")
                        st.json(log['Precos_MP_Antigos'])
                    
                    with c2:
                        st.write("**Tabela de Engenharia:**")
                        # O "Link para nova página" aqui é o download do arquivo CSV daquela versão
                        st.download_button(
                            label="📥 Baixar Tabela desta Versão (CSV)",
                            data=log['Tabela_Snapshot'],
                            file_name=f"Engenharia_Retroativa_{log['Data_Alteracao'].replace('/','-')}.csv",
                            mime="text/csv",
                            key=f"dl_btn_{idx}"
                        )
                        st.info("Este arquivo contém todos os custos técnicos calculados com os preços acima.")
        else:
            st.info("Nenhuma alteração de custo registrada no log ainda.")

    else:
        st.error("Acesso restrito ao Administrador para alteração de custos.")