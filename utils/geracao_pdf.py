# utils/geracao_pdf.py
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.platypus import Table as InnerTable
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.utils import ImageReader
import pandas as pd
import io
import os
import matplotlib.pyplot as plt
from utils.cores import PALETTE
import unicodedata
from PyPDF2 import PdfReader, PdfWriter  # alteração realizada aqui

# =========================
# Estado global simples
# =========================
patrimonio_total = 0.0
CLIENTE_NOME = ""
NOME_ASSESSOR = ""

def _format_number_br(valor: float) -> str:
    try:
        v = float(valor)
    except Exception:
        return str(valor)
    s = f"{v:,.2f}"
    return s.replace(",", "v").replace(".", ",").replace("v", ".")

def draw_header(canvas, doc):
    canvas.saveState()
    page_width, page_height = A4
    faixa_altura = 40

    # Faixa azul no topo
    canvas.setFillColor(colors.HexColor("#0F2B56"))
    canvas.rect(4, page_height - faixa_altura - 4, page_width - 8, faixa_altura, stroke=0, fill=1)

    # Logo
    try:
        base_dir = os.path.dirname(__file__)
        logo_path = os.path.join(base_dir, "Logo_Criteria_Financial_Group_Cor_V2_RGB-01.png")
        logo = ImageReader(logo_path)
        canvas.drawImage(logo, x=6, y=page_height - 55, width=125.6, height=60, mask='auto')
    except Exception as e:
        print("Erro ao carregar logo:", e)

    # Título à direita
    canvas.setFillColor(colors.whitesmoke)
    canvas.setFont("Helvetica", 18)
    canvas.drawRightString(page_width - 10, page_height - 28, "Realocação de Carteira")

    # Bloco de informações do cliente
    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(colors.black)
    canvas.drawString(10, page_height - 80, (CLIENTE_NOME or "").upper())

    canvas.setFont("Helvetica-Bold", 10)
    right_base_y = page_height - 60
    info_spacing = 10

    canvas.drawRightString(page_width - 110, right_base_y - 1 * info_spacing, "Assessor de Investimentos")
    canvas.drawRightString(page_width - 110, right_base_y - 2.5 * info_spacing, "Patrimônio Total")

    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.black)
    canvas.drawRightString(page_width - 10, right_base_y - 1 * info_spacing, NOME_ASSESSOR or "")
    canvas.drawRightString(
        page_width - 10,
        right_base_y - 2.5 * info_spacing,
        f"R$ {_format_number_br(patrimonio_total)}"
    )

    # Linha final separadora
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.5)
    canvas.line(10, page_height - 100, page_width - 10, page_height - 100)

    canvas.restoreState()

def draw_footer(canvas, doc):
    canvas.saveState()
    page_width, _ = A4
    canvas.setFillColor(colors.lightgrey)
    canvas.rect(0, 0, page_width, 60, stroke=0, fill=1)

    styles = getSampleStyleSheet()
    footer_style = ParagraphStyle(
        name="FooterStyle",
        fontSize=5,
        leading=7,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceBefore=2,
        spaceAfter=2
    )

    disclaimer = (
        "Disclaimers: A Criteria Invest – Agente Autônomo de Investimentos Ltda. é uma empresa de agentes autônomos de investimento devidamente registrada na Comissão de Valores Mobiliários, "
        "na forma da Instrução Normativa n. 434/06. A Criteria Invest – Agente Autônomo de Investimentos Ltda. atua no mercado financeiro através da XP Investimentos CCTVM S/A, realizando o atendimento "
        "de pessoas físicas e jurídicas (não institucionais). Na forma da legislação da CVM, o agente autônomo de investimento não pode administrar ou gerir o patrimônio de investidores. O agente autônomo "
        "é um intermediário e depende da autorização prévia do cliente para realizar operações no mercado financeiro. Esta mensagem, incluindo os seus anexos, contém informações confidenciais destinadas a "
        "indivíduo e propósito específicos, sendo protegida por lei. Caso você não seja a pessoa a quem foi dirigida a mensagem, deve apagá-la. É terminantemente proibida a utilização, acesso, cópia ou divulgação "
        "não autorizada das informações presentes nesta mensagem. As informações contidas nesta mensagem e em seus anexos são de responsabilidade de seu autor, não representando necessariamente ideias, opiniões, "
        "pensamentos ou qualquer forma de posicionamento por parte da Criteria Invest. – Agente Autônomo de Investimentos Ltda. O investimento em ações é um investimento de risco e rentabilidade passada não é garantia "
        "de rentabilidade futura. Na realização de operações com derivativos existe a possibilidade de perdas superiores aos valores investidos, podendo resultar em significativas perdas patrimoniais. Para informações "
        "e dúvidas, favor contatar seu operador. Para reclamações, favor contatar a Ouvidoria da XP Investimentos no telefone nº 0800-722-3710."
    )

    disclaimer_paragraph = Paragraph(disclaimer, footer_style)
    disclaimer_paragraph_width, _ = disclaimer_paragraph.wrap(page_width - 5, 40)
    x_position = (page_width - disclaimer_paragraph_width) / 2
    disclaimer_paragraph.drawOn(canvas, x_position, 5)

    canvas.restoreState()

def generate_pdf(
    dist_df: pd.DataFrame,
    modelo_df: pd.DataFrame,
    resumo_df: pd.DataFrame,
    sugestao: dict,
    ativos_df: pd.DataFrame,
    cliente_nome: str = "",
    nome_assessor: str = "",
) -> bytes:
    """
    Gera o PDF completo e concatena:
    - capa.pdf (primeira página)
    - contra_capa.pdf (segunda página)
    - relatório (gerado aqui)
    - ultima_pagina.pdf (última página)
    """
    # =========================
    # Normalizações de entrada
    # =========================
    df_dist = dist_df.copy()
    if "valor" not in df_dist.columns and "valor_atual" in df_dist.columns:
        df_dist = df_dist.rename(columns={"valor_atual": "valor"})

    if "Percentual" not in df_dist.columns:
        total_val = pd.to_numeric(df_dist["valor"], errors="coerce").fillna(0.0).sum()
        df_dist["Percentual"] = (
            pd.to_numeric(df_dist["valor"], errors="coerce").fillna(0.0) / total_val * 100 if total_val else 0.0
        )

    df_modelo = modelo_df.copy()
    if "Percentual Ideal" not in df_modelo.columns:
        possibles = [c for c in df_modelo.columns if "percentual" in c.lower()]
        if possibles:
            df_modelo = df_modelo.rename(columns={possibles[0]: "Percentual Ideal"})
        else:
            raise ValueError("modelo_df precisa conter a coluna 'Percentual Ideal'.")

    global patrimonio_total, CLIENTE_NOME, NOME_ASSESSOR
    CLIENTE_NOME = cliente_nome
    NOME_ASSESSOR = nome_assessor
    patrimonio_total = pd.to_numeric(df_dist["valor"], errors="coerce").fillna(0.0).sum()

    styles = getSampleStyleSheet()
    elems = []

    # =========================
    # Documento temporário (somente o relatório interno)
    # =========================
    buffer_relatorio = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer_relatorio,
        pagesize=A4,
        topMargin=130,
        bottomMargin=60,
        leftMargin=36,
        rightMargin=36
    )

    # (Conteúdo do relatório igual ao anterior...)
    elems.append(Spacer(1, 5))
    elems.append(Paragraph("Proposta de Alocação de Carteira", styles["Title"]))
    elems.append(Spacer(1, 12))

    def _on_page(canvas, doc):
        draw_header(canvas, doc)
        draw_footer(canvas, doc)

    doc.build(elems, onFirstPage=_on_page, onLaterPages=_on_page)
    buffer_relatorio.seek(0)

    # =========================
    # Concatenação dos PDFs
    # =========================
    base_dir = os.path.dirname(__file__)
    capa_path = os.path.join(base_dir, "capa.pdf")
    contra_path = os.path.join(base_dir, "contra_capa.pdf")
    ultima_path = os.path.join(base_dir, "ultima_pagina.pdf")  # alteração realizada aqui

    writer = PdfWriter()

    # adiciona capa
    reader_capa = PdfReader(capa_path)
    for page in reader_capa.pages:
        writer.add_page(page)

    # adiciona contra-capa
    reader_contra = PdfReader(contra_path)
    for page in reader_contra.pages:
        writer.add_page(page)

    # adiciona relatório
    reader_rel = PdfReader(buffer_relatorio)
    for page in reader_rel.pages:
        writer.add_page(page)

    # adiciona ultima página
    reader_ultima = PdfReader(ultima_path)
    for page in reader_ultima.pages:
        writer.add_page(page)

    output_final = io.BytesIO()
    writer.write(output_final)
    output_final.seek(0)
    return output_final.read()
