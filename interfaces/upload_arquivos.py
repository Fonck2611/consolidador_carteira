import streamlit as st
from utils.extrair_pdf_xp import extrair_texto_ativos, parse_ativos

def show():
    st.header("1. Upload dos Arquivos da Carteira")

    uploaded_files = st.file_uploader(
        "Faça upload de um ou mais PDFs da carteira do cliente",
        type="pdf",
        accept_multiple_files=True
    )

    if uploaded_files:
        nomes_arquivos = [f.name for f in uploaded_files]

        if 'arquivos' not in st.session_state or st.session_state.get("arquivos_originais") != nomes_arquivos:
            arquivos_processados = []
            ativos_completos = []

            for file in uploaded_files:
                texto_ativos = extrair_texto_ativos(file)
                df_ativos = parse_ativos(texto_ativos)
                df_ativos["Banco"] = "XP"  # Marca como XP

                ativos_completos.extend(df_ativos.to_dict(orient="records"))

                arquivos_processados.append({
                    "nome_arquivo": file.name,
                    "banco": "XP",
                    "ativos_extraidos": df_ativos.to_dict(orient="records")
                })

            st.session_state.arquivos = arquivos_processados
            st.session_state.ativos_df = ativos_completos
            st.session_state.arquivos_originais = nomes_arquivos

        for arq in st.session_state.arquivos:
            st.write(f"📄 **{arq['nome_arquivo']}** — Banco: **{arq['banco']}**")

        if st.button("Avançar para Detalhamento dos Ativos"):
            st.session_state.etapa = 2
            st.rerun()
    else:
        st.info("Por favor, envie ao menos um arquivo PDF para continuar.")
