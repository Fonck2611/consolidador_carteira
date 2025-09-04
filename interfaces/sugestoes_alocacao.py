import streamlit as st
import pandas as pd
from utils.carteiras_modelo import get_modelo_carteira
import re

# Formata valores financeiros no padrão brasileiro
def format_valor_br(valor):
    s = f"{valor:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def _parse_br_money(x):
    """Converte '1.234,56' / 'R$ 1.234,56' / 1234.56 para float."""
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace(" ", "")
    # remove milhares e ajeita decimal
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def show():
    st.header("4. Sugestões de Ajustes na Alocação")

    ativos_raw           = st.session_state.get("ativos_df", [])
    carteira_modelo_tipo = st.session_state.get("carteira_modelo")
    if not ativos_raw or not carteira_modelo_tipo:
        st.error("Informações incompletas. Volte para as etapas anteriores.")
        return

    # Lê o aporte do session_state (se houver)
    sug = dict(st.session_state.get("sugestao", {}))
    aporte = 0.0
    if "aporte_valor" in sug:
        aporte = _parse_br_money(sug.get("aporte_valor"))
    elif "aporte_text" in sug:
        aporte = _parse_br_money(sug.get("aporte_text"))
    if aporte < 0:
        aporte = 0.0

    ativos_df = pd.DataFrame(ativos_raw)
    liq_map = dict(zip(ativos_df["estrategia"], ativos_df["Liquidez"]))

    modelo = (
        get_modelo_carteira(carteira_modelo_tipo)
        if carteira_modelo_tipo != "Personalizada"
        else st.session_state.get("modelo_personalizado_dict", {})
    )

    # Distribuição atual (inicial)
    dist = (
        ativos_df.groupby("Classificação")["saldo_bruto"]
        .sum()
        .reset_index()
        .rename(columns={"saldo_bruto": "Valor"})
    )
    total_atual = float(dist["Valor"].sum())
    dist["Percentual"] = dist["Valor"] / total_atual * 100 if total_atual else 0.0

    # === Ajustes por classe (BASE = total_atual + APORTE) ===
    base_total = total_atual + aporte
    ajustes = {}
    for cls in set(dist["Classificação"]) | set(modelo.keys()):
        valor_atual_classe = float(dist.loc[dist["Classificação"] == cls, "Valor"].sum())
        pct_modelo = float(modelo.get(cls, 0.0))
        alvo_classe = (pct_modelo / 100.0) * base_total
        ajustes[cls] = alvo_classe - valor_atual_classe  # pode ser + ou -

    # Totais
    total_alocar  = sum(v for v in ajustes.values() if v > 0)         # inclui o aporte
    total_reduzir = sum(abs(v) for v in ajustes.values() if v < 0)
    delta_diff = (total_alocar - total_reduzir) - aporte
    # Ajuste fino de flutuação
    if abs(delta_diff) > 1e-6:
        pos_items = [(c, v) for c, v in ajustes.items() if v > 0]
        if pos_items:
            cmax, vmax = max(pos_items, key=lambda x: x[1])
            novo = vmax - delta_diff
            ajustes[cmax] = max(novo, 0.0)
            total_alocar  = sum(v for v in ajustes.values() if v > 0)
            total_reduzir = sum(abs(v) for v in ajustes.values() if v < 0)

    # Ordem de exibição das classes
    aumentos        = [c for c, v in sorted(ajustes.items(), key=lambda x: x[1], reverse=True) if v > 0]
    reducoes        = [c for c, v in sorted(ajustes.items(), key=lambda x: x[1]) if v < 0]
    inalterados     = [c for c, v in ajustes.items() if abs(v) < 1e-9]
    classes_ordered = aumentos + reducoes + inalterados

    st.subheader(f"Total a alocar (inclui aporte): R$ {format_valor_br(total_alocar)}")
    st.caption(f"Aporte: R$ {format_valor_br(aporte)}")

    if "open_classes" not in st.session_state:
        st.session_state.open_classes = {}

    # Inicializa o editor para cada classe
    for cls in classes_ordered:
        key = f"editor_df_{cls}"
        if key not in st.session_state:
            df0 = ativos_df[ativos_df["Classificação"] == cls][["estrategia", "saldo_bruto"]].copy()
            df0.columns = ["Ativo", "Valor Atual"]
            df0["Valor Realocado"] = 0.0
            df0["Novo Valor"]      = df0["Valor Atual"]
            df0["Liquidez"]        = df0["Ativo"].map(liq_map)
            st.session_state[key] = df0.reset_index(drop=True)

    # ===== total novo global (para % ajustado de cada classe)
    total_novo_global = 0.0
    for cls in classes_ordered:
        df_cls = st.session_state.get(f"editor_df_{cls}")
        if df_cls is not None:
            # garante consistência
            nv = pd.to_numeric(df_cls["Valor Atual"], errors="coerce").fillna(0.0) + \
                 pd.to_numeric(df_cls["Valor Realocado"], errors="coerce").fillna(0.0)
            total_novo_global += float(nv.sum())

    # Exibe/edita cada classe
    for cls in classes_ordered:
        key = f"editor_df_{cls}"
        df_current = st.session_state[key].reset_index(drop=True)
        st.session_state[key] = df_current

        # Tipos
        df_current["Valor Atual"]     = pd.to_numeric(df_current["Valor Atual"], errors="coerce").fillna(0.0)
        df_current["Valor Realocado"] = pd.to_numeric(df_current["Valor Realocado"], errors="coerce").fillna(0.0)
        df_current["Novo Valor"]      = df_current["Valor Atual"] + df_current["Valor Realocado"]
        df_current["Liquidez"]        = df_current["Ativo"].map(liq_map).apply(lambda x: re.sub(r"D\+ ?", "", str(x)))
        df_current = df_current[["Ativo", "Liquidez", "Valor Atual", "Valor Realocado", "Novo Valor"]]

        soma_realocado_classe = float(df_current["Valor Realocado"].sum())
        restante_classe       = float(ajustes.get(cls, 0.0) - soma_realocado_classe)

        pct_atual  = float(dist.loc[dist["Classificação"] == cls, "Percentual"].sum())
        pct_modelo = float(modelo.get(cls, 0.0))
        class_total_inicial = float(dist.loc[dist["Classificação"] == cls, "Valor"].sum())

        total_ajustado_classe = float(df_current["Novo Valor"].sum())
        pct_ajustado_classe = (total_ajustado_classe / total_novo_global * 100.0) if total_novo_global else 0.0
        pct_ajustado_fmt = f"{pct_ajustado_classe:.2f}".replace(".", ",") + "%"

        # Mensagem por classe
        if abs(restante_classe) < 1e-2:
            if abs(soma_realocado_classe) < 1e-2:
                texto, color, simbolo = "Inalterado", "#000", ""
            elif soma_realocado_classe < 0:
                texto, color, simbolo = "Reduzir R$ 0,00", "red", "⬇️"
            else:
                texto, color, simbolo = "Aumentar R$ 0,00", "green", "⬆️"
        else:
            if restante_classe > 0:
                texto, color, simbolo = f"Aumentar R$ {format_valor_br(restante_classe)}", "green", "⬆️"
            else:
                texto, color, simbolo = f"Reduzir R$ {format_valor_br(abs(restante_classe))}", "red", "⬇️"

        cols = st.columns([8, 1])
        with cols[0]:
            st.markdown(f"""
                <div style='border:1px solid #000; padding:15px; border-radius:10px; margin-bottom:10px; background:#fff;'>
                    <span style='font-size:16px;'>{simbolo} {cls}</span><br>
                    <span style='color:gray'>{pct_atual:.2f}% → {pct_modelo:.2f}%</span><br>
                    <span style='color:gray'>Total da classe (inicial): R$ {format_valor_br(class_total_inicial)}</span><br>
                    <span style='color:gray; font-weight:bold'>Total ajustado (classe): R$ {format_valor_br(total_ajustado_classe)}</span><br>
                    <span style='color:gray'>Percentual ajustado (classe): {pct_ajustado_fmt}</span><br>
                    <span style='color:{color}; font-weight:bold'>{texto}</span>
                </div>
            """, unsafe_allow_html=True)
        with cols[1]:
            if st.button("🔍", key=f"toggle_{cls}"):
                st.session_state.open_classes[cls] = not st.session_state.open_classes.get(cls, False)
                st.rerun()

        if st.session_state.open_classes.get(cls, False):
            prev   = df_current.copy()
            edited = st.data_editor(
                df_current,
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
            # recalcula
            edited["Valor Atual"]     = pd.to_numeric(edited["Valor Atual"], errors="coerce").fillna(0.0)
            edited["Valor Realocado"] = pd.to_numeric(edited["Valor Realocado"], errors="coerce").fillna(0.0)
            edited["Novo Valor"]      = edited["Valor Atual"] + edited["Valor Realocado"]

            if any(prev.at[idx, "Valor Realocado"] != edited.at[idx, "Valor Realocado"]
                   for idx in edited.index if idx in prev.index):
                st.session_state[key] = edited
                st.rerun()
            else:
                st.session_state[key] = edited

    # ================= Saldo restante do APORTE =================
    soma_novo_total = sum(
        float(st.session_state[f"editor_df_{cls}"]["Novo Valor"].sum()) for cls in classes_ordered
    )
    saldo_restante = aporte - (soma_novo_total - total_atual)

    st.subheader(f"Saldo restante: R$ {format_valor_br(saldo_restante)}")
    if abs(saldo_restante) > 0.01:
        st.warning("Distribua o aporte entre os ativos até que o saldo restante zere (0,00).")

    botao_disabled = bool(abs(saldo_restante) > 0.01)

    if st.button("Avançar para Confirmação e Geração do PDF", disabled=botao_disabled):
        novos_ativos = []
        for cls in classes_ordered:
            df_cls = st.session_state[f"editor_df_{cls}"]
            for _, r in df_cls.iterrows():
                liqui = str(r["Liquidez"]).strip()
                if liqui == "No Vencimento":
                    liqui_out = "No Vencimento"
                else:
                    liqui_out = f"D+{liqui}" if liqui and not liqui.startswith("D+") else liqui

                novos_ativos.append({
                    "estrategia":       r["Ativo"],
                    "saldo_bruto":      float(r["Valor Atual"]),
                    "Novo Valor":       float(r["Novo Valor"]),
                    "Valor Realocado":  float(r["Valor Realocado"]),
                    "Classificação":    cls,
                    "Liquidez":         liqui_out
                })
        st.session_state.ativos_df = novos_ativos

        # garante que o aporte siga adiante nas próximas telas
        sug_out = dict(st.session_state.get("sugestao", {}))
        sug_out["aporte_valor"] = aporte
        if "aporte_text" not in sug_out:
            sug_out["aporte_text"] = format_valor_br(aporte)
        st.session_state.sugestao = sug_out

        st.session_state.etapa = 5
        st.rerun()
