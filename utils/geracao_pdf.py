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
import unicodedata
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime

# === Matplotlib (garantir geração dos gráficos em ambiente headless)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from utils.cores import PALETTE

# =========================
# Estado global simples (para header)
# =========================
patrimonio_total = 0.0
CLIENTE_NOME = ""
NOME_ASSESSOR = ""

# Cor primária de texto
PRIMARY_COLOR = colors.HexColor("#122940")

# Variáveis do novo cabeçalho
DATA_HOJE_STR = ""          # ex.: "28 de julho de 2025"
PERFIL_RISCO = "PERSONALIZADA"
APORTE_TEXT = "Sem aporte"  # preparado para virar variável

# Bloco de contato (topo direito)
CONTACT_LINES = [
    "Av. Magalhães de Castro, 4800 – 1º andar",
    "Continental Tower (Torre 3)",
    "Cidade Jardim Corporate Center",
    "São Paulo - SP, 05676-120",
    "+55 (11) 3124-9696",
    "www.criteriafg.com.br",
]

# -------------------------
# Fontes (fixadas para Helvetica, conforme solicitado)
# -------------------------
BASE_FONT = "Helvetica"        # (mantido)
BOLD_FONT = "Helvetica-Bold"   # (mantido)

# -------------------------
# Utilidades
# -------------------------
def _format_number_br(valor: float) -> str:
    try:
        v = float(valor)
    except Exception:
        return str(valor)
    s = f"{v:,.2f}"
    return s.replace(",", "v").replace(".", ",").replace("v", ".")

def _data_hoje_br() -> str:
    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    hoje = datetime.today()
    return f"{hoje.day} de {meses[hoje.month-1]} de {hoje.year}"

def _inferir_perfil(sugestao: dict) -> str:
    cand = (sugestao or {}).get("perfil") or (sugestao or {}).get("carteira_modelo") or ""
    cand = str(cand).strip().lower()
    if "conserv" in cand:
        return "CONSERVADORA"
    if "moder" in cand:
        return "MODERADA"
    if "sofist" in cand:
        return "SOFISTICADA"
    if "person" in cand or "custom" in cand or "personalizada" in cand:
        return "PERSONALIZADA"
    return "PERSONALIZADA"

# -------------------------
# Cabeçalho/Rodapé
# -------------------------
def draw_header(canvas, doc):
    canvas.saveState()
    page_width, page_height = A4

    left = doc.leftMargin
    right = page_width - doc.rightMargin
    top_y = page_height - 54  # posição já rebaixada

    # ====== Título e data (lado esquerdo) ======
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.setFont(BOLD_FONT, 18)  # alteração realizada aqui (título em 18)
    canvas.drawString(left, top_y, "Realocação de Portfólio")

    canvas.setFont(BASE_FONT, 10)  # alteração realizada aqui (data em 10)
    canvas.drawString(left, top_y - 20, DATA_HOJE_STR or _data_hoje_br())

    # ====== Contato (topo direito) ======
    contact_x = right
    contact_y = top_y
    canvas.setFont(BASE_FONT, 7)  # alteração realizada aqui (contato/endereço em 7)
    canvas.setFillColor(PRIMARY_COLOR)
    line_gap = 11
    for i, line in enumerate(CONTACT_LINES):
        canvas.drawRightString(contact_x, contact_y - i * line_gap, line)
    after_contact_y = contact_y - (len(CONTACT_LINES) - 1) * line_gap

    # ====== Linha divisória (mantida próxima do bloco de contato)
    line_y = min(top_y - 34, after_contact_y - 16)
    canvas.setStrokeColor(PRIMARY_COLOR)
    canvas.setLineWidth(0.6)
    canvas.line(left, line_y, right, line_y)

    # ====== Campos ======
    label_color = colors.HexColor("#5D6B7A")
    field_bg = colors.HexColor("#F1F3F5")
    field_radius = 4
    field_height = 16

    col_gap = 20
    col_width = (right - left - col_gap) / 2

    # Linha 1: Nome do cliente | Perfil de risco sugerido
    row1_label_y = line_y - 16
    row1_field_y = row1_label_y - 14

    # Nome do cliente
    canvas.setFillColor(label_color)
    canvas.setFont(BOLD_FONT, 9)
    canvas.drawString(left, row1_label_y, "Nome do cliente")

    canvas.setFillColor(field_bg)
    canvas.roundRect(left, row1_field_y - field_height + 2, col_width, field_height, field_radius, stroke=0, fill=1)
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.setFont(BOLD_FONT, 10)
    canvas.drawString(left + 6, row1_field_y - field_height + 5, (CLIENTE_NOME or "").upper())

    # Perfil de risco sugerido (label)
    perf_left = left + col_width + col_gap
    canvas.setFillColor(label_color)
    canvas.setFont(BOLD_FONT, 9)
    canvas.drawString(perf_left, row1_label_y, "Perfil de risco sugerido")

    # ---- Pílulas ocupando 100% da largura (sem caixa de fundo) ----
    pills = ["CONSERVADORA", "MODERADA", "SOFISTICADA", "PERSONALIZADA"]
    sel = (PERFIL_RISCO or "PERSONALIZADA").upper()
    pill_h = field_height
    pill_gap = 8
    pill_font = 8
    pad_x = 8

    pill_width = (col_width - (len(pills) - 1) * pill_gap) / len(pills)

    def fits(font_size, padding):
        maxw = max(canvas.stringWidth(p, BOLD_FONT, font_size) for p in pills)
        return (maxw + 2 * padding) <= pill_width

    while pill_font > 6 and not fits(pill_font, pad_x):
        pill_font -= 1
        if not fits(pill_font, pad_x) and pad_x > 6:
            pad_x -= 1

    start_x = perf_left
    start_y = row1_field_y - field_height + 2
    canvas.setFont(BOLD_FONT, pill_font)

    def draw_pill_fixed(x, y, text, selected, width):
        if selected:
            canvas.setFillColor(PRIMARY_COLOR)
            canvas.roundRect(x, y, width, pill_h, 8, stroke=0, fill=1)
            canvas.setFillColor(colors.whitesmoke)
        else:
            canvas.setFillColor(colors.white)
            canvas.setStrokeColor(PRIMARY_COLOR)
            canvas.roundRect(x, y, width, pill_h, 8, stroke=1, fill=1)
            canvas.setFillColor(PRIMARY_COLOR)
        canvas.drawCentredString(x + width / 2, y + 4, text)

    px = start_x
    for p in pills:
        draw_pill_fixed(px, start_y, p, p == sel, pill_width)
        px += pill_width + pill_gap

    # Linha 2: Nome de assessor | Aporte
    row2_label_y = row1_field_y - field_height - 12
    row2_field_y = row2_label_y - 14

    # Nome de assessor
    canvas.setFillColor(label_color)
    canvas.setFont(BOLD_FONT, 9)
    canvas.drawString(left, row2_label_y, "Nome de assessor")

    canvas.setFillColor(field_bg)
    canvas.roundRect(left, row2_field_y - field_height + 2, col_width, field_height, field_radius, stroke=0, fill=1)
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.setFont(BOLD_FONT, 10)
    canvas.drawString(left + 6, row2_field_y - field_height + 5, (NOME_ASSESSOR or "").upper())

    # Aporte
    canvas.setFillColor(label_color)
    canvas.setFont(BOLD_FONT, 9)
    canvas.drawString(perf_left, row2_label_y, "Aporte")

    canvas.setFillColor(field_bg)
    canvas.roundRect(perf_left, row2_field_y - field_height + 2, col_width, field_height, field_radius, stroke=0, fill=1)
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.setFont(BASE_FONT, 10)
    canvas.drawString(perf_left + 6, row2_field_y - field_height + 5, APORTE_TEXT or "Sem aporte")

    canvas.restoreState()

def draw_footer(canvas, doc):
    """
    Rodapé com o ÍCONE à esquerda e uma linha longa, como na referência enviada.
    """
    canvas.saveState()
    page_width, _ = A4

    left = 36                           # mesmo leftMargin padrão
    right = page_width - 36
    # --- Logo (ícone) à esquerda ---
    base_dir = os.path.dirname(__file__)
    logo_path = os.path.join(base_dir, "Logo_Criteria_Financial_Group_Cor_V2_RGB-01.png")
    x_logo = left                       # alteração realizada aqui
    target_w = 18                       # largura do ícone em pt (pequeno)  # alteração realizada aqui
    y_logo = 14                         # altura do logo a partir da base    # alteração realizada aqui
    try:
        img = ImageReader(logo_path)
        iw, ih = img.getSize()
        scale = target_w / float(iw)
        target_h = ih * scale
        canvas.drawImage(img, x_logo, y_logo, width=target_w, height=target_h, mask='auto')  # alteração realizada aqui
        # Linha alinhada verticalmente ao centro do ícone e começando após ele:
        y_line = y_logo + target_h / 2
        x_line_start = x_logo + target_w + 18   # gap após o ícone               # alteração realizada aqui
    except Exception:
        # se o logo não estiver disponível, coloca a linha em posição padrão
        y_line = 22
        x_line_start = left + 50

    x_line_end = right                       # vai até próximo da margem direita  # alteração realizada aqui
    canvas.setStrokeColor(PRIMARY_COLOR)
    canvas.setLineWidth(0.8)                 # linha fina e nítida                # alteração realizada aqui
    canvas.line(x_line_start, y_line, x_line_end, y_line)  # alteração realizada aqui

    canvas.restoreState()

# -------------------------
# Geração do PDF
# -------------------------
def generate_pdf(
    dist_df: pd.DataFrame,
    modelo_df: pd.DataFrame,
    resumo_df: pd.DataFrame,   # mantido para compatibilidade
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
    # Normalizações
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
        poss = [c for c in df_modelo.columns if "percentual" in c.lower()]
        if poss:
            df_modelo = df_modelo.rename(columns={poss[0]: "Percentual Ideal"})
        else:
            raise ValueError("modelo_df precisa conter a coluna 'Percentual Ideal'.")

    # Estado global para header
    global patrimonio_total, CLIENTE_NOME, NOME_ASSESSOR, DATA_HOJE_STR, PERFIL_RISCO, APORTE_TEXT
    CLIENTE_NOME = cliente_nome or ""
    NOME_ASSESSOR = nome_assessor or ""
    patrimonio_total = pd.to_numeric(df_dist["valor"], errors="coerce").fillna(0.0).sum()
    DATA_HOJE_STR = _data_hoje_br()
    PERFIL_RISCO = _inferir_perfil(sugestao)
    APORTE_TEXT = (sugestao or {}).get("aporte_text", "Sem aporte") or "Sem aporte"

    styles = getSampleStyleSheet()
    # Força Helvetica em todos os ParagraphStyles
    for s in styles.byName.values():
        s.textColor = PRIMARY_COLOR
        s.fontName = BASE_FONT

    elems = []

    # ===== Gráficos donut =====
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
            wedgeprops={'width': 0.30, 'edgecolor': 'white'}
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
            wedgeprops={'width': 0.30, 'edgecolor': 'white'}
        )
        ax.axis('equal')
        plt.tight_layout()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0)
        return buf

    # ===== Conteúdo do relatório =====
    buffer_relatorio = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer_relatorio,
        pagesize=A4,
        topMargin=220,   # respiro após o cabeçalho
        bottomMargin=70, # espaço para o novo rodapé
        leftMargin=36,
        rightMargin=36
    )

    elems.append(Spacer(1, 14))

    buf1, color_map = make_doughnut_atual(df_dist, "Percentual")
    buf2 = make_doughnut_modelo(df_modelo, "Percentual Ideal", color_map)

    # Tabela comparativa com barras
    header_small = ParagraphStyle(
        name="HeaderSmall", parent=styles["Normal"], alignment=TA_CENTER,
        fontName=BOLD_FONT, fontSize=8, leading=8, textColor=colors.whitesmoke
    )

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
        small = ParagraphStyle("Small", parent=styles["Normal"], fontName=BASE_FONT, fontSize=8, textColor=PRIMARY_COLOR,
                               alignment=TA_RIGHT if align=="right" else TA_LEFT)
        if align == "left":
            return Table([[b, Spacer(1,0), Paragraph(percent, small)]], colWidths=[4,1,None],
                         style=[("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),0)])
        else:
            return Table([[Paragraph(percent, small), Spacer(1,0), b]], colWidths=[None,1,4],
                         style=[("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),0)])

    rows = []
    small_center = ParagraphStyle("SmallCenter", parent=styles["Normal"], alignment=TA_CENTER, fontName=BASE_FONT, fontSize=7,
                                  wordWrap='CJK', keepAll=True, textColor=PRIMARY_COLOR)
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
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('BACKGROUND', (0,0), (-1,0), colors.gray),
        ('TEXTCOLOR', (0,1), (-1,-1), PRIMARY_COLOR),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))

    def titulo_com_traco(texto):
        sub = ParagraphStyle("SubHeader", parent=styles["Normal"], alignment=TA_CENTER,
                             fontName=BOLD_FONT, fontSize=9, spaceAfter=2, textColor=PRIMARY_COLOR, textTransform='uppercase')
        return Table([[Paragraph(texto, sub)],
                      [Table([[""]], colWidths="100%", style=[("LINEBELOW",(0,0),(-1,-1),0, PRIMARY_COLOR)])]],
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

    tbl1 = Table([dist_fmt.columns.tolist()] + dist_fmt.values.tolist(), hAlign='LEFT')
    tbl2 = Table([modelo_fmt.columns.tolist()] + modelo_fmt.values.tolist(), hAlign='LEFT')
    styl = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.gray),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('FONTNAME',(0,0),(-1,0),BOLD_FONT),
        ('FONTNAME',(0,1),(-1,-1),BASE_FONT),
        ('TEXTCOLOR',(0,1),(-1,-1),PRIMARY_COLOR),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('FONTSIZE',(0,0),(-1,0),10),
        ('FONTSIZE',(0,1),(-1,-1),8),
    ])
    tbl1.setStyle(styl); tbl2.setStyle(styl)

    title_center = ParagraphStyle(name="CenteredTitle", parent=styles["Heading2"], alignment=TA_CENTER,
                                  textColor=PRIMARY_COLOR, fontName=BOLD_FONT)
    elems.append(Table([[Paragraph("Carteira Atual", title_center), Paragraph("Carteira Proposta", title_center)]],
                       colWidths=[doc.width/2, doc.width/2], hAlign='CENTER'))
    elems.append(Table([[tbl1, tbl2]], colWidths=[doc.width/2, doc.width/2], hAlign='CENTER',
                       style=[('VALIGN',(0,0),(-1,-1),'TOP')]))

    # Página seguinte — Sugestão de Carteira (detalhada)
    elems.append(PageBreak())
    elems.append(Paragraph("Sugestão de Carteira",
                           ParagraphStyle(name="H2", parent=styles["Heading2"], fontName=BOLD_FONT)))
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
        ("TEXTCOLOR",(0,1),(-1,-1),PRIMARY_COLOR),
        ("FONTNAME",(0,0),(-1,0),BOLD_FONT),
        ("FONTSIZE",(0,0),(-1,0),10),
        ("ALIGN",(0,0),(-1,0),"CENTER"),
        ("VALIGN",(0,0),(-1,0),"MIDDLE"),
        ("FONTNAME",(0,1),(-1,-1),BASE_FONT),
        ("FONTSIZE",(0,1),(-1,-1),8),
        ("ALIGN",(0,1),(0,-1),"LEFT"),
        ("ALIGN",(1,1),(-1,-1),"CENTER"),
        ("VALIGN",(0,1),(-1,-1),"MIDDLE"),
    ])
    for i in classification_rows:
        style.add("BACKGROUND",(0,i),(-1,i),colors.lightgrey)
        style.add("FONTNAME",(0,i),(-1,i),BOLD_FONT)
    tbl.setStyle(style)
    elems.append(tbl)

    # Build do relatório — com header/footer
    def _on_page(canvas, doc):
        draw_header(canvas, doc)
        draw_footer(canvas, doc)

    doc.build(elems, onFirstPage=_on_page, onLaterPages=_on_page)
    buffer_relatorio.seek(0)

    # Concatenação final
    base_dir = os.path.dirname(__file__)
    capa_path    = os.path.join(base_dir, "capa.pdf")
    contra_path  = os.path.join(base_dir, "contra_capa.pdf")
    ultima_path  = os.path.join(base_dir, "ultima_pagina.pdf")

    writer = PdfWriter()
    for p in PdfReader(capa_path).pages: writer.add_page(p)
    for p in PdfReader(contra_path).pages: writer.add_page(p)
    for p in PdfReader(buffer_relatorio).pages: writer.add_page(p)
    for p in PdfReader(ultima_path).pages: writer.add_page(p)

    output_final = io.BytesIO()
    writer.write(output_final)
    output_final.seek(0)
    return output_final.read()
