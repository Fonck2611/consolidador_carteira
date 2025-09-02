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
from PyPDF2 import PdfReader, PdfWriter  # para concatenar PDFs (capa/contra/última)

# =========================
# Estado global simples (para header)
# =========================
patrimonio_total = 0.0
CLIENTE_NOME = ""
NOME_ASSESSOR = ""

# Cor primária de texto
PRIMARY_COLOR = colors.HexColor("#122940")  # alteração realizada aqui

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

    # Título à direita (permanece branco para contraste na faixa azul)
    canvas.setFillColor(colors.whitesmoke)
    canvas.setFont("Helvetica", 18)
    canvas.drawRightString(page_width - 10, page_height - 28, "Realocação de Carteira")

    # Bloco de informações do cliente (na cor primária)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(PRIMARY_COLOR)  # alteração realizada aqui
    canvas.drawString(10, page_height - 80, (CLIENTE_NOME or "").upper())

    canvas.setFont("Helvetica-Bold", 10)
    right_base_y = page_height - 60
    info_spacing = 10

    # Rótulos à direita (mantêm branco por estarem na faixa azul)
    canvas.setFillColor(colors.whitesmoke)
    canvas.drawRightString(page_width - 110, right_base_y - 1 * info_spacing, "Assessor de Investimentos")
    canvas.drawRightString(page_width - 110, right_base_y - 2.5 * info_spacing, "Patrimônio Total")

    # Valores à direita (na cor primária)
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(PRIMARY_COLOR)  # alteração realizada aqui
    canvas.drawRightString(page_width - 10, right_base_y - 1 * info_spacing, NOME_ASSESSOR or "")
    canvas.drawRightString(
        page_width - 10,
        right_base_y - 2.5 * info_spacing,
        f"R$ {_format_number_br(patrimonio_total)}"
    )

    # Linha final separadora (na cor primária)
    canvas.setStrokeColor(PRIMARY_COLOR)  # alteração realizada aqui
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
        textColor=PRIMARY_COLOR,  # alteração realizada aqui
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
    Gera o relatório e concatena:
      [1] utils/capa.pdf
      [2] utils/contra_capa.pdf
      [3] relatório (gerado aqui, com header/footer)
      [4] utils/ultima_pagina.pdf
    """
    # -------------------------
    # Normalizações de entrada
    # -------------------------
    df_dist = dist_df.copy()
    if "valor" not in df_dist.columns and "valor_atual" in df_dist.columns:
        df_dist = df_dist.rename(columns={"valor_atual": "valor"})  # alteração realizada aqui

    if "Percentual" not in df_dist.columns:
        total_val = pd.to_numeric(df_dist["valor"], errors="coerce").fillna(0.0).sum()
        df_dist["Percentual"] = (
            pd.to_numeric(df_dist["valor"], errors="coerce").fillna(0.0) / total_val * 100 if total_val else 0.0
        )  # alteração realizada aqui

    df_modelo = modelo_df.copy()
    if "Percentual Ideal" not in df_modelo.columns:
        poss = [c for c in df_modelo.columns if "percentual" in c.lower()]
        if poss:
            df_modelo = df_modelo.rename(columns={poss[0]: "Percentual Ideal"})  # alteração realizada aqui
        else:
            raise ValueError("modelo_df precisa conter a coluna 'Percentual Ideal'.")

    # -------------------------
    # Estado global para header
    # -------------------------
    global patrimonio_total, CLIENTE_NOME, NOME_ASSESSOR
    CLIENTE_NOME = cliente_nome or ""
    NOME_ASSESSOR = nome_assessor or ""
    patrimonio_total = pd.to_numeric(df_dist["valor"], errors="coerce").fillna(0.0).sum()

    styles = getSampleStyleSheet()

    # Define a cor da fonte nos estilos padrões (Normal, Title, Heading2, etc.)
    for s in styles.byName.values():  # alteração realizada aqui
        s.textColor = PRIMARY_COLOR

    elems = []

    # -------------------------
    # Funções de gráficos donut
    # -------------------------
    def make_doughnut_atual(df, percent_col):
        sorted_df = df.sort_values(by=percent_col, ascending=False).reset_index(drop=True)
        labels = sorted_df["Classificação"].tolist()
        sizes  = sorted_df[percent_col].tolist()
        colors_list = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
        color_map = dict(zip(labels, colors_list))

        buf = io.BytesIO()
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(
            sizes, labels=None, startangle=90, counterclock=False, colors=colors_list,
            wedgeprops={'width': 0.3, 'edgecolor': 'white'}
        )
        ax.axis('equal')
        plt.tight_layout()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0)
        return buf, color_map

    def make_doughnut_modelo(df, percent_col, color_map):
        sorted_df = df.sort_values(by=percent_col, ascending=False).reset_index(drop=True)
        labels = sorted_df["Classificação"].tolist()
        sizes  = sorted_df[percent_col].tolist()
        MANUAL_FALLBACK_COLORS = ["#CCCCCC", "#D4AF37", "#E7CA80", "#827008"]
        fallback = 0
        for label in labels:
            if label not in color_map:
                if fallback < len(MANUAL_FALLBACK_COLORS):
                    color_map[label] = MANUAL_FALLBACK_COLORS[fallback]; fallback += 1
                else:
                    idx = len(color_map) % len(PALETTE); color_map[label] = PALETTE[idx]
        colors_list = [color_map[l] for l in labels]

        buf = io.BytesIO()
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(
            sizes, labels=None, startangle=90, counterclock=False, colors=colors_list,
            wedgeprops={'width': 0.3, 'edgecolor': 'white'}
        )
        ax.axis('equal')
        plt.tight_layout()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0)
        return buf

    # -------------------------
    # Conteúdo do relatório (COMPLETO)
    # -------------------------
    buffer_relatorio = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer_relatorio, pagesize=A4, topMargin=130, bottomMargin=60, leftMargin=36, rightMargin=36
    )

    # Título
    elems.append(Spacer(1, 5))
    elems.append(Paragraph("Proposta de Alocação de Carteira", styles["Title"]))
    elems.append(Spacer(1, 12))

    # Donuts + comparativo
    buf1, color_map = make_doughnut_atual(df_dist, 'Percentual')
    buf2 = make_doughnut_modelo(df_modelo, 'Percentual Ideal', color_map)

    comp_data = [["Atual (%)", "Classificação", "Modelo (%)"]]
    header_small = ParagraphStyle(
        name="HeaderSmall",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=8,
        leading=8,
        textColor=colors.whitesmoke  # mantém branco no cabeçalho da tabela para contraste
    )
    comp_data[0] = [Paragraph(c, header_small) for c in comp_data[0]]

    temp_df = pd.DataFrame({
        "Classificação": list(dict.fromkeys(list(df_dist["Classificação"]) + list(df_modelo["Classificação"])))
    })
    temp_df["Atual"]  = temp_df["Classificação"].map(lambda x: df_dist.loc[df_dist["Classificação"] == x, "Percentual"].sum())
    temp_df["Modelo"] = temp_df["Classificação"].map(lambda x: df_modelo.loc[df_modelo["Classificação"] == x, "Percentual Ideal"].sum())
    temp_df = temp_df.fillna(0.0).sort_values(by="Atual", ascending=False).reset_index(drop=True)

    def bar(color: str, align="left", value: float = 0.0):
        val = float(value) if pd.notna(value) else 0.0
        percent = f"{val:.1f}".replace(".", ",") + "%"
        b = InnerTable([[" "]], colWidths=4, rowHeights=12)
        b.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor(color) if isinstance(color, str) else color),
                               ("BOX", (0,0), (-1,-1), 0, colors.white)]))
        small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=PRIMARY_COLOR,
                               alignment=TA_RIGHT if align=="right" else TA_LEFT)  # alteração realizada aqui
        if align == "left":
            return Table([[b, Spacer(1,0), Paragraph(percent, small)]], colWidths=[4,1,None],
                         style=[("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),0)])
        else:
            return Table([[Paragraph(percent, small), Spacer(1,0), b]], colWidths=[None,1,4],
                         style=[("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),0)])

    rows = []
    small_center = ParagraphStyle("SmallCenter", parent=styles["Normal"], alignment=TA_CENTER, fontSize=7,
                                  wordWrap='CJK', keepAll=True, textColor=PRIMARY_COLOR)  # alteração realizada aqui
    for _, r in temp_df.iterrows():
        color = color_map.get(r["Classificação"], "#000000")
        rows.append([bar(color, "left", r["Atual"]), Paragraph(str(r["Classificação"]), small_center), bar(color, "right", r["Modelo"])])

    comp_tbl = Table([["Atual (%)", "Classificação", "Modelo (%)"]] + rows, colWidths=[55, 90, 55], hAlign='CENTER')
    comp_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,1), (0,-1), 0),
        ('RIGHTPADDING', (-1,1), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),  # header
        ('BACKGROUND', (0,0), (-1,0), colors.gray),
        ('TEXTCOLOR', (0,1), (-1,-1), PRIMARY_COLOR),      # corpo na cor primária (alteração)
    ]))

    def titulo_com_traco(texto):
        sub = ParagraphStyle("SubHeader", parent=styles["Normal"], alignment=TA_CENTER,
                             fontSize=9, spaceAfter=2, textColor=PRIMARY_COLOR, textTransform='uppercase')  # alteração
        return Table([[Paragraph(texto, sub)],
                      [Table([[""]], colWidths="100%", style=[("LINEBELOW",(0,0),(-1,-1),0, PRIMARY_COLOR)])]],  # alteração
                     hAlign='CENTER',
                     style=[("BOTTOMPADDING",(0,0),(-1,-1),0), ("TOPPADDING",(0,1),(-1,1),-12)])

    grafico_atual    = Table([[titulo_com_traco("CARTEIRA ATUAL")],[Image(buf1, width=130, height=130)]],
                             rowHeights=[19,None], hAlign='CENTER')
    grafico_sugerido = Table([[titulo_com_traco("CARTEIRA PROPOSTA")],[Image(buf2, width=130, height=130)]],
                             rowHeights=[19,None], hAlign='CENTER')

    elems.append(Table([[grafico_atual, comp_tbl, grafico_sugerido]], colWidths=[155,230,155], hAlign='CENTER',
                       style=[('VALIGN',(0,0),(-1,-1),'TOP'), ('ALIGN',(0,0),(-1,-1),'CENTER')]))
    elems.append(Spacer(1, 30))

    # Tabelas "Carteira Atual" x "Proposta"
    dist_fmt = df_dist.copy().sort_values(by="valor", ascending=False)
    dist_fmt["valor"] = pd.to_numeric(dist_fmt["valor"], errors="coerce").fillna(0.0)
    dist_fmt["Valor"] = dist_fmt["valor"].apply(_format_number_br)
    dist_fmt["% PL"]  = dist_fmt["Percentual"].apply(lambda x: _format_number_br(x) + "%")
    dist_fmt = dist_fmt[["Classificação", "Valor", "% PL"]]

    modelo_fmt = df_modelo.copy()
    if "Valor Ideal (R$)" in modelo_fmt.columns:
        modelo_fmt["valor"] = pd.to_numeric(modelo_fmt["Valor Ideal (R$)"], errors="coerce").fillna(0.0)
    else:
        modelo_fmt["valor"] = 0.0
    modelo_fmt = modelo_fmt.sort_values(by="valor", ascending=False)
    modelo_fmt["Valor"] = modelo_fmt["valor"].apply(_format_number_br)
    modelo_fmt["% PL"]  = modelo_fmt["Percentual Ideal"].apply(lambda x: _format_number_br(x) + "%")
    modelo_fmt = modelo_fmt[["Classificação", "Valor", "% PL"]]

    tbl1 = Table([dist_fmt.columns.tolist()] + dist_fmt.values.tolist())
    tbl2 = Table([modelo_fmt.columns.tolist()] + modelo_fmt.values.tolist())
    styl = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.gray),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('TEXTCOLOR',(0,1),(-1,-1),PRIMARY_COLOR),  # corpo na cor primária (alteração)
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
    ])
    tbl1.setStyle(styl); tbl2.setStyle(styl)

    title_center = ParagraphStyle(name="CenteredTitle", parent=styles["Heading2"], alignment=TA_CENTER, textColor=PRIMARY_COLOR)  # alteração
    elems.append(Table([[Paragraph("Carteira Atual", title_center), Paragraph("Carteira Proposta", title_center)]],
                       colWidths=[doc.width/2, doc.width/2], hAlign='CENTER'))
    elems.append(Table([[tbl1, tbl2]], colWidths=[doc.width/2, doc.width/2], hAlign='CENTER',
                       style=[('VALIGN',(0,0),(-1,-1),'TOP')]))

    # Página seguinte — Sugestão de Carteira (detalhada)
    elems.append(PageBreak())
    elems.append(Paragraph("Sugestão de Carteira", styles["Heading2"]))  # Heading2 já usa PRIMARY_COLOR
    elems.append(Spacer(1, 12))

    data = [["Ativo", "Capital Alocado", "% PL"]]
    classification_rows = []
    row_idx = 1
    total_sug = pd.to_numeric(ativos_df["Novo Valor"], errors="coerce").fillna(0.0).sum()

    class_sums = (
        ativos_df.assign(_novo=pd.to_numeric(ativos_df["Novo Valor"], errors="coerce").fillna(0.0))
                 .groupby("Classificação")["_novo"].sum().sort_values(ascending=False)
    )
    for categoria, soma_val in class_sums.items():
        soma_pct = (soma_val / total_sug * 100) if total_sug else 0.0
        data.append([str(categoria).upper(), _format_number_br(soma_val), f"{soma_pct:.2f}".replace(".", ",") + "%"])
        classification_rows.append(row_idx); row_idx += 1

        grp = (ativos_df[ativos_df["Classificação"] == categoria]
               .assign(_novo=pd.to_numeric(ativos_df.loc[ativos_df["Classificação"] == categoria, "Novo Valor"], errors="coerce").fillna(0.0))
               .sort_values("_novo", ascending=False))
        for _, r in grp.iterrows():
            nome_ativo = unicodedata.normalize("NFKC", str(r.get("estrategia",""))).replace("\uFFFD","").replace("\xa0"," ").strip()
            nv = float(r.get("Novo Valor", 0.0)) if pd.notna(r.get("Novo Valor", 0.0)) else 0.0
            data.append([nome_ativo, _format_number_br(nv), (f"{(nv/total_sug*100):.2f}".replace(".", ",") + "%") if total_sug else "0,00%"])
            row_idx += 1

    tbl = Table(data, colWidths=[doc.width*0.6, doc.width*0.2, doc.width*0.2], hAlign="LEFT", repeatRows=1)
    style = TableStyle([
        ("GRID",(0,0),(-1,-1),0.5,colors.black),
        ("BACKGROUND",(0,0),(-1,0),colors.gray),
        ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),
        ("TEXTCOLOR",(0,1),(-1,-1),PRIMARY_COLOR),  # corpo na cor primária (alteração)
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,0),10),
        ("ALIGN",(0,0),(-1,0),"CENTER"),
        ("VALIGN",(0,0),(-1,0),"MIDDLE"),

        ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,1),(-1,-1),8),
        ("ALIGN",(0,1),(0,-1),"LEFT"),
        ("ALIGN",(1,1),(-1,-1),"CENTER"),
        ("VALIGN",(0,1),(-1,-1),"MIDDLE"),
    ])
    for i in classification_rows:
        style.add("BACKGROUND",(0,i),(-1,i),colors.lightgrey)
        style.add("FONTNAME",(0,i),(-1,i),"Helvetica-Bold")
    tbl.setStyle(style)
    elems.append(tbl)

    # Build do relatório — com header/footer
    def _on_page(canvas, doc):
        draw_header(canvas, doc)
        draw_footer(canvas, doc)

    doc.build(elems, onFirstPage=_on_page, onLaterPages=_on_page)
    buffer_relatorio.seek(0)

    # -------------------------
    # Concatenação final
    # -------------------------
    base_dir = os.path.dirname(__file__)
    capa_path    = os.path.join(base_dir, "capa.pdf")
    contra_path  = os.path.join(base_dir, "contra_capa.pdf")
    ultima_path  = os.path.join(base_dir, "ultima_pagina.pdf")

    writer = PdfWriter()

    # 1) Capa
    reader_capa = PdfReader(capa_path)
    for p in reader_capa.pages:
        writer.add_page(p)

    # 2) Contra-capa
    reader_contra = PdfReader(contra_path)
    for p in reader_contra.pages:
        writer.add_page(p)

    # 3) Relatório
    reader_rel = PdfReader(buffer_relatorio)
    for p in reader_rel.pages:
        writer.add_page(p)

    # 4) Última página
    reader_ultima = PdfReader(ultima_path)
    for p in reader_ultima.pages:
        writer.add_page(p)

    output_final = io.BytesIO()
    writer.write(output_final)
    output_final.seek(0)
    return output_final.read()
