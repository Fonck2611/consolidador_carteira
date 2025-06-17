import streamlit as st
from interfaces import upload_arquivos, detalhamento_ativos, comparacao_carteira, sugestoes_alocacao, confirmacao_pdf

# Define layout amplo para a página inteira
st.set_page_config(layout="wide")

# Inicializa estado da sessao
if 'etapa' not in st.session_state:
    st.session_state.etapa = 1

st.title("Simulador de Carteira - v0")

# Navegação controlada
with st.sidebar:
    st.write("## Etapas")
    for i in range(1, 6):
        label = f"Etapa {i}"
        disabled = i > st.session_state.etapa
        if st.button(label, disabled=disabled):
            st.session_state.etapa = i
            st.rerun()  # Corrige clique duplo

# Roteia para a interface correta
if st.session_state.etapa == 1:
    upload_arquivos.show()
elif st.session_state.etapa == 2:
    detalhamento_ativos.show()
elif st.session_state.etapa == 3:
    comparacao_carteira.show()
elif st.session_state.etapa == 4:
    sugestoes_alocacao.show()
elif st.session_state.etapa == 5:
    confirmacao_pdf.show()
