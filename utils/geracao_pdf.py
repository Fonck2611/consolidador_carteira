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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, Frame
import unicodedata




patrimonio_total = 0.0  # será atualizado na função generate_pdf
CLIENTE_NOME = ""
NOME_ASSESSOR = ""

def draw_header(canvas, doc):
    canvas.saveState()
    page_width, page_height = A4
    faixa_altura = 40

    # Faixa azul no topo
    canvas.setFillColor(colors.HexColor("#0F2B56"))
    canvas.rect(4, page_height - faixa_altura - 4, page_width - 8, faixa_altura, stroke=0, fill=1)

    # Logo
    try:
        logo_path = os.path.join(os.path.dirname(__file__), "Logo_Criteria_Financial_Group_Cor_V2_RGB-01.png")
        logo = ImageReader(logo_path)
        canvas.drawImage(logo, x=6, y=page_height - 55, width=125.6, height=60, mask='auto')
    except Exception as e:
        print("Erro ao carregar logo:", e)

    # Texto à direita
    canvas.setFillColor(colors.whitesmoke)
    canvas.setFont("Helvetica", 18)
    canvas.drawRightString(page_width - 10, page_height - 28, "Realocação de Carteira")

    # Bloco de informações do cliente
    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(colors.black)
    canvas.drawString(10, page_height - 80, CLIENTE_NOME.upper())

    canvas.setFont("Helvetica-Bold", 10)
    right_base_y = page_height - 60
    info_spacing = 10

    canvas.drawRightString(page_width - 110, right_base_y - 1 * info_spacing, "Assessor de Investimentos")
    canvas.drawRightString(page_width - 110, right_base_y - 2.5 * info_spacing, "Patrimônio Total")

    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.black)
    canvas.drawRightString(page_width - 10, right_base_y - 1 * info_spacing, NOME_ASSESSOR)
    canvas.drawRightString(page_width - 10, right_base_y - 2.5 * info_spacing, f"R$ {patrimonio_total:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))

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
        spaceAfter= 2
    )

    disclaimer = (
        "Disclaimers: A Criteria Invest – Agente Autônomo de Investimentos Ltda. é uma empresa de agentes autônomos de investimento devidamente registrada na Comissão de Valores Mobiliários, na forma da Instrução "
        "Normativa n. 434/06. A Criteria Invest – Agente Autônomo de Investimentos Ltda. atua no mercado financeiro através da XP Investimentos CCTVM S/A, realizando o atendimento de pessoas físicas e jurídicas (não "
        "institucionais). Na forma da legislação da CVM, o agente autônomo de investimento não pode administrar ou gerir o patrimônio de investidores. O agente autônomo é um intermediário e depende da autorização "
        "prévia do cliente para realizar operações no mercado financeiro. Esta mensagem, incluindo os seus anexos, contém informações confidenciais destinadas a indivíduo e propósito específicos, sendo protegida por lei. "
        "Caso você não seja a pessoa a quem foi dirigida a mensagem, deve apagá-la. É terminantemente proibida a utilização, acesso, cópia ou divulgação não autorizada das informações presentes nesta mensagem. As "
        "informações contidas nesta mensagem e em seus anexos são de responsabilidade de seu autor, não representando necessariamente ideias, opiniões, pensamentos ou qualquer forma de posicionamento por parte "
        "da Criteria Invest. – Agente Autônomo de Investimentos Ltda. O investimento em ações é um investimento de risco e rentabilidade passada não é garantia de rentabilidade futura. Na realização de operações com "
        "derivativos existe a possibilidade de perdas superiores aos valores investidos, podendo resultar em significativas perdas patrimoniais. Para informações e dúvidas, favor contatar seu operador. Para reclamações, "
        "favor contatar a Ouvidoria da XP Investimentos no telefone nº 0800-722-3710."
    )

    disclaimer_paragraph = Paragraph(disclaimer, footer_style)
    disclaimer_paragraph_width, _ = disclaimer_paragraph.wrap(page_width - 5, 40)
    x_position = (page_width - disclaimer_paragraph_width) / 2
    disclaimer_paragraph.drawOn(canvas, x_position, 5)

    canvas.restoreState()

def format_number_br(valor):
    return f"{valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def generate_pdf(
    dist_df: pd.DataFrame,
    modelo_df: pd.DataFrame,
    resumo_df: pd.DataFrame,
    sugestao: dict,
    ativos_df: pd.DataFrame,
    output_path: str = "relatorio_carteira.pdf",
    cliente_nome: str = CLIENTE_NOME,
    nome_assessor: str = NOME_ASSESSOR,
    ):
    raw_modelo_df = modelo_df.copy()
    global patrimonio_total, CLIENTE_NOME, NOME_ASSESSOR
    CLIENTE_NOME = cliente_nome
    NOME_ASSESSOR = nome_assessor
    patrimonio_total = dist_df["valor"].sum() if "valor" in dist_df.columns else 0.0

    styles = getSampleStyleSheet()
    elems = []
    elems.append(Spacer(1, 5))
    elems.append(Paragraph("Proposta de Alocação de Carteira", styles["Title"]))
    elems.append(Spacer(1, 12))

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=130,
        bottomMargin=60,
        leftMargin=36,
        rightMargin=36
    )

    def make_doughnut_atual(df, percent_col):
        sorted_df = df.sort_values(by=percent_col, ascending=False).reset_index(drop=True)
        labels = sorted_df["Classificação"].tolist()
        sizes = sorted_df[percent_col].tolist()
        colors_list = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
        color_map = dict(zip(labels, colors_list))

        buf = io.BytesIO()
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(
            sizes,
            labels=None,
            startangle=90,
            counterclock=False,
            colors=colors_list,
            wedgeprops={'width': 0.3, 'edgecolor': 'white'}
        )
        ax.axis('equal')
        plt.tight_layout()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf, color_map

    def make_doughnut_modelo(df, percent_col, color_map):
        sorted_df = df.sort_values(by=percent_col, ascending=False).reset_index(drop=True)
        labels = sorted_df["Classificação"].tolist()
        sizes = sorted_df[percent_col].tolist()

        MANUAL_FALLBACK_COLORS = ["#CCCCCC", "#D4AF37", "#E7CA80", "#827008"]
        fallback_index = 0

        for label in labels:
            if label not in color_map:
                if fallback_index < len(MANUAL_FALLBACK_COLORS):
                    color_map[label] = MANUAL_FALLBACK_COLORS[fallback_index]
                    fallback_index += 1
                else:
                    idx = len(color_map) % len(PALETTE)
                    color_map[label] = PALETTE[idx]

        colors_list = [color_map[label] for label in labels]

        buf = io.BytesIO()
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(
            sizes,
            labels=None,
            startangle=90,
            counterclock=False,
            colors=colors_list,
            wedgeprops={'width': 0.3, 'edgecolor': 'white'}
        )
        ax.axis('equal')
        plt.tight_layout()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf

    def format_percent(val):
        return f"{val:.1f}".replace(".", ",") + "%"

    def render_color_bar(color: str, align: str = "left", value: float = 0.0):
        percent = format_percent(value)

        bar = InnerTable(
            [[" "]],
            colWidths=4,
            rowHeights=12
        )
        bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), color),
            ("BOX", (0, 0), (-1, -1), 0, color),
        ]))

        small_text_style = ParagraphStyle(
            "SmallText",
            parent=styles["Normal"],
            fontSize=8,
            alignment=TA_RIGHT if align == "right" else TA_LEFT
        )

        if align == "left":
            return Table(
                [[bar, Spacer(1, 0), Paragraph(percent, small_text_style)]],
                colWidths=[4, 1, None],
                style=[
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT")
                ]
            )
        else:
            return Table(
                [[Paragraph(percent, small_text_style), Spacer(1, 0), bar]],
                colWidths=[None, 1, 4],
                style=[
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT")
                ]
            )


    buf1, color_map = make_doughnut_atual(dist_df, 'valor')
    buf2 = make_doughnut_modelo(modelo_df, 'Percentual Ideal', color_map)

    comp_data = [["Atual (%)", "Classificação", "Modelo (%)"]]

    header_style = ParagraphStyle(
        name="HeaderSmall",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=8,
        leading=8,  # diminui a altura da linha
        textColor=colors.whitesmoke
    )
    comp_data[0] = [Paragraph(c, header_style) for c in comp_data[0]]

    temp_df = pd.DataFrame({
        "Classificação": list(dict.fromkeys(list(dist_df["Classificação"]) + list(modelo_df["Classificação"])))
    })
    temp_df["Atual"] = temp_df["Classificação"].map(lambda x: dist_df.loc[dist_df["Classificação"] == x, "Percentual"].sum())
    temp_df["Modelo"] = temp_df["Classificação"].map(lambda x: modelo_df.loc[modelo_df["Classificação"] == x, "Percentual Ideal"].sum())
    temp_df = temp_df.sort_values(by="Atual", ascending=False).reset_index(drop=True)

    for _, row in temp_df.iterrows():
        color = color_map.get(row["Classificação"], "#000000")
        bar_left = render_color_bar(color, align="left", value=row["Atual"])
        bar_right = render_color_bar(color, align="right", value=row["Modelo"])
        small_center_style = ParagraphStyle(
            "SmallCenter",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=7,
            wordWrap='CJK',
            keepAll=True
        )
        p_cls = Paragraph(row["Classificação"], small_center_style)
        comp_data.append([bar_left, p_cls, bar_right])

    comp_tbl = Table(comp_data, colWidths=[55, 90, 55], hAlign='CENTER')
    comp_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 1), (0, -1), 0),
        ('RIGHTPADDING', (-1, 1), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
    ]))

    subheader_style = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        spaceAfter=2,
        textTransform='uppercase'
    )

    # Função auxiliar para criar o título com traço
    def titulo_com_traco(texto):
        return Table(
            [
                [Paragraph(texto, subheader_style)],
                [Table(
                    [[""]],
                    colWidths="100%",
                    style=[("LINEBELOW", (0, 0), (-1, -1), 0, colors.black)]
                )]
            ],
            hAlign='CENTER',
            style=[("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 1), (-1, 1), -12),]
        )

    # Gráfico Atual com título e traço
    grafico_atual = Table(
        [
            [titulo_com_traco("CARTEIRA ATUAL")],
            [Image(buf1, width=130, height=130)]
        ],
        rowHeights=[19, None],
        hAlign='CENTER'
    )

    # Gráfico Modelo com título e traço
    grafico_sugerido = Table(
        [
            [titulo_com_traco("CARTEIRA PROPOSTA")],
            [Image(buf2, width=130, height=130)]
        ],
        rowHeights=[19, None],
        hAlign='CENTER'
    )

    # Composição final
    elems.append(
        Table(
            [[grafico_atual, comp_tbl, grafico_sugerido]],
            colWidths=[155, 230, 155],
            hAlign='CENTER',
            style=[
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER')
            ]
        )
    )
    elems.append(Spacer(1, 30))  # espaçamento aumentado

    # Tabelas detalhadas

    dist_df = dist_df.copy().sort_values(by="valor", ascending=False)
    dist_df["valor"] = dist_df["valor"].apply(format_number_br)
    dist_df["Percentual"] = dist_df["Percentual"].apply(lambda x: format_number_br(x) + "%")
    dist_df = dist_df.rename(
        columns={
        "Classificação": "Classificação",
        "valor":        "Valor",
        "Percentual":   "% PL"
        }
    )
    dist_df = dist_df[["Classificação", "Valor", "% PL"]]

    modelo_df = modelo_df.copy().rename(columns={"Percentual Ideal": "Percentual", "Valor Ideal (R$)": "valor"})
    modelo_df = modelo_df.sort_values(by="valor", ascending=False)
    modelo_df["valor"] = modelo_df["valor"].apply(format_number_br)
    modelo_df["Percentual"] = modelo_df["Percentual"].apply(lambda x: format_number_br(x) + "%")
    modelo_df = modelo_df.rename(
        columns={
        "Classificação": "Classificação",
        "valor":        "Valor",
        "Percentual":   "% PL"
        }
    )
    modelo_df = modelo_df[["Classificação", "Valor", "% PL"]]

    data1 = [dist_df.columns.tolist()] + dist_df.values.tolist()
    data2 = [modelo_df.columns.tolist()] + modelo_df.values.tolist()
    tbl1 = Table(data1)
    tbl2 = Table(data2)

    grid_style = ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
    header_style = ('BACKGROUND', (0, 0), (-1, 0), colors.gray)
    textcolor_style = ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke)
    base_align = ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    valign_top = ('VALIGN', (0, 0), (-1, -1), 'TOP')
    tbl_styles = [header_style, textcolor_style, grid_style, base_align, valign_top]
    tbl1.setStyle(TableStyle(tbl_styles))
    tbl2.setStyle(TableStyle(tbl_styles))

    # Títulos centralizados horizontalmente com as tabelas
    title_style_centered = ParagraphStyle(
        name="CenteredTitle",
        parent=styles["Heading2"],
        alignment=TA_CENTER
    )
    
    tbl_titles = Table(
        [[
            Paragraph("Carteira Atual", title_style_centered),
            Paragraph("Carteira Proposta", title_style_centered)
        ]],
        colWidths=[doc.width / 2, doc.width / 2],
        hAlign='CENTER'
    )
    
    tbl_both = Table(
        [[tbl1, tbl2]],
        colWidths=[doc.width / 2, doc.width / 2],
        hAlign='CENTER',
        style=[('VALIGN', (0, 0), (-1, -1), 'TOP')]
    )
    
    elems.append(tbl_titles)
    elems.append(tbl_both)

    # 1) Quebra para 2ª página e título
    elems.append(PageBreak())
    elems.append(Paragraph("Sugestão de Carteira", styles["Heading2"]))
    elems.append(Spacer(1, 12))

    # 1) Cabeçalho e preparação de dados
    data = [["Ativo", "Capital Alocado", "% PL"]]
    classification_rows = []
    row_idx = 1
    total_sug = ativos_df["Novo Valor"].astype(float).sum()

    # 2) Calcula soma por classificação e ordena decrescente
    class_sums = (
        ativos_df
        .groupby("Classificação")["Novo Valor"]
        .sum()
        .sort_values(ascending=False)
    )

    # 3) Preenche linhas: sub-cabeçalho (classificação) + ativos ordenados
    for categoria, soma_val in class_sums.items():
        # % do grupo na carteira
        soma_pct = (soma_val / total_sug) * 100

        # 3.1) Linha de classificação (sub-cabeçalho)
        data.append([
            categoria.upper(),
            format_number_br(soma_val),
            f"{soma_pct:.2f}%".replace(".", ",")
        ])
        classification_rows.append(row_idx)
        row_idx += 1

        # 3.2) Linhas dos ativos dessa classificação, também ordenados decrescente
        grp = (
            ativos_df[ativos_df["Classificação"] == categoria]
            .sort_values("Novo Valor", ascending=False)
        )
        for _, row in grp.iterrows():
            # normaliza e remove chars invisíveis que viram quadrado preto
            nome_ativo = unicodedata.normalize("NFKC", row["estrategia"]) \
                .replace("\uFFFD", "") \
                .replace("\xa0", " ") \
                .strip()

            data.append([
                nome_ativo,
                format_number_br(row["Novo Valor"]),
                f"{(row['Novo Valor'] / total_sug * 100):.2f}%".replace(".", ",")
            ])
            row_idx += 1

    # 4) Cria única tabela com header repetido a cada página
    tbl = Table(
        data,
        colWidths=[doc.width * 0.6, doc.width * 0.2, doc.width * 0.2],
        hAlign="LEFT",
        repeatRows=1
    )

    # 5) Ajusta estilos gerais e de classificação
    style = TableStyle([
        # grid em toda a tabela
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),

        # cabeçalho: fundo cinza, texto branco, negrito e fonte maior
        ("BACKGROUND",  (0, 0), (-1, 0), colors.gray),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 10),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",      (0, 0), (-1, 0), "MIDDLE"),

        # corpo: fonte normal, menor
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8),
        ("ALIGN",       (0, 1), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 1), (-1, -1), "MIDDLE"),

        # coluna “Ativo” alinhada à esquerda
        ("ALIGN",       (0, 1), (0, -1), "LEFT"),
    ])

    # 5.1) Destaca cada linha de classificação
    for i in classification_rows:
        style.add("BACKGROUND", (0, i), (-1, i), colors.lightgrey)
        style.add("FONTNAME",   (0, i), (-1, i), "Helvetica-Bold")

    tbl.setStyle(style)
    elems.append(tbl)
    # --- fim da Carteira Modelo Detalhada ---

    doc.build(
        elems,
        onFirstPage=lambda c, d: (draw_header(c, d), draw_footer(c, d)),
        onLaterPages=lambda c, d: (draw_header(c, d), draw_footer(c, d))
    )
    return output_path
