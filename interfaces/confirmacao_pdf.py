import streamlit as st
import pandas as pd
import plotly.express as px
import re
import io  # alteração realizada aqui: manipular buffer de Excel
from datetime import date
from utils.carteiras_modelo import get_modelo_carteira
from utils.cores import PALETTE
from utils.geracao_pdf import generate_pdf  # mantém mesmo nome

def format_number_br(valor):
    try:
        v = float(valor)
    except Exception:
        return str(valor)
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def show():
    st.header("5. Confirmação e Geração de PDF")

    # estilo das tabelas
    st.markdown("""
        <style>
        table thead th:first-child, table tbody td:first-child {
            text-align: left !important;
        }
        table thead th:not(:first-child), table tbody td:not(:first-child) {
            text-align: center !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # entradas de cliente e assessor
    cliente_nome  = st.text_input("Nome do Cliente")
    nome_assessor = st.text_input("Nome do Assessor")

    # dados das etapas anteriores
    ativos_df       = pd.DataFrame(st.session_state.get("ativos_df", []))
    carteira_modelo = st.session_state.get("carteira_modelo", "")
    sugestao        = st.session_state.get("sugestao", {})

    # validações iniciais
    if ativos_df.empty or not carteira_modelo:
        st.error("Informações incompletas. Volte e revise as etapas anteriores.")
        return
    for col in ("saldo_bruto", "Liquidez", "Novo Valor"):
        if col not in ativos_df.columns:
            st.error(f"Coluna '{col}' não encontrada. Verifique as etapas anteriores.")
            return

    # === DISTRIBUIÇÃO ATUAL ===
    ativos_df["valor_atual"] = pd.to_numeric(ativos_df["saldo_bruto"], errors="coerce").fillna(0.0)  # alteração realizada aqui
    dist_atual = (
        ativos_df.groupby("Classificação")["valor_atual"]
                 .sum()
                 .reset_index()
    )
    total_atual = float(dist_atual["valor_atual"].sum())
    dist_atual["Percentual"] = dist_atual["valor_atual"] / total_atual * 100 if total_atual else 0.0  # alteração realizada aqui

    # === DISTRIBUIÇÃO SUGERIDA ===
    ativos_df["Novo Valor"] = pd.to_numeric(ativos_df["Novo Valor"], errors="coerce").fillna(0.0)  # alteração realizada aqui
    dist_sug = (
        ativos_df.groupby("Classificação")["Novo Valor"]
                 .sum()
                 .reset_index()
                 .rename(columns={"Novo Valor": "valor_sugerido"})
    )
    total_sug = float(dist_sug["valor_sugerido"].sum())
    dist_sug["Percentual"] = dist_sug["valor_sugerido"] / total_sug * 100 if total_sug else 0.0  # alteração realizada aqui

    # === MAPA DE CORES PELA ORDEM ATUAL ===
    sorted_classes = dist_atual.sort_values("Percentual", ascending=False)["Classificação"].tolist()
    for cls in dist_sug["Classificação"]:
        if cls not in sorted_classes:
            sorted_classes.append(cls)
    color_map = {cls: PALETTE[i % len(PALETTE)] for i, cls in enumerate(sorted_classes)}

    # === GRÁFICOS DE DISTRIBUIÇÃO ===
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Atual")
        fig_atual = px.pie(
            dist_atual,
            names="Classificação",
            values="valor_atual",
            hole=0.3,
            color="Classificação",
            color_discrete_map=color_map
        )
        fig_atual.update_traces(direction="clockwise", textinfo="percent+label", texttemplate="%{percent:.1%}")
        fig_atual.update_layout(separators=",.")
        st.plotly_chart(fig_atual, use_container_width=True)
    with c2:
        st.subheader("Carteira Sugerida")
        fig_sug = px.pie(
            dist_sug,
            names="Classificação",
            values="valor_sugerido",
            hole=0.3,
            color="Classificação",
            color_discrete_map=color_map
        )
        fig_sug.update_traces(direction="clockwise", textinfo="percent+label", texttemplate="%{percent:.1%}")
        fig_sug.update_layout(separators=",.")
        st.plotly_chart(fig_sug, use_container_width=True)

    # === TABELAS ORDENADAS ===
    t1, t2 = st.columns(2)
    with t1:
        st.subheader("Atual")
        d1 = dist_atual.sort_values("valor_atual", ascending=False).reset_index(drop=True)
        d1["Valor (R$)"]     = d1["valor_atual"].apply(format_number_br)
        d1["Percentual (%)"] = d1["Percentual"].apply(lambda x: format_number_br(x) + "%")
        st.table(d1[["Classificação", "Valor (R$)", "Percentual (%)"]])
    with t2:
        st.subheader("Carteira Sugerida")
        d2 = dist_sug.sort_values("valor_sugerido", ascending=False).reset_index(drop=True)
        d2["Valor Ideal (R$)"]     = d2["valor_sugerido"].apply(format_number_br)
        d2["Percentual Ideal (%)"] = d2["Percentual"].apply(lambda x: format_number_br(x) + "%")
        st.table(d2[["Classificação", "Valor Ideal (R$)", "Percentual Ideal (%)"]])

    # === DIFERENÇAS ENTRE ATUAL E SUGERIDA ===
    st.subheader("Diferenças entre Atual e Sugerida")
    resumo = []
    all_classes = set(dist_atual["Classificação"]).union(dist_sug["Classificação"])
    for cls in all_classes:
        pa = float(dist_atual.loc[dist_atual["Classificação"] == cls, "Percentual"].sum())
        ps = float(dist_sug.loc[dist_sug["Classificação"] == cls, "Percentual"].sum())
        adj = round(ps - pa, 2)
        resumo.append({
            "Classificação": cls,
            "Atual (%)": pa,
            "Sugerida (%)": ps,
            "Ajuste (%)": adj,
            "Ação": "Aumentar" if adj > 0 else ("Reduzir" if adj < 0 else "Inalterado")
        })
    res_df = pd.DataFrame(resumo).sort_values("Ajuste (%)", key=lambda c: c.astype(float), ascending=False).reset_index(drop=True)
    res_disp = res_df.copy()
    for col in ["Atual (%)", "Sugerida (%)", "Ajuste (%)"]:
        res_disp[col] = res_disp[col].apply(lambda x: format_number_br(x) + "%")
    st.table(res_disp)

    # === ATIVOS ALOCADOS E RESGATADOS ===
    if "Valor Realocado" in ativos_df.columns:
        st.subheader("Ativos Alocados")
        alocados = ativos_df[pd.to_numeric(ativos_df["Valor Realocado"], errors="coerce").fillna(0.0) > 0].copy()  # alteração realizada aqui
        if not alocados.empty:
            for c in ["valor_atual", "Novo Valor", "Valor Realocado"]:
                alocados[c] = pd.to_numeric(alocados[c], errors="coerce").fillna(0.0)
            alocados["Valor Atual (R$)"]     = alocados["valor_atual"].apply(format_number_br)
            alocados["Novo Valor (R$)"]      = alocados["Novo Valor"].apply(format_number_br)
            alocados["Valor Realocado (R$)"] = alocados["Valor Realocado"].apply(format_number_br)
            st.dataframe(alocados[["Classificação", "estrategia", "Valor Atual (R$)", "Valor Realocado (R$)", "Novo Valor (R$)"]],
                         use_container_width=True, hide_index=True)
        else:
            st.markdown("_Nenhum ativo alocado._")
        st.subheader("Ativos Resgatados")
        resgatados = ativos_df[pd.to_numeric(ativos_df["Valor Realocado"], errors="coerce").fillna(0.0) < 0].copy()  # alteração realizada aqui
        if not resgatados.empty:
            for c in ["valor_atual", "Novo Valor", "Valor Realocado"]:
                resgatados[c] = pd.to_numeric(resgatados[c], errors="coerce").fillna(0.0)
            resgatados["Valor Atual (R$)"]     = resgatados["valor_atual"].apply(format_number_br)
            resgatados["Novo Valor (R$)"]      = resgatados["Novo Valor"].apply(format_number_br)
            resgatados["Valor Realocado (R$)"] = resgatados["Valor Realocado"].apply(format_number_br)
            st.dataframe(resgatados[["Classificação", "estrategia", "Valor Atual (R$)", "Valor Realocado (R$)", "Novo Valor (R$)"]],
                         use_container_width=True, hide_index=True)
        else:
            st.markdown("_Nenhum ativo resgatado._")
    else:
        st.warning("Coluna 'Valor Realocado' não encontrada. Volte à etapa 4 para simular os ajustes.")

    # === LIQUIDEZ POR FAIXAS ===
    st.subheader("Liquidez da carteira (R$) por Faixas")
    def extract_days(liq):
        m = re.search(r"D\+(\d+)", str(liq))
        return int(m.group(1)) if m else None
    ativos_df["days"] = ativos_df["Liquidez"].apply(extract_days)
    def classify_faixa(row):
        d = row["days"]
        liq = str(row["Liquidez"]).lower()
        if d is None:
            return "D+0"  # fallback  # alteração realizada aqui
        if d > 180: return "Acima de D+180"
        if d > 60:  return "Até D+180"
        if d > 15:  return "Até D+60"
        if d > 5:   return "Até D+15"
        if d > 0:   return "Até D+5"
        if d == 0 and "à mercado" in liq: return "D+0 (à mercado)"
        return "D+0"
    ativos_df["Faixa"] = ativos_df.apply(classify_faixa, axis=1)
    liq_faixas = ativos_df.groupby("Faixa")["valor_atual"].sum().reset_index()

    # ordem invertida
    ordem = [
        "D+0 (à mercado)",
        "D+0",
        "Até D+5",
        "Até D+15",
        "Até D+60",
        "Até D+180",
        "Acima de D+180"
    ]
    liq_faixas["Faixa"] = pd.Categorical(liq_faixas["Faixa"], categories=ordem, ordered=True)
    liq_faixas = liq_faixas.sort_values("Faixa")

    fig_liq = px.bar(
        liq_faixas,
        x="valor_atual",
        y="Faixa",
        orientation="h",
        text="valor_atual"
    )
    fig_liq.update_traces(texttemplate="%{text:,.2f}", textposition="outside")
    fig_liq.update_layout(
        separators=".,",
        yaxis=dict(categoryorder="array", categoryarray=ordem)
    )
    st.plotly_chart(fig_liq, use_container_width=True)

    # === PREPARO DE DATAFRAMES PARA O PDF ===
    modelo_raw = get_modelo_carteira(carteira_modelo)
    if isinstance(modelo_raw, dict):
        modelo_df = pd.DataFrame([modelo_raw])
    else:
        modelo_df = modelo_raw.copy()

    # tenta identificar coluna de percentual ideal
    percent_cols = [c for c in modelo_df.columns if "percentual" in c.lower()]
    if percent_cols:
        modelo_df = modelo_df.rename(columns={percent_cols[0]: "Percentual Ideal"})
    else:
        # fallback: usa dist_sug já calculado
        modelo_df = dist_sug.rename(columns={"Percentual": "Percentual Ideal", "valor_sugerido": "valor"})[["Classificação", "valor", "Percentual Ideal"]]

    dist_df = dist_atual.rename(columns={"valor_atual": "valor"})

    # === GERAÇÃO E DOWNLOAD DO PDF ===
    # alteração realizada aqui: agora generate_pdf devolve bytes (sem gravar em disco)
    pdf_bytes = generate_pdf(
        dist_df=dist_df,
        modelo_df=modelo_df,
        resumo_df=res_df,
        sugestao=sugestao,
        ativos_df=ativos_df,
        cliente_nome=cliente_nome or "",
        nome_assessor=nome_assessor or "",
    )
    st.download_button("Gerar e Baixar PDF", pdf_bytes, "relatorio_carteira.pdf", "application/pdf")  # alteração realizada aqui

    # === DOWNLOAD DO EXCEL ===
    excel1 = ativos_df.copy()
    excel1["Valor Atual (R$)"] = excel1["valor_atual"].apply(format_number_br)
    total_atual = float(excel1["valor_atual"].sum())
    excel1["Percentual (%)"] = excel1["valor_atual"].apply(lambda x: format_number_br((x/total_atual*100) if total_atual else 0) + "%")
    excel1_export = excel1[["Classificação", "estrategia", "Liquidez", "Valor Atual (R$)", "Percentual (%)"]].sort_values("Classificação")

    excel2 = ativos_df.copy()
    total_sug = float(excel2["Novo Valor"].sum())
    excel2["Valor Sugerido (R$)"] = excel2["Novo Valor"].apply(format_number_br)
    excel2["Percentual Ideal (%)"] = excel2["Novo Valor"].apply(lambda x: format_number_br((x/total_sug*100) if total_sug else 0) + "%")
    excel2_export = excel2[["Classificação", "estrategia", "Liquidez", "Valor Sugerido (R$)", "Percentual Ideal (%)"]].sort_values("Classificação")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        excel1_export.to_excel(writer, sheet_name='Carteira Inicial', index=False)
        excel2_export.to_excel(writer, sheet_name='Carteira Sugerida', index=False)
    output.seek(0)
    st.download_button(
        label="Baixar Carteiras (Excel)",
        data=output,
        file_name="carteiras.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # botão voltar
    if st.button("Voltar para Sugestões"):
        st.session_state.etapa = 4
        st.rerun()
