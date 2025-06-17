import streamlit as st
import pandas as pd
from utils.carteiras_modelo import get_modelo_carteira

# Formata valores financeiros no padrão brasileiro
def format_valor_br(valor):
    s = f"{valor:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def show():
    st.header("4. Sugestões de Ajustes na Alocação")

    ativos_raw           = st.session_state.get("ativos_df", [])
    carteira_modelo_tipo = st.session_state.get("carteira_modelo")
    if not ativos_raw or not carteira_modelo_tipo:
        st.error("Informações incompletas. Volte para as etapas anteriores.")
        return

    ativos_df = pd.DataFrame(ativos_raw)
    # guarda liquidez para repassar depois, sem mostrar na tabela
    liq_map   = dict(zip(ativos_df["estrategia"], ativos_df["Liquidez"]))

    modelo = (
        get_modelo_carteira(carteira_modelo_tipo)
        if carteira_modelo_tipo != "Personalizada"
        else st.session_state.get("modelo_personalizado_dict", {})
    )

    # Distribuição atual e cálculo dos ajustes
    dist = (
        ativos_df.groupby("Classificação")["saldo_bruto"]
        .sum()
        .reset_index()
        .rename(columns={"saldo_bruto": "Valor"})
    )
    total_atual = dist["Valor"].sum()
    dist["Percentual"] = dist["Valor"] / total_atual * 100

    ajustes = {}
    for cls in set(dist["Classificação"]) | set(modelo.keys()):
        pct_atual  = dist.loc[dist["Classificação"] == cls, "Percentual"].sum()
        pct_modelo = modelo.get(cls, 0)
        ajustes[cls] = (pct_modelo - pct_atual) / 100 * total_atual

    # Ajuste de arredondamento
    total_alocar = sum(v for v in ajustes.values() if v > 0)
    total_reduzir = sum(abs(v) for v in ajustes.values() if v < 0)
    delta = total_alocar - total_reduzir
    if abs(delta) > 1e-6:
        cmax, _ = max(((c,v) for c,v in ajustes.items() if v>0), key=lambda x: x[1], default=(None,0))
        if cmax:
            ajustes[cmax] -= delta

    # Ordem de exibição das classes
    aumentos       = [c for c,v in sorted(ajustes.items(), key=lambda x: x[1], reverse=True) if v>0]
    reducoes       = [c for c,v in sorted(ajustes.items(), key=lambda x: x[1]) if v<0]
    inalterados    = [c for c,v in ajustes.items() if abs(v)<1e-9]
    classes_ordered = aumentos + reducoes + inalterados

    st.subheader(f"Total a realocar: R$ {format_valor_br(total_alocar)}")
    if "open_classes" not in st.session_state:
        st.session_state.open_classes = {}

    # Inicializa o editor para cada classe
    for cls in classes_ordered:
        key = f"editor_df_{cls}"
        if key not in st.session_state:
            df0 = ativos_df[ativos_df["Classificação"] == cls][
                ["estrategia", "saldo_bruto"]
            ].copy()
            df0.columns = ["Ativo", "Valor Atual"]
            df0["Valor Realocado"] = 0.0
            df0["Novo Valor"]      = df0["Valor Atual"]
            df0["Liquidez"]        = df0["Ativo"].map(liq_map)  # adicionado campo de liquidez
            st.session_state[key] = df0.reset_index(drop=True)

    # Exibe e edita cada classe
    for cls in classes_ordered:
        key = f"editor_df_{cls}"
        df_current = st.session_state[key].reset_index(drop=True)
        st.session_state[key] = df_current

        # Garante tipos numéricos
        df_current["Valor Atual"]     = pd.to_numeric(df_current["Valor Atual"], errors="coerce").fillna(0)
        df_current["Valor Realocado"] = pd.to_numeric(df_current["Valor Realocado"], errors="coerce").fillna(0)
        df_current["Novo Valor"]      = df_current["Valor Atual"] + df_current["Valor Realocado"]
        df_current["Liquidez"]        = df_current["Ativo"].map(liq_map)  # garantir que esteja no dataframe
        df_current = df_current[["Ativo", "Liquidez", "Valor Atual", "Valor Realocado", "Novo Valor"]]  # forçar ordem

        soma_realocado = df_current["Valor Realocado"].sum()
        restante       = ajustes.get(cls, 0) - soma_realocado

        pct_atual  = dist.loc[dist["Classificação"] == cls, "Percentual"].sum()
        pct_modelo = modelo.get(cls, 0)
        class_total = dist.loc[dist["Classificação"] == cls, "Valor"].sum()

        # Mensagem de ajuste
        if abs(restante) < 1e-2:
            if soma_realocado == 0:
                texto, color, simbolo = "Inalterado", "#000", ""
            elif soma_realocado < 0:
                texto, color, simbolo = "Reduzir R$ 0,00", "red", "⬇️"
            else:
                texto, color, simbolo = "Aumentar R$ 0,00", "green", "⬆️"
        else:
            if restante > 0:
                texto, color, simbolo = f"Aumentar R$ {format_valor_br(restante)}", "green", "⬆️"
            else:
                texto, color, simbolo = f"Reduzir R$ {format_valor_br(abs(restante))}", "red", "⬇️"

        cols = st.columns([8, 1])
        with cols[0]:
            st.markdown(f"""
                <div style='border:1px solid #000; padding:15px; border-radius:10px; margin-bottom:10px; background:#fff;'>
                    <span style='font-size:16px;'>{simbolo} {cls}</span><br>
                    <span style='color:gray'>{pct_atual:.2f}% → {pct_modelo:.2f}%</span><br>
                    <span style='color:gray'>Total da classe: R$ {format_valor_br(class_total)}</span><br>
                    <span style='color:gray; font-weight:bold'>Total ajustado: R$ {format_valor_br(df_current["Novo Valor"].sum())}</span><br>
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
                    "Liquidez":         st.column_config.TextColumn(label="Liquidez", disabled=True),  # adicionado aqui
                    "Valor Atual":      st.column_config.NumberColumn(label="Valor Atual", disabled=True),
                    "Valor Realocado":  st.column_config.NumberColumn(label="Valor Realocado"),
                    "Novo Valor":       st.column_config.NumberColumn(label="Novo Valor", disabled=True)
                },
                use_container_width=True,
                key=f"editor_{cls}"
            )
            # recalcula
            edited["Valor Atual"]     = pd.to_numeric(edited["Valor Atual"], errors="coerce").fillna(0)
            edited["Valor Realocado"] = pd.to_numeric(edited["Valor Realocado"], errors="coerce").fillna(0)
            edited["Novo Valor"]      = edited["Valor Atual"] + edited["Valor Realocado"]

            if any(prev.at[idx, "Valor Realocado"] != edited.at[idx, "Valor Realocado"]
                   for idx in edited.index if idx in prev.index):
                st.session_state[key] = edited
                st.rerun()
            else:
                st.session_state[key] = edited

    # Saldo restante
    soma_novo_total = sum(
        st.session_state[f"editor_df_{cls}"]["Novo Valor"].sum() for cls in classes_ordered
    )
    saldo_restante = soma_novo_total - total_atual
    st.subheader(f"Saldo Restante: R$ {format_valor_br(saldo_restante)}")
    if abs(saldo_restante) > 0.01:
        st.warning("A alocação ainda não está equilibrada. Ajuste até o Saldo Restante ser zero.")

    # Avança para a etapa 5 mantendo 'estrategia' e 'Liquidez'
    if st.button("Avançar para Confirmação e Geração do PDF", disabled=(abs(saldo_restante) > 0.01)):
        novos_ativos = []
        for cls in classes_ordered:
            df_cls = st.session_state[f"editor_df_{cls}"]
            for _, r in df_cls.iterrows():
                novos_ativos.append({
                    "estrategia":       r["Ativo"],
                    "saldo_bruto":      r["Valor Atual"],
                    "Novo Valor":       r["Novo Valor"],
                    "Valor Realocado":  r["Valor Realocado"],
                    "Classificação":    cls,
                    "Liquidez":         liq_map.get(r["Ativo"], "")
                })
        st.session_state.ativos_df = novos_ativos
        st.session_state.etapa      = 5
        st.rerun()
