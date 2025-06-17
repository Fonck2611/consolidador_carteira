import streamlit as st
import pandas as pd
import re
from datetime import date
from pathlib import Path  # alteração realizada aqui: para construir caminho relativo

def sql_get_df():
    """
    Lê o arquivo liquidez_ativos.xlsx que fica na mesma pasta deste script.
    """
    # alteração realizada aqui: determina o diretório deste arquivo
    script_dir = Path(__file__).parent
    file_path = script_dir / "liquidez_ativos.xlsx"
    
    try:
        # alteração realizada aqui: lendo do caminho correto
        df = pd.read_excel(
            file_path,
            dtype={"ativo": str, "liquidez": str, "vencimento": str}
        )
    except Exception as e:
        # alteração realizada aqui: loga o caminho e o erro
        print(f"sql_get_df – não encontrou o arquivo em {file_path}: {e}")
        df = pd.DataFrame(columns=["ativo", "liquidez", "vencimento"])
    return df

def format_valor_br(valor):
    s = f"{valor:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def show():
    st.header("2. Detalhamento e Classificação dos Ativos")
    ativos_raw = st.session_state.get("ativos_df")
    if not ativos_raw:
        st.warning("Nenhum ativo carregado. Volte para a Etapa 1.")
        return

    df = pd.DataFrame(ativos_raw).copy()
    if df.empty:
        st.warning("A lista de ativos está vazia.")
        return

    # Garante coluna de Classificação
    if "Classificação" not in df.columns:
        df["Classificação"] = df.get("classificacao", "")

    # 1) Puxa liquidez do SQL
    df_sql = sql_get_df()
    liq_map = dict(zip(df_sql["ativo"], df_sql["liquidez"]))
    # Aplica liquidez do SQL ou vazio
    df["Liquidez"] = df["estrategia"].map(liq_map).fillna("")

    # 2) Fallback MMM/YYYY para D+X (dia 15 do mês)
    month_map = {
        "JAN":1, "FEV":2, "MAR":3, "ABR":4, "MAI":5, "JUN":6,
        "JUL":7, "AGO":8, "SET":9, "OUT":10, "NOV":11, "DEZ":12
    }
    today = date.today()
    def calc_fallback(estrat: str) -> str:
        m = re.search(r"([A-Za-z]{3})/(\d{4})", estrat)
        if not m:
            return ""
        abbr, ano = m.group(1).upper(), int(m.group(2))
        mes = month_map.get(abbr)
        if not mes:
            return ""
        alvo = date(ano, mes, 15)
        dias = (alvo - today).days
        return f"D+{dias}"

    # 3) Regras adicionais de fallback
    def compute_liq(r):
        # valor do SQL
        if r["Liquidez"]:
            return r["Liquidez"]
        # fallback MMM/YYYY
        fb = calc_fallback(r["estrategia"])
        if fb:
            return fb
        # sufixos específicos -> D+2
        if re.search(r"(?:3|4|11|34|39)$", str(r["estrategia"])):
            return "D+2"
        # se contém "Tesouro" -> D+0
        if "tesouro" in str(r["estrategia"]).lower():
            return "D+0 (à mercado)"
        return ""

    df["Liquidez"] = df.apply(compute_liq, axis=1)

    detalhes_visiveis = st.session_state.setdefault("detalhes_visiveis", {})

    # Cabeçalho com nova coluna Liquidez
    header_cols = st.columns([0.5, 5, 2, 3, 2], gap="small")
    header_cols[0].write("")
    header_cols[1].markdown("**Ativo**")
    header_cols[2].markdown("**Valor**")
    header_cols[3].markdown("**Classificação**")
    header_cols[4].markdown("**Liquidez**")
    st.markdown("---")

    classificacoes = [
        "Pós Fixado", "Inflação", "Pré Fixado", "Multimercado",
        "Renda Variável Brasil", "Alternativo", "Renda Variável Global",
        "Renda Fixa Global", "Fundos Listados", "Caixa"
    ]

    novos = []
    for i, row in df.iterrows():
        cols = st.columns([0.5, 5, 2, 3, 2], gap="small")

        # Lupa de detalhes
        with cols[0]:
            if st.button("🔍", key=f"mostrar_{i}"):
                detalhes_visiveis[i] = not detalhes_visiveis.get(i, False)
                st.session_state.detalhes_visiveis = detalhes_visiveis
                st.rerun()

        # Ativo e valor
        cols[1].write(row["estrategia"])
        valor = row.get("saldo_bruto", 0.0)
        cols[2].write(f"R$ {format_valor_br(valor)}")

        # Classificação editável
        key_cls = f"classificacao_{i}"
        curr = st.session_state.get(key_cls, row["Classificação"])
        idx = classificacoes.index(curr) if curr in classificacoes else 0
        nova_cls = cols[3].selectbox(
            label="Classificação",
            options=classificacoes,
            index=idx,
            key=key_cls,
            label_visibility="collapsed"
        )

        # Liquidez editável como texto (mantém D+x)
        key_liq = f"liquidez_{i}"
        default_liq = row["Liquidez"]
        nova_liq = cols[4].text_input(
            label="Liquidez",
            value=default_liq,
            key=key_liq,
            label_visibility="collapsed"
        )

        rec = row.to_dict()
        rec["Classificação"] = nova_cls
        rec["Liquidez"] = nova_liq
        novos.append(rec)

        # Detalhes expandidos
        if detalhes_visiveis.get(i, False):
            with st.container():
                info = {
                    "Quantidade": row.get("quantidade", 0),
                    "Rentabilidade no Mês": row.get("rentabilidade_mes_atual", 0),
                    "%CDI no Mês": row.get("porcentagem_cdi_mes_atual", 0),
                    "Rentabilidade no Ano": row.get("rentabilidade_ano", 0),
                    "%CDI no Ano": row.get("porcentagem_cdi_ano", 0),
                    "Rentabilidade Últimos 24 meses": row.get("rentabilidade_24m", 0),
                    "%CDI Últimos 24 meses": row.get("porcentagem_cdi_24m", 0),
                    "Banco": row.get("Banco", "")
                }
                st.markdown("<div style='margin-left:40px;'>", unsafe_allow_html=True)
                for label, val in info.items():
                    if isinstance(val, (int, float)):
                        txt = format_valor_br(val) + ("%" if "%" in label else "")
                    else:
                        txt = val
                    st.markdown(
                        f"<p style='margin:2px 0;'><strong>{label}:</strong> {txt}</p>",
                        unsafe_allow_html=True
                    )
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")

    st.session_state.ativos_df = pd.DataFrame(novos).to_dict("records")

    if st.button("Avançar para Comparação com Carteira Modelo"):
        if all(r["Classificação"] for r in novos):
            st.session_state.etapa = 3
            st.rerun()
        else:
            st.warning("Preencha a classificação de todos os ativos antes de avançar.")