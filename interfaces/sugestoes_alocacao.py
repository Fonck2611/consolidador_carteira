import streamlit as st
import pandas as pd
from utils.carteiras_modelo import get_modelo_carteira
import re

# ---- helpers ----
def format_valor_br(valor):
    s = f"{valor:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def _parse_br_money(x):
    """
    Converte 'R$ 1.234,56' -> 1234.56. Aceita float/int, string BR/US.
    """
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("R$", "").replace(" ", "")
    if s == "":
        return 0.0
    # remove separador de milhar e troca decimal
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def show():
    st.header("4. Sugestões de Ajustes na Alocação")

    # ------------------ dados base ------------------
    ativos_raw           = st.session_state.get("ativos_df", [])
    carteira_modelo_tipo = st.session_state.get("carteira_modelo")
    if not ativos_raw or not carteira_modelo_tipo:
        st.error("Informações incompletas. Volte para as etapas anteriores.")
        return

    # aporte (propagado da etapa 2/3)
    sug = dict(st.session_state.get("sugestao", {}))
    aporte_valor = sug.get("aporte_valor", st.session_state.get("aporte_valor", 0.0))
    if not aporte_valor and sug.get("aporte_text"):
        aporte_valor = _parse_br_money(sug["aporte_text"])
    aporte_valor = max(0.0, float(aporte_valor or 0.0))  # garante não-negativo

    # dataframe de trabalho
    ativos_df = pd.DataFrame(ativos_raw)
    # mapeia liquidez por estratégia (para reaplicar)
    liq_map = dict(zip(ativos_df["estrategia"], ativos_df.get("Liquidez", "")))

    # modelo alvo
    modelo = (
        get_modelo_carteira(carteira_modelo_tipo)
        if carteira_modelo_tipo != "Personalizada"
        else st.session_state.get("modelo_personalizado_dict", {})
    )

    # ------------------ distribuição atual e alvo ------------------
    dist = (
        ativos_df.groupby("Classificação")["saldo_bruto"]
        .sum()
        .reset_index()
        .rename(columns={"saldo_bruto": "Valor"})
    )
    total_atual = float(dist["Valor"].sum())
    base_total  = total_atual + aporte_valor  # << considera aporte em todas as contas de percentual

    # % atual (considerando aporte no denominador)
    # Obs: no começo os % somam < 100% (porque o aporte ainda não está alocado)
    dist["PercentualAtual"] = dist["Valor"] / base_total * 100 if base_total > 0 else 0.0

    # alvo monetário por classe (modelo% * (total_atual + aporte))
    alvo_por_cls = {cls: (modelo.get(cls, 0.0) / 100.0) * base_total for cls in set(dist["Classificação"]) | set(modelo.keys())}
    atual_por_cls = dict(zip(dist["Classificação"], dist["Valor"]))
    for cls in alvo_por_cls.keys():
        if cls not in atual_por_cls:
            atual_por_cls[cls] = 0.0

    # diferença alvo - atual (só para ordenar/guia)
    deltas_iniciais = {cls: (alvo_por_cls[cls] - atual_por_cls[cls]) for cls in alvo_por_cls.keys()}
    aumentos    = [c for c, v in sorted(deltas_iniciais.items(), key=lambda x: x[1], reverse=True) if v > 0]
    reducoes    = [c for c, v in sorted(deltas_iniciais.items(), key=lambda x: x[1]) if v < 0]
    inalterados = [c for c, v in deltas_iniciais.items() if abs(v) < 1e-9]
    classes_ordered = aumentos + reducoes + inalterados

    # ------------------ topo da tela ------------------
    st.subheader(f"Aporte informado: R$ {format_valor_br(aporte_valor)}")
    st.caption("Distribua o aporte entre os ativos nas classes abaixo. O total a alocar deve bater exatamente com o aporte.")

    # estado: visibilidade de editores
    if "open_classes" not in st.session_state:
        st.session_state.open_classes = {}

    # inicializa dataframes por classe (editor)
    for cls in classes_ordered:
        key = f"editor_df_{cls}"
        if key not in st.session_state:
            df0 = ativos_df[ativos_df["Classificação"] == cls][["estrategia", "saldo_bruto"]].copy()
            df0.columns = ["Ativo", "Valor Atual"]
            df0["Valor Realocado"] = 0.0     # aqui o usuário coloca o que quer adicionar/retirar
            df0["Novo Valor"]      = df0["Valor Atual"]  # Valor Atual + Valor Realocado
            # mostra "Liquidez" apenas como visual, editável (sem D+ no campo)
            df0["Liquidez"]        = df0["Ativo"].map(liq_map).apply(lambda x: re.sub(r"D\+ ?", "", str(x)))
            st.session_state[key]  = df0.reset_index(drop=True)

    # ------------------ edição por classe ------------------
    for cls in classes_ordered:
        key = f"editor_df_{cls}"
        df_current = st.session_state[key].reset_index(drop=True)

        # tipos numéricos consistentes
        df_current["Valor Atual"]     = pd.to_numeric(df_current["Valor Atual"], errors="coerce").fillna(0.0)
        df_current["Valor Realocado"] = pd.to_numeric(df_current["Valor Realocado"], errors="coerce").fillna(0.0)
        df_current["Novo Valor"]      = df_current["Valor Atual"] + df_current["Valor Realocado"]

        # métricas da classe
        soma_realocado = float(df_current["Valor Realocado"].sum())
        total_atual_cls = float(atual_por_cls.get(cls, 0.0))
        alvo_cls        = float(alvo_por_cls.get(cls, 0.0))
        restante_cls    = alvo_cls - (total_atual_cls + soma_realocado)

        # % atual (denominador com aporte) e alvo
        pct_atual_cls  = (total_atual_cls / base_total * 100) if base_total > 0 else 0.0
        pct_modelo_cls = float(modelo.get(cls, 0.0))
        pct_proj_cls   = ((total_atual_cls + soma_realocado) / base_total * 100) if base_total > 0 else 0.0

        # mensagem amigável
        if abs(restante_cls) < 0.01:
            if soma_realocado > 0:
                texto, color, simbolo = "Aumento ok", "green", "✅"
            elif soma_realocado < 0:
                texto, color, simbolo = "Redução ok", "red", "✅"
            else:
                texto, color, simbolo = "Inalterado", "#6B7280", "•"
        else:
            if restante_cls > 0:
                texto, color, simbolo = f"Aumentar R$ {format_valor_br(restante_cls)}", "green", "⬆️"
            else:
                texto, color, simbolo = f"Reduzir R$ {format_valor_br(abs(restante_cls))}", "red", "⬇️"

        cols = st.columns([8, 1])
        with cols[0]:
            st.markdown(f"""
                <div style='border:1px solid #D1D5DB; padding:15px; border-radius:10px; margin-bottom:10px; background:#fff;'>
                    <div style='font-size:16px; font-weight:600;'>{cls}</div>
                    <div style='color:gray'>
                        {pct_atual_cls:.2f}% → {pct_modelo_cls:.2f}% (proj.: {pct_proj_cls:.2f}%)
                    </div>
                    <div style='color:gray'>Total atual da classe: R$ {format_valor_br(total_atual_cls)}</div>
                    <div style='color:gray; font-weight:bold'>Total ajustado da classe: R$ {format_valor_br(df_current["Novo Valor"].sum())}</div>
                    <div style='color:{color}; font-weight:bold; margin-top:6px;'>{simbolo} {texto}</div>
                </div>
            """, unsafe_allow_html=True)
        with cols[1]:
            if st.button("🔍", key=f"toggle_{cls}"):
                st.session_state.open_classes[cls] = not st.session_state.open_classes.get(cls, False)
                st.rerun()

        # editor de linhas da classe
        if st.session_state.open_classes.get(cls, False):
            prev   = df_current.copy()
            edited = st.data_editor(
                df_current[["Ativo", "Liquidez", "Valor Atual", "Valor Realocado", "Novo Valor"]],
                hide_index=True,
                num_rows="dynamic",
                column_config={
                    "Ativo":            st.column_config.TextColumn(label="Ativo"),
                    "Liquidez":         st.column_config.TextColumn(label="Liquidez"),
                    "Valor Atual":      st.column_config.NumberColumn(label="Valor Atual", disabled=True),
                    "Valor Realocado":  st.column_config.NumberColumn(label="Valor Realocado"),
                    "Novo Valor":       st.column_config.NumberColumn(label="Novo Valor", disabled=True)
                },
                use_container_width=True,
                key=f"editor_{cls}"
            )
            # recálculo
            edited["Valor Atual"]     = pd.to_numeric(edited["Valor Atual"], errors="coerce").fillna(0.0)
            edited["Valor Realocado"] = pd.to_numeric(edited["Valor Realocado"], errors="coerce").fillna(0.0)
            edited["Novo Valor"]      = edited["Valor Atual"] + edited["Valor Realocado"]

            # persistência
            if any(prev.at[idx, "Valor Realocado"] != edited.at[idx, "Valor Realocado"]
                   for idx in edited.index if idx in prev.index):
                st.session_state[key] = edited
                st.rerun()
            else:
                st.session_state[key] = edited

    # ------------------ validações globais ------------------
    # soma dos realocados POSITIVOS (tem que bater o aporte)
    soma_pos_realocados = 0.0
    soma_novo_total     = 0.0
    any_novo_negativo   = False

    for cls in classes_ordered:
        df_cls = st.session_state[f"editor_df_{cls}"]
        soma_pos_realocados += float(df_cls["Valor Realocado"].clip(lower=0).sum())
        soma_novo_total     += float(df_cls["Novo Valor"].sum())
        if (df_cls["Novo Valor"] < 0).any():
            any_novo_negativo = True

    # Saldo restante = aporte - (somatório dos realocados positivos)
    saldo_restante = aporte_valor - soma_pos_realocados

    st.subheader(f"Total a alocar (aporte): R$ {format_valor_br(aporte_valor)}")
    st.subheader(f"Saldo Restante: R$ {format_valor_br(saldo_restante)}")

    # mensagens
    if aporte_valor > 0 and abs(saldo_restante) > 0.01:
        st.warning("Distribua o aporte entre os ativos até o Saldo Restante chegar a zero.")
    if any_novo_negativo:
        st.error("Há ativo(s) com Novo Valor negativo. Ajuste os valores realocados.")

    # regra para habilitar botão:
    # - se aporte > 0: exigir saldo_restante == 0
    # - se aporte == 0: exigir que a soma dos realocados seja 0 (automaticamente saldo_restante == 0)
    pode_avancar = (abs(saldo_restante) <= 0.01) and not any_novo_negativo

    # ------------------ avançar ------------------
    if st.button("Avançar para Confirmação e Geração do PDF", disabled=not pode_avancar):
        novos_ativos = []
        for cls in classes_ordered:
            df_cls = st.session_state[f"editor_df_{cls}"].copy()
            # normaliza Liquidez: se "No Vencimento" mantém, senão prefixa D+
            for _, r in df_cls.iterrows():
                liq_raw = str(r["Liquidez"]).strip()
                liq_fmt = liq_raw if liq_raw == "No Vencimento" else f"D+{liq_raw}" if liq_raw != "" else ""
                novos_ativos.append({
                    "estrategia":       r["Ativo"],
                    "saldo_bruto":      float(r["Valor Atual"]),
                    "Valor Realocado":  float(r["Valor Realocado"]),
                    "Novo Valor":       float(r["Novo Valor"]),
                    "Classificação":    cls,
                    "Liquidez":         liq_fmt
                })

        # salva para a etapa 5
        st.session_state.ativos_df = novos_ativos

        # garante que o aporte fique disponível adiante
        sug["aporte_valor"] = aporte_valor
        if "aporte_text" in st.session_state and st.session_state["aporte_text"]:
            sug["aporte_text"] = st.session_state["aporte_text"]
        st.session_state.sugestao = sug

        st.session_state.etapa = 5
        st.rerun()
