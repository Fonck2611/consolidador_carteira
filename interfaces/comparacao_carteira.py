import streamlit as st
import pandas as pd
import plotly.express as px
from utils.carteiras_modelo import get_modelo_carteira
from utils.cores import PALETTE


def show():
    st.header("3. Comparação com Carteira Modelo")

    ativos_raw = st.session_state.get("ativos_df", [])
    ativos_df = pd.DataFrame(ativos_raw)

    if ativos_df.empty or "Classificação" not in ativos_df.columns:
        st.error("Não há dados suficientes. Volte e preencha a etapa anterior.")
        return

    carteira_tipo = st.selectbox(
        "Escolha o tipo de carteira modelo:",
        ["Conservadora", "Moderada", "Sofisticada", "Personalizada"]
    )

    # Distribuição atual da carteira
    dist_atual = (
        ativos_df.groupby("Classificação")["saldo_bruto"]
        .sum()
        .reset_index()
    )
    total = dist_atual["saldo_bruto"].sum()
    dist_atual["Percentual"] = dist_atual["saldo_bruto"] / total * 100

    # Ordena do maior para o menor e gera colormap
    dist_sorted = dist_atual.sort_values("Percentual", ascending=False).reset_index(drop=True)
    sorted_classes = dist_sorted["Classificação"].tolist()
    color_map = {cls: PALETTE[i % len(PALETTE)] for i, cls in enumerate(sorted_classes)}

    # Preparar modelo
    if carteira_tipo != "Personalizada":
        modelo = get_modelo_carteira(carteira_tipo)
        modelo_df = pd.DataFrame({
            "Classificação": list(modelo.keys()),
            "Percentual": list(modelo.values())
        })
        soma_percentual = modelo_df["Percentual"].sum()
    else:
        st.markdown("### Defina a Carteira Personalizada")
        # Inicializa estado raw_modelo_personalizado
        if "raw_modelo_personalizado" not in st.session_state:
            base = dist_atual[["Classificação", "Percentual"]].copy()
            base.rename(columns={"Percentual": "Percentual Desejado"}, inplace=True)
            st.session_state.raw_modelo_personalizado = base
        raw = st.session_state.raw_modelo_personalizado.copy()

        # Editor de modelo personalizado com alinhamento
        st.markdown(
            """
            <style>
            div[data-testid="stDataEditor"] .ag-cell,
            div[data-testid="stDataEditor"] .ag-header-cell {
                text-align: left !important;
            }
            </style>
            """, unsafe_allow_html=True
        )
        df_display = raw.copy()
        df_display["Percentual Desejado"] = df_display["Percentual Desejado"].map(
            lambda v: f"{v:.2f}".replace('.', ',')
        )
        edited = st.data_editor(
            df_display,
            num_rows="dynamic",
            key="custom_modelo_editor",
            column_config={
                "Classificação": st.column_config.TextColumn(label="Classificação"),
                "Percentual Desejado": st.column_config.TextColumn(label="%")
            },
            use_container_width=True
        )
        updated_raw = raw.copy()
        changed = False
        for idx in edited.index:
            if idx < len(raw):
                new_class = edited.at[idx, 'Classificação']
                if new_class != raw.at[idx, 'Classificação']:
                    updated_raw.at[idx, 'Classificação'] = new_class
                    changed = True
                val = edited.at[idx, 'Percentual Desejado']
                original = f"{raw.at[idx, 'Percentual Desejado']:.2f}".replace('.', ',')
                if val != original:
                    try:
                        updated_raw.at[idx, 'Percentual Desejado'] = float(val.replace(',', '.'))
                        changed = True
                    except:
                        pass
            else:
                classe = edited.at[idx, 'Classificação']
                pct_str = edited.at[idx, 'Percentual Desejado']
                if classe and isinstance(pct_str, str):
                    try:
                        pct = float(pct_str.replace(',', '.'))
                        updated_raw.loc[len(updated_raw)] = {'Classificação': classe, 'Percentual Desejado': pct}
                        changed = True
                    except:
                        pass
        st.session_state.raw_modelo_personalizado = updated_raw.reset_index(drop=True)
        if changed:
            st.rerun()
        soma_percentual = updated_raw["Percentual Desejado"].sum()
        modelo_df = updated_raw.rename(columns={"Percentual Desejado": "Percentual"})[["Classificação", "Percentual"]]

    # Exibir gráficos
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Distribuição Atual")
        fig_atual = px.pie(
            dist_sorted,
            names="Classificação",
            values="Percentual",
            hole=0.3,
            color="Classificação",
            color_discrete_map=color_map
        )
        fig_atual.update_layout(separators=",.")
        fig_atual.update_traces(
            textinfo='percent',
            texttemplate='%{percent:.1%}',
            rotation=0,
            direction='clockwise'
        )
        st.plotly_chart(fig_atual, use_container_width=True)

    with col2:
        st.subheader(f"Carteira {carteira_tipo}")
        if carteira_tipo == "Personalizada" and round(soma_percentual, 2) != 100.00:
            st.warning(f"⚠️ A soma dos percentuais está em {soma_percentual:.2f}%. Ajuste para que totalize 100%.")
        else:
            fig_modelo = px.pie(
                modelo_df,
                names="Classificação",
                values="Percentual",
                hole=0.3,
                color="Classificação",
                color_discrete_map=color_map
            )
            fig_modelo.update_layout(separators=",.")
            fig_modelo.update_traces(
                textinfo='percent',
                texttemplate='%{percent:.1%}',
                rotation=0,
                direction='clockwise'
            )
            st.plotly_chart(fig_modelo, use_container_width=True)

    if st.button("Avançar para Sugestão de Ajustes"):
        if carteira_tipo == "Personalizada" and round(soma_percentual, 2) != 100.00:
            st.warning("Ajuste a carteira sugerida para que totalize 100%.")
        else:
            # guarda o tipo de carteira escolhido
            st.session_state.carteira_modelo = carteira_tipo
            if carteira_tipo == "Personalizada":
                st.session_state.modelo_personalizado_dict = dict(
                    zip(modelo_df["Classificação"], modelo_df["Percentual"])
                )

            # >>> GARANTIR QUE O APORTE SIGA ADIANTE + MERGE DA SUGESTÃO <<<
            sug_existente = dict(st.session_state.get("sugestao", {}))
            sug_existente["carteira_modelo"] = carteira_tipo
            if carteira_tipo == "Personalizada":
                sug_existente["modelo_personalizado"] = st.session_state.get("modelo_personalizado_dict")

            # Propaga aporte se já foi informado na Etapa 2
            if "aporte_text" in st.session_state and st.session_state.get("aporte_text"):
                sug_existente["aporte_text"] = st.session_state["aporte_text"]
            if "aporte_valor" in st.session_state and st.session_state.get("aporte_valor") is not None:
                sug_existente["aporte_valor"] = st.session_state["aporte_valor"]

            st.session_state.sugestao = sug_existente
            # <<< FIM – PROPAGAÇÃO DO APORTE >>>

            st.session_state.etapa = 4
            st.rerun()
