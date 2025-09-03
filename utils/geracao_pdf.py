# utils/geracao_pdf.py
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Table, TableStyle, Paragraph, Spacer, Image, PageBreak
)
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
import re
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime

# === Matplotlib (headless)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from utils.cores import PALETTE

# =========================
# Estado global (para header)
# =========================
patrimonio_total = 0.0
CLIENTE_NOME = ""
NOME_ASSESSOR = ""

# Cores
PRIMARY_COLOR = colors.HexColor("#122940")
HLINE_COLOR   = colors.HexColor("#D6DBE2")  # cinza claro para linhas horizontais

# Variáveis do cabeçalho
DATA_HOJE_STR = ""
PERFIL_RISCO = "PERSONALIZADA"
APORTE_TEXT = "Sem aporte"

# Contato (topo direito)
CONTACT_LINES = [
    "Av. Magalhães de Castro, 4800 – 1º andar",
    "Continental Tower (Torre 3)",
    "Cidade Jardim Corporate Center",
    "São Paulo - SP, 05676-120",
    "+55 (11) 3124-9696",
    "www.criteriafg.com.br",
]

# Fontes
BASE_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"

# -------------------------
# Utilidades numéricas
# -------------------------
def _to_float_br(series) -> pd.Series:
    def conv(x):
        if pd.isna(x):
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "":
            return 0.0
        s = s.replace("R$", "").replace(" ", "").replace("%", "")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            return 0.0
    return series.apply(conv)

def _format_number_br(valor: float) -> str:
    try:
        v = float(valor)
    except Exception:
        return str(valor)
    s = f"{v:,.2f}"
    return s.replace(",", "v").replace(".", ",").replace("v", ".")

def _data_hoje_br() -> str:
    meses = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    hoje = datetime.today()
    return f"{hoje.day} de {meses[hoje.month-1]} de {hoje.year}"

def _inferir_perfil(sugestao: dict) -> str:
    cand = (sugestao or {}).get("perfil") or (sugestao or {}).get("carteira_modelo") or ""
    cand = str(cand).strip().lower()
    if "conserv" in cand: return "CONSERVADORA"
    if "moder" in cand:  return "MODERADA"
    if "sofist" in cand: return "SOFISTICADA"
    if "person" in cand or "custom" in cand or "personalizada" in cand: return "PERSONALIZADA"
    return "PERSONALIZADA"

# -------------------------
# Cabeçalho / Rodapé
# -------------------------
def draw_header(canvas, doc):
    canvas.saveState()
    page_width, page_height = A4

    left  = doc.leftMargin
    right = page_width - doc.rightMargin
    top_y = page_height - 36

    # Título e data
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.setFont(BOLD_FONT, 18)
    canvas.drawString(left, top_y, "Realocação de Portfólio")
    canvas.setFont(BASE_FONT, 10)
    canvas.drawString(left, top_y - 20, DATA_HOJE_STR or _data_hoje_br())

    # Contatos
    canvas.setFont(BASE_FONT, 7)
    line_gap = 11
    for i, line in enumerate(CONTACT_LINES):
        canvas.drawRightString(right, top_y - i*line_gap, line)

    # Linha divisória
    after_contact_y = top_y - (len(CONTACT_LINES)-1)*line_gap
    line_y = min(top_y - 34, after_contact_y - 16)
    canvas.setStrokeColor(PRIMARY_COLOR)
    canvas.setLineWidth(0.6)
    canvas.line(left, line_y, right, line_y)

    # Campos
    label_color = colors.HexColor("#5D6B7A")
    field_bg    = colors.HexColor("#F1F3F5")
    field_r     = 4
    field_h     = 16
    col_gap     = 20
    col_w       = (right - left - col_gap) / 2

    # Linha 1
    row1_label_y = line_y - 16
    row1_field_y = row1_label_y - 10

    # Nome do cliente
    canvas.setFillColor(label_color); canvas.setFont(BOLD_FONT, 9)
    canvas.drawString(left, row1_label_y, "Nome do cliente")
    canvas.setFillColor(field_bg)
    canvas.roundRect(left, row1_field_y - field_h + 2, col_w, field_h, field_r, stroke=0, fill=1)
    canvas.setFillColor(PRIMARY_COLOR); canvas.setFont(BOLD_FONT, 10)
    canvas.drawString(left + 6, row1_field_y - field_h + 5, (CLIENTE_NOME or "").upper())

    # Perfil
    perf_left = left + col_w + col_gap
    canvas.setFillColor(label_color); canvas.setFont(BOLD_FONT, 9)
    canvas.drawString(perf_left, row1_label_y, "Perfil de risco sugerido")

    pills     = ["CONSERVADORA","MODERADA","SOFISTICADA","PERSONALIZADA"]
    sel       = (PERFIL_RISCO or "PERSONALIZADA").upper()
    pill_h    = field_h
    pill_gap  = 8
    pill_font = 8
    pad_x     = 8
    pill_w    = (col_w - (len(pills)-1)*pill_gap) / len(pills)

    def fits(font_size, padding):
        maxw = max(canvas.stringWidth(p, BOLD_FONT, font_size) for p in pills)
        return (maxw + 2*padding) <= pill_w

    while pill_font > 6 and not fits(pill_font, pad_x):
        pill_font -= 1
        if not fits(pill_font, pad_x) and pad_x > 6:
            pad_x -= 1

    start_x = perf_left
    start_y = row1_field_y - field_h + 2
    canvas.setFont(BOLD_FONT, pill_font)

    def draw_pill(x, y, text, selected, width):
        if selected:
            canvas.setFillColor(PRIMARY_COLOR)
            canvas.roundRect(x, y, width, pill_h, 8, stroke=0, fill=1)
            canvas.setFillColor(colors.whitesmoke)
        else:
            canvas.setFillColor(colors.white)
            canvas.setStrokeColor(PRIMARY_COLOR)
            canvas.roundRect(x, y, width, pill_h, 8, stroke=1, fill=1)
            canvas.setFillColor(PRIMARY_COLOR)
        canvas.drawCentredString(x + width/2, y + 4, text)

    px = start_x
    for p in pills:
        draw_pill(px, start_y, p, p == sel, pill_w)
        px += pill_w + pill_gap

    # Linha 2
    row2_label_y = row1_field_y - field_h - 12
    row2_field_y = row2_label_y - 10

    # Assessor
    canvas.setFillColor(label_color); canvas.setFont(BOLD_FONT, 9)
    canvas.drawString(left, row2_label_y, "Nome de assessor")
    canvas.setFillColor(field_bg)
    canvas.roundRect(left, row2_field_y - field_h + 2, col_w, field_h, field_r, stroke=0, fill=1)
    canvas.setFillColor(PRIMARY_COLOR); canvas.setFont(BOLD_FONT, 10)
    canvas.drawString(left + 6, row2_field_y - field_h + 5, (NOME_ASSESSOR or "").upper())

    # Aporte
    canvas.setFillColor(label_color); canvas.setFont(BOLD_FONT, 9)
    canvas.drawString(perf_left, row2_label_y, "Aporte")
    canvas.setFillColor(field_bg)
    canvas.roundRect(perf_left, row2_field_y - field_h + 2, col_w, field_h, field_r, stroke=0, fill=1)
    canvas.setFillColor(PRIMARY_COLOR); canvas.setFont(BASE_FONT, 10)
    canvas.drawString(perf_left + 6, row2_field_y - field_h + 5, APORTE_TEXT or "Sem aporte")

    # Linha inferior do cabeçalho
    base_boxes_y = row2_field_y - field_h + 2
    footer_line_y = base_boxes_y - 6
    canvas.setStrokeColor(PRIMARY_COLOR); canvas.setLineWidth(0.6)
    canvas.line(left, footer_line_y, right, footer_line_y)

    canvas.restoreState()

def draw_footer(canvas, doc):
    canvas.saveState()
    page_width, _ = A4
    left  = doc.leftMargin
    right = page_width - doc.rightMargin

    base_dir  = os.path.dirname(__file__)
    logo_path = os.path.join(base_dir, "c-com-fundo-branco.png")
    logo_w_target = 44
    try:
        img = ImageReader(logo_path)
        iw, ih = img.getSize()
        scale  = logo_w_target / float(iw)
        logo_w = logo_w_target
        logo_h = ih * scale
        x_img, y_img = left, 12
        canvas.drawImage(img, x_img, y_img, width=logo_w, height=logo_h, mask='auto')
    except Exception:
        logo_w = 0; logo_h = 0
        x_img, y_img = left, 24

    y_line  = y_img + (logo_h/2 if logo_h else 10)
    x_start = x_img + logo_w + 12
    canvas.setStrokeColor(PRIMARY_COLOR); canvas.setLineWidth(0.6)
    canvas.line(x_start, y_line, right, y_line)
    canvas.restoreState()

# -------------------------
# PDF
# -------------------------
def generate_pdf(
    dist_df: pd.DataFrame,
    modelo_df: pd.DataFrame,
    resumo_df: pd.DataFrame,  # compat.
    sugestao: dict,
    ativos_df: pd.DataFrame,
    cliente_nome: str = "",
    nome_assessor: str = "",
) -> bytes:

    # --- Normalizações
    df_dist = dist_df.copy()
    if "valor" not in df_dist.columns and "valor_atual" in df_dist.columns:
        df_dist = df_dist.rename(columns={"valor_atual": "valor"})
    df_dist["valor"] = _to_float_br(df_dist["valor"])
    if "Percentual" not in df_dist.columns:
        total_val = df_dist["valor"].sum()
        df_dist["Percentual"] = (df_dist["valor"] / total_val * 100) if total_val else 0.0

    df_modelo = modelo_df.copy()
    if "Percentual Ideal" not in df_modelo.columns:
        poss = [c for c in df_modelo.columns if "percentual" in c.lower()]
        if poss:
            df_modelo = df_modelo.rename(columns={poss[0]: "Percentual Ideal"})
        else:
            raise ValueError("modelo_df precisa conter a coluna 'Percentual Ideal'.")
    df_modelo["Percentual Ideal"] = _to_float_br(df_modelo["Percentual Ideal"])

    # Estado global para header
    global patrimonio_total, CLIENTE_NOME, NOME_ASSESSOR, DATA_HOJE_STR, PERFIL_RISCO, APORTE_TEXT
    CLIENTE_NOME = cliente_nome or ""
    NOME_ASSESSOR = nome_assessor or ""
    patrimonio_total = df_dist["valor"].sum()
    DATA_HOJE_STR = _data_hoje_br()
    PERFIL_RISCO  = _inferir_perfil(sugestao)
    APORTE_TEXT   = (sugestao or {}).get("aporte_text", "Sem aporte") or "Sem aporte"

    styles = getSampleStyleSheet()
    for s in styles.byName.values():
        s.textColor = PRIMARY_COLOR
        s.fontName  = BASE_FONT

    # ••• Estilo de títulos reutilizável
    title_center = ParagraphStyle(name="CenteredTitle", parent=styles["Heading2"],
                                  alignment=TA_CENTER, textColor=PRIMARY_COLOR,
                                  fontName=BOLD_FONT)

    elems = []

    # ===== Gráficos donut
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
        ax.axis('equal'); plt.tight_layout()
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
        ax.axis('equal'); plt.tight_layout()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0)
        return buf

    # ===== Documento sem paddings
    buffer_relatorio = io.BytesIO()
    doc = BaseDocTemplate(
        buffer_relatorio, pagesize=A4,
        leftMargin=36, rightMargin=36, topMargin=202, bottomMargin=70
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id='normal')

    def _on_page(canvas, doc_):
        draw_header(canvas, doc_)
        draw_footer(canvas, doc_)

    doc.addPageTemplates(PageTemplate(id='OneCol', frames=[frame], onPage=_on_page))

    elems.append(Spacer(1, 14))

    buf1, color_map = make_doughnut_atual(df_dist, "Percentual")
    buf2 = make_doughnut_modelo(df_modelo, "Percentual Ideal", color_map)

    # ===== Tabela comparativa central (barras)
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
        b.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), colors.HexColor(color) if isinstance(color,str) else color),
            ("BOX",(0,0),(-1,-1),0, colors.white)
        ]))
        small = ParagraphStyle("Small", parent=styles["Normal"], fontName=BASE_FONT, fontSize=8, textColor=PRIMARY_COLOR,
                               alignment=TA_RIGHT if align=="right" else TA_LEFT)
        if align == "left":
            return Table([[b, Spacer(1,0), Paragraph(percent, small)]], colWidths=[4,1,None],
                         style=[("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),0)])
        else:
            return Table([[Paragraph(percent, small), Spacer(1,0), b]], colWidths=[None,1,4],
                         style=[("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),0)])

    rows = []
    small_center = ParagraphStyle("SmallCenter", parent=styles["Normal"], alignment=TA_CENTER,
                                  fontName=BASE_FONT, fontSize=7, wordWrap='CJK', keepAll=True, textColor=PRIMARY_COLOR)
    for _, r in temp_df.iterrows():
        color = color_map.get(r["Classificação"], "#000000")
        rows.append([bar(color,"left",r["Atual"]), Paragraph(str(r["Classificação"]), small_center), bar(color,"right",r["Modelo"])])

    comp_tbl = Table([["Atual (%)","Classificação","Proposta (%)"]] + rows, colWidths=[63,84,63], hAlign='CENTER')
    comp_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,1),(0,-1),0), ('RIGHTPADDING',(-1,1),(-1,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),2), ('BOTTOMPADDING',(0,0),(-1,-1),2),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('BACKGROUND',(0,0),(-1,0),colors.gray),
        ('TEXTCOLOR',(0,1),(-1,-1),PRIMARY_COLOR),
        # Linhas horizontais (sem verticais)
        ('LINEABOVE',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,1),(-1,-1),0.3,HLINE_COLOR),
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

    # ===== Tabelas "Carteira Atual" x "Proposta"
    dist_fmt = df_dist.copy().sort_values(by="valor", ascending=False)
    dist_fmt["Valor"] = dist_fmt["valor"].apply(_format_number_br)
    dist_fmt["% PL"]  = dist_fmt["Percentual"].apply(lambda x: _format_number_br(x) + "%")
    dist_fmt = dist_fmt[["Classificação", "Valor", "% PL"]]

    modelo_fmt = df_modelo.copy()
    if "Valor Ideal (R$)" in modelo_fmt.columns:
        modelo_fmt["valor"] = _to_float_br(modelo_fmt["Valor Ideal (R$)"])
    else:
        base_total = patrimonio_total
        perc = _to_float_br(modelo_fmt["Percentual Ideal"])
        modelo_fmt["valor"] = base_total * (perc / 100.0)
    modelo_fmt = modelo_fmt.sort_values(by="valor", ascending=False)
    modelo_fmt["Valor"] = modelo_fmt["valor"].apply(_format_number_br)
    modelo_fmt["% PL"]  = modelo_fmt["Percentual Ideal"].apply(lambda x: _format_number_br(x) + "%")
    modelo_fmt = modelo_fmt[["Classificação", "Valor", "% PL"]]

    GAP = 20
    half = (doc.width - GAP) / 2
    colspec = [half*0.55, half*0.25, half*0.20]

    tbl1 = Table([dist_fmt.columns.tolist()] + dist_fmt.values.tolist(), colWidths=colspec, hAlign='LEFT')
    tbl2 = Table([modelo_fmt.columns.tolist()] + modelo_fmt.values.tolist(), colWidths=colspec, hAlign='LEFT')

    styl_common = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.gray),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('FONTNAME',(0,0),(-1,0),BOLD_FONT),
        ('FONTNAME',(0,1),(-1,-1),BASE_FONT),
        ('TEXTCOLOR',(0,1),(-1,-1),PRIMARY_COLOR),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('FONTSIZE',(0,0),(-1,0),10),
        ('FONTSIZE',(0,1),(-1,-1),8),
        ('LEFTPADDING',(0,0),(-1,-1),6),
        ('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',(0,0),(-1,-1),2),
        ('BOTTOMPADDING',(0,0),(-1,-1),2),
        # Linhas horizontais (sem verticais)
        ('LINEABOVE',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,1),(-1,-1),0.3,HLINE_COLOR),
    ])
    tbl1.setStyle(styl_common); tbl2.setStyle(styl_common)

    elems.append(Table([[Paragraph("Carteira Atual", title_center), "", Paragraph("Carteira Proposta", title_center)]],
                       colWidths=[half, GAP, half], hAlign='LEFT',
                       style=[('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(-1,-1),0),
                              ('TOPPADDING',(0,0),(-1,-1),0), ('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    elems.append(Table([[tbl1, "", tbl2]], colWidths=[half, GAP, half], hAlign='LEFT',
                       style=[('VALIGN',(0,0),(-1,-1),'TOP'),
                              ('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(-1,-1),0),
                              ('TOPPADDING',(0,0),(-1,-1),0), ('BOTTOMPADDING',(0,0),(-1,-1),0)]))

    # ======================= Gráfico de Liquidez =======================
    def _extract_days(liq):
        m = re.search(r"D\+(\d+)", str(liq))
        return int(m.group(1)) if m else None

    ativos_local = ativos_df.copy()
    ativos_local["days"] = ativos_local["Liquidez"].apply(_extract_days)

    def _classify(row):
        d = row["days"]; liq = str(row["Liquidez"]).lower()
        if d is None: return "D+0"
        if d > 180: return "Acima de D+180"
        if d > 60:  return "Até D+180"
        if d > 15:  return "Até D+60"
        if d > 5:   return "Até D+15"
        if d > 0:   return "Até D+5"
        if d == 0 and "à mercado" in liq: return "D+0 (à mercado)"
        return "D+0"

    ativos_local["Faixa"] = ativos_local.apply(_classify, axis=1)

    valor_col = "Novo Valor" if "Novo Valor" in ativos_local.columns else "valor_atual"
    liq_faixas = (
        ativos_local.assign(valor=_to_float_br(ativos_local[valor_col]))
                   .groupby("Faixa")["valor"].sum()
                   .reindex(["Acima de D+180","Até D+180","Até D+60","Até D+15","Até D+5","D+0","D+0 (à mercado)"], fill_value=0.0)
                   .reset_index()
    )

    cinza_txt = "#6B7280"
    buf_liq = io.BytesIO()
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    y_labels = ["Acima de D+180","Até D+180","Até D+60","Até D+15","Até D+5","D+0","D+0 (à mercado)"]
    y_pos = list(range(len(y_labels)))
    valores = [liq_faixas.set_index("Faixa").loc[l, "valor"] for l in y_labels]

    bars = ax.barh(y_pos, valores, height=0.70)
    ax.set_yticks(y_pos, labels=y_labels)
    ax.invert_yaxis()  # garante o "Acima de D+180" no topo
    ax.tick_params(axis='y', labelsize=8, colors=cinza_txt, length=0)
    ax.set_ylabel("Faixa", fontsize=9, color=cinza_txt)
    ax.set_xlabel(""); ax.set_xticks([]); ax.tick_params(axis='x', length=0, colors=cinza_txt)
    for side in ["bottom","top","right","left"]:
        ax.spines[side].set_visible(False)
    max_v = max(valores) if valores else 0.0
    ax.set_xlim(0, max_v*1.15 if max_v > 0 else 1)
    for rect, val in zip(bars, valores):
        if val <= 0: continue
        txt = _format_number_br(val)
        ax.text(rect.get_width() + (max_v*0.012 if max_v else 0.02),
                rect.get_y() + rect.get_height()/2, txt,
                va='center', ha='left', fontsize=9, color=cinza_txt)
    plt.tight_layout(pad=1.0)
    fig.savefig(buf_liq, format='PNG', dpi=150, bbox_inches='tight')
    plt.close(fig); buf_liq.seek(0)

    elems.append(Spacer(1, 22))
    elems.append(Paragraph("Liquidez da carteira proposta (R$)",
                           ParagraphStyle(name="H2_LIQ", parent=styles["Heading2"],
                                          fontName=BOLD_FONT, alignment=TA_CENTER)))
    elems.append(Spacer(1, 6))
    elems.append(Image(buf_liq, width=doc.width, height=182))

    # ======= NOVA PÁGINA: Diferenças / Alocados / Resgatados =======  # alteração realizada aqui
    elems.append(PageBreak())  # começa a nova página logo após os gráficos

    # -- Diferenças entre Atual e Sugerida --
    all_classes = set(df_dist["Classificação"]).union(set(df_modelo["Classificação"]))
    resumo_rows = []
    for cls in sorted(all_classes, key=lambda x: str(x)):
        pa = float(df_dist.loc[df_dist["Classificação"] == cls, "Percentual"].sum())
        ps = float(df_modelo.loc[df_modelo["Classificação"] == cls, "Percentual Ideal"].sum())
        adj = round(ps - pa, 2)
        resumo_rows.append([cls,
                            _format_number_br(pa) + "%",                 # Atual (%)
                            _format_number_br(ps) + "%",                 # Sugerida (%)
                            _format_number_br(adj) + "%",                # Ajuste (%)
                            "Aumentar" if adj > 0 else ("Reduzir" if adj < 0 else "Inalterado")])

    dif_cols = ["Classificação","Atual (%)","Sugerida (%)","Ajuste (%)","Ação"]
    dif_tbl = Table([dif_cols] + resumo_rows,
                    colWidths=[doc.width*0.34, doc.width*0.16, doc.width*0.16, doc.width*0.16, doc.width*0.18],
                    hAlign='LEFT')
    dif_tbl.setStyle(styl_common)  # mesmo estilo das tabelas principais
    elems.append(Paragraph("Diferenças entre Atual e Sugerida", title_center))  # título
    elems.append(dif_tbl)
    elems.append(Spacer(1, 18))

    # -- Ativos Alocados --
    if "Valor Realocado" in ativos_df.columns:
        alocados = ativos_df.copy()
        for c in ["valor_atual", "Novo Valor", "Valor Realocado"]:
            if c in alocados.columns:
                alocados[c] = _to_float_br(alocados[c])
        alocados = alocados[alocados["Valor Realocado"] > 0].copy()
        alocados = alocados.rename(columns={"estrategia": "Ativo"})
        if not alocados.empty:
            alocados["Valor Atual (R$)"]     = alocados["valor_atual"].apply(_format_number_br)
            alocados["Novo Valor (R$)"]      = alocados["Novo Valor"].apply(_format_number_br)
            alocados["Valor Realocado (R$)"] = alocados["Valor Realocado"].apply(_format_number_br)
            cols_a = ["Classificação","Ativo","Valor Atual (R$)","Valor Realocado (R$)","Novo Valor (R$)"]
            alocados_tbl = Table([cols_a] + alocados[cols_a].values.tolist(),
                                 colWidths=[doc.width*0.18, doc.width*0.52, doc.width*0.10, doc.width*0.10, doc.width*0.10],
                                 hAlign='LEFT')
            alocados_tbl.setStyle(styl_common)
            elems.append(Paragraph("Ativos Alocados", title_center))
            elems.append(alocados_tbl)
            elems.append(Spacer(1, 18))
        else:
            elems.append(Paragraph("Ativos Alocados", title_center))
            elems.append(Paragraph("_Nenhum ativo alocado._", styles["Italic"]))
            elems.append(Spacer(1, 18))

        # -- Ativos Resgatados --
        resgatados = ativos_df.copy()
        for c in ["valor_atual", "Novo Valor", "Valor Realocado"]:
            if c in resgatados.columns:
                resgatados[c] = _to_float_br(resgatados[c])
        resgatados = resgatados[resgatados["Valor Realocado"] < 0].copy()
        resgatados = resgatados.rename(columns={"estrategia": "Ativo"})
        if not resgatados.empty:
            resgatados["Valor Atual (R$)"]     = resgatados["valor_atual"].apply(_format_number_br)
            resgatados["Novo Valor (R$)"]      = resgatados["Novo Valor"].apply(_format_number_br)
            resgatados["Valor Realocado (R$)"] = resgatados["Valor Realocado"].apply(_format_number_br)
            cols_r = ["Classificação","Ativo","Valor Atual (R$)","Valor Realocado (R$)","Novo Valor (R$)"]
            resgatados_tbl = Table([cols_r] + resgatados[cols_r].values.tolist(),
                                   colWidths=[doc.width*0.18, doc.width*0.52, doc.width*0.10, doc.width*0.10, doc.width*0.10],
                                   hAlign='LEFT')
            resgatados_tbl.setStyle(styl_common)
            elems.append(Paragraph("Ativos Resgatados", title_center))
            elems.append(resgatados_tbl)
            elems.append(Spacer(1, 6))
        else:
            elems.append(Paragraph("Ativos Resgatados", title_center))
            elems.append(Paragraph("_Nenhum ativo resgatado._", styles["Italic"]))
            elems.append(Spacer(1, 6))

    # --- Página seguinte — Sugestão de Carteira (detalhada)
    elems.append(PageBreak())  # esta página vem após a nova página  # alteração realizada aqui
    elems.append(Paragraph("Sugestão de Carteira",
                           ParagraphStyle(name="H2", parent=styles["Heading2"], fontName=BOLD_FONT)))
    elems.append(Spacer(1, 12))

    data = [["Ativo","Capital Alocado","% PL"]]
    classification_rows = []; row_idx = 1
    total_sug = pd.to_numeric(ativos_df["Novo Valor"], errors="coerce").fillna(0.0).sum()

    class_sums = (ativos_df.assign(_novo=pd.to_numeric(ativos_df["Novo Valor"], errors="coerce").fillna(0.0))
                           .groupby("Classificação")["_novo"].sum().sort_values(ascending=False))
    for categoria, soma_val in class_sums.items():
        soma_pct = (soma_val/total_sug*100) if total_sug else 0.0
        data.append([str(categoria).upper(), _format_number_br(soma_val), f"{soma_pct:.2f}".replace(".", ",") + "%"])
        classification_rows.append(row_idx); row_idx += 1

        grp = (ativos_df[ativos_df["Classificação"] == categoria]
               .assign(_novo=pd.to_numeric(ativos_df.loc[ativos_df["Classificação"] == categoria, "Novo Valor"], errors="coerce").fillna(0.0))
               .sort_values("_novo", ascending=False))
        for _, r in grp.iterrows():
            nome_ativo = unicodedata.normalize("NFKC", str(r.get("estrategia",""))).replace("\uFFFD","").replace("\xa0"," ").strip()
            nv = float(r.get("Novo Valor", 0.0)) if pd.notna(r.get("Novo Valor", 0.0)) else 0.0
            data.append([nome_ativo, _format_number_br(nv),
                        (f"{(nv/total_sug*100):.2f}".replace(".", ",") + "%") if total_sug else "0,00%"])
            row_idx += 1

    tbl = Table(data, colWidths=[doc.width*0.6, doc.width*0.2, doc.width*0.2], hAlign="LEFT", repeatRows=1)
    style = TableStyle([
        # Cabeçalho
        ("BACKGROUND",(0,0),(-1,0),colors.gray),
        ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),
        ("FONTNAME",(0,0),(-1,0),BOLD_FONT),
        ("FONTSIZE",(0,0),(-1,0),10),
        ("ALIGN",(0,0),(-1,0),"CENTER"),
        ("VALIGN",(0,0),(-1,0),"MIDDLE"),
        # Corpo
        ("TEXTCOLOR",(0,1),(-1,-1),PRIMARY_COLOR),
        ("FONTNAME",(0,1),(-1,-1),BASE_FONT),
        ("FONTSIZE",(0,1),(-1,-1),8),
        ("ALIGN",(0,1),(0,-1),"LEFT"),
        ("ALIGN",(1,1),(-1,-1),"CENTER"),
        ("VALIGN",(0,1),(-1,-1),"MIDDLE"),
        # Linhas horizontais (sem verticais)
        ('LINEABOVE',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,1),(-1,-1),0.3,HLINE_COLOR),
    ])
    for i in classification_rows:
        style.add("BACKGROUND",(0,i),(-1,i),colors.lightgrey)
        style.add("FONTNAME",(0,i),(-1,i),BOLD_FONT)
    tbl.setStyle(style)
    elems.append(tbl)

    # Build
    doc.build(elems)

    # Concatenação final
    base_dir  = os.path.dirname(__file__)
    capa_path = os.path.join(base_dir, "capa.pdf")
    contra_path = os.path.join(base_dir, "contra_capa.pdf")
    ultima_path = os.path.join(base_dir, "ultima_pagina.pdf")

    writer = PdfWriter()
    for p in PdfReader(capa_path).pages: writer.add_page(p)
    for p in PdfReader(contra_path).pages: writer.add_page(p)
    for p in PdfReader(buffer_relatorio).pages: writer.add_page(p)
    for p in PdfReader(ultima_path).pages: writer.add_page(p)

    out = io.BytesIO()
    writer.write(out); out.seek(0)
    return out.read()
