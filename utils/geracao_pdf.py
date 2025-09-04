# utils/geracao_pdf.py
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Table, TableStyle, Paragraph, Spacer, Image, PageBreak
)
from reportlab.platypus import Table as InnerTable
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.utils import ImageReader
import pandas as pd
import io
import os
import unicodedata
import re
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
from reportlab.platypus.flowables import KeepInFrame

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
HLINE_COLOR   = colors.HexColor("#D6DBE2")   # cinza claro para linhas horizontais
HEADER_BG     = colors.lightgrey             # igual ao fundo dos grupos da “Sugestão de Carteira”

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
        if pd.isna(x): return 0.0
        if isinstance(x, (int, float)): return float(x)
        s = str(x).strip()
        if s == "": return 0.0
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

def _normalize_text(s: str) -> str:
    s = str(s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("M"))
    return s

def _first_nonempty(d: dict, keys):
    for k in keys:
        cur = d
        ok = True
        for part in k.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and str(cur).strip() not in ("", "None"):
            return cur
    return ""

def _inferir_perfil(sugestao: dict) -> str:
    sug = sugestao or {}
    cand = _first_nonempty(sug, [
        "carteira_modelo", "perfil", "perfil_sugerido", "perfil_risco",
        "profile", "risk_profile"
    ])
    codigo = _first_nonempty(sug, ["perfil_codigo", "perfil_id", "perfilCode", "risk_code"])
    code = str(codigo).strip().upper()
    if code in {"1","C","CONS","CONSERVADOR","CONSERVADORA"}: return "CONSERVADORA"
    if code in {"2","M","MOD","MODERADO","MODERADA"}:         return "MODERADA"
    if code in {"3","S","A","ARROJADO","SOFISTICADO","SOFISTICADA"}: return "SOFISTICADA"
    if code in {"4","P","PERSONALIZADO","PERSONALIZADA"}:     return "PERSONALIZADA"

    c = _normalize_text(cand)
    if any(k in c for k in ["conserv", "consev", "defensiv", "baixo risco"]): return "CONSERVADORA"
    if any(k in c for k in ["moder", "balancead", "medio risco"]):            return "MODERADA"
    if any(k in c for k in ["sofist", "arroj", "agress", "alto risco"]):      return "SOFISTICADA"
    if any(k in c for k in ["person", "custom", "sob medida", "personaliz"]): return "PERSONALIZADA"
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
    canvas.setFillColor(PRIMARY_COLOR); canvas.setFont(BASE_FONT, 10)  # sem negrito
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
    canvas.setFillColor(PRIMARY_COLOR); canvas.setFont(BASE_FONT, 10)  # sem negrito
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

    # modelo (mantido para fallback apenas)
    df_modelo = modelo_df.copy()
    if "Percentual Ideal" not in df_modelo.columns:
        poss = [c for c in df_modelo.columns if "percentual" in c.lower()]
        if poss:
            df_modelo = df_modelo.rename(columns={poss[0]: "Percentual Ideal"})
        else:
            raise ValueError("modelo_df precisa conter a coluna 'Percentual Ideal'.")
    df_modelo["Percentual Ideal"] = _to_float_br(df_modelo["Percentual Ideal"])

    # --- Proposta REAL (do que foi editado na Etapa 4/5): soma de Novo Valor
    df_prop = None
    if isinstance(ativos_df, pd.DataFrame) and ("Novo Valor" in ativos_df.columns or "valor_sugerido" in ativos_df.columns):
        col_nv = "Novo Valor" if "Novo Valor" in ativos_df.columns else "valor_sugerido"
        df_prop = (ativos_df.copy()
                   .assign(valor=_to_float_br(ativos_df[col_nv]))
                   .groupby("Classificação", as_index=False)["valor"].sum())
        total_prop = df_prop["valor"].sum()
        df_prop["Percentual"] = (df_prop["valor"]/total_prop*100) if total_prop else 0.0
    if df_prop is None:
        df_prop = df_modelo.rename(columns={"Percentual Ideal": "Percentual"}).copy()
        try:
            ap = float(_to_float_br(pd.Series([(sugestao or {}).get("aporte_valor", 0.0)]))[0])
        except Exception:
            ap = 0.0
        base_total = float(df_dist["valor"].sum()) + max(ap, 0.0)
        perc = _to_float_br(df_prop["Percentual"])
        df_prop["valor"] = base_total * (perc / 100.0)

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

    # atual vs proposta (proposta = df_prop)
    buf1, color_map = make_doughnut_atual(df_dist, "Percentual")
    buf2 = make_doughnut_modelo(df_prop, "Percentual", color_map)

    # ===== Tabela comparativa central (barras)
    temp_df = pd.DataFrame({
        "Classificação": list(dict.fromkeys(list(df_dist["Classificação"]) + list(df_prop["Classificação"])))
    })
    temp_df["Atual"]    = temp_df["Classificação"].map(lambda x: df_dist.loc[df_dist["Classificação"] == x, "Percentual"].sum())
    temp_df["Proposta"] = temp_df["Classificação"].map(lambda x: df_prop.loc[df_prop["Classificação"] == x, "Percentual"].sum())
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
                               alignment=TA_RIGHT if align=="right" else TA_RIGHT)
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
        rows.append([bar(color,"left",r["Atual"]), Paragraph(str(r["Classificação"]), small_center), bar(color,"right",r["Proposta"])])

    comp_tbl = Table([["Atual (%)","Classificação","Proposta (%)"]] + rows, colWidths=[63,84,63], hAlign='CENTER')
    comp_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        # cabeçalho com a MESMA cor da sugestão de carteira e texto preto
        ('BACKGROUND',(0,0),(-1,0),HEADER_BG),
        ('TEXTCOLOR',(0,0),(-1,0),colors.black),
        ('LEFTPADDING',(0,1),(0,-1),0), ('RIGHTPADDING',(-1,1),(-1,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),2), ('BOTTOMPADDING',(0,0),(-1,-1),2),
        ('TEXTCOLOR',(0,1),(-1,-1),PRIMARY_COLOR),
        # Linhas horizontais
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
    elems.append(Spacer(1, 18))

    # ===== Tabelas "Carteira Atual" x "Proposta" (Proposta = df_prop)
    dist_fmt = df_dist.copy().sort_values(by="valor", ascending=False)
    dist_fmt["Valor"] = dist_fmt["valor"].apply(_format_number_br)
    dist_fmt["% PL"]  = dist_fmt["Percentual"].apply(lambda x: _format_number_br(x) + "%")
    dist_fmt = dist_fmt[["Classificação", "Valor", "% PL"]]

    prop_fmt = df_prop.copy().sort_values(by="valor", ascending=False)
    prop_fmt["Valor"] = prop_fmt["valor"].apply(_format_number_br)
    prop_fmt["% PL"]  = prop_fmt["Percentual"].apply(lambda x: _format_number_br(x) + "%")
    prop_fmt = prop_fmt[["Classificação", "Valor", "% PL"]]

    GAP = 20
    half = (doc.width - GAP) / 2
    colspec = [half*0.55, half*0.25, half*0.20]

    tbl1 = Table([dist_fmt.columns.tolist()] + dist_fmt.values.tolist(), colWidths=colspec, hAlign='LEFT')
    tbl2 = Table([prop_fmt.columns.tolist()] + prop_fmt.values.tolist(), colWidths=colspec, hAlign='LEFT')

    styl_common = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),HEADER_BG),       # cabeçalho na cor pedida
        ('TEXTCOLOR',(0,0),(-1,0),colors.black),     # texto preto
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
        ('LINEABOVE',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,1),(-1,-1),0.3,HLINE_COLOR),
    ])
    tbl1.setStyle(styl_common); tbl2.setStyle(styl_common)

    title_center = ParagraphStyle(name="CenteredTitle", parent=styles["Heading2"], alignment=TA_CENTER,
                                  textColor=PRIMARY_COLOR, fontName=BOLD_FONT)

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
    fig, ax = plt.subplots(figsize=(7.5, 2.4))
    y_labels = ["Acima de D+180","Até D+180","Até D+60","Até D+15","Até D+5","D+0","D+0 (à mercado)"]
    y_pos = list(range(len(y_labels)))
    valores = [liq_faixas.set_index("Faixa").loc[l, "valor"] for l in y_labels]

    bars = ax.barh(y_pos, valores, height=0.70)
    ax.set_yticks(y_pos, labels=y_labels)
    ax.invert_yaxis()
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
    plt.tight_layout(pad=0.6)
    fig.savefig(buf_liq, format='PNG', dpi=150, bbox_inches='tight')
    plt.close(fig); buf_liq.seek(0)

    elems.append(Spacer(1, 8))
    elems.append(Paragraph(
        "Liquidez da carteira proposta (R$)",
        ParagraphStyle(name="H2_LIQ", parent=styles["Heading2"], fontName=BOLD_FONT, alignment=TA_CENTER, spaceAfter=2)
    ))
    elems.append(Spacer(1, 2))

    liq_img_h = max(120, min(165, int(doc.height * 0.24)))
    liq_img   = Image(buf_liq, width=doc.width, height=liq_img_h)
    liq_img._preserveAspectRatio = True  # manter proporção
    elems.append(KeepInFrame(maxWidth=doc.width, maxHeight=liq_img_h, content=[liq_img], mode='shrink'))

    # =================================================================
    # NOVA PÁGINA: Diferenças / Ativos Alocados / Ativos Resgatados
    # =================================================================
    elems.append(PageBreak())

    hdr9 = ParagraphStyle("Hdr9", parent=styles["Normal"], fontName=BOLD_FONT,
                          fontSize=9, alignment=TA_CENTER, textColor=colors.black,  # texto preto
                          wordWrap="CJK")
    cell_wrap = ParagraphStyle("CellWrap", parent=styles["Normal"], fontName=BASE_FONT,
                               fontSize=8, textColor=PRIMARY_COLOR, wordWrap="CJK")

    # 1) Diferenças entre Atual e Sugerida (Sugerida = df_prop)
    all_classes = set(df_dist["Classificação"]).union(set(df_prop["Classificação"]))
    linhas = []
    for cls in all_classes:
        pa = float(df_dist.loc[df_dist["Classificação"] == cls, "Percentual"].sum())
        ps = float(df_prop.loc[df_prop["Classificação"] == cls, "Percentual"].sum())
        adj = round(ps - pa, 2)
        linhas.append({
            "Classificação": cls,
            "Atual (%)": pa,
            "Sugerida (%)": ps,
            "AjusteNum": adj,
            "Ajuste (%)": adj,
            "Ação": "Aumentar" if adj > 0 else ("Reduzir" if adj < 0 else "Inalterado")
        })

    dif_df = pd.DataFrame(linhas).sort_values("AjusteNum", ascending=False).reset_index(drop=True)
    dif_df["Atual (%)"]    = dif_df["Atual (%)"].apply(lambda v: _format_number_br(v) + "%")
    dif_df["Sugerida (%)"] = dif_df["Sugerida (%)"].apply(lambda v: _format_number_br(v) + "%")
    dif_df["Ajuste (%)"]   = dif_df["Ajuste (%)"].apply(lambda v: _format_number_br(v) + "%")

    def _cw_with_cushion(pcts):
        avail = doc.width - 12
        s = sum(pcts)
        return [avail * (p/s) for p in pcts]

    dif_colwidths = _cw_with_cushion([34, 16, 16, 16, 18])

    dif_tbl = Table([["Classificação","Atual (%)","Sugerida (%)","Ajuste (%)","Ação"]] + dif_df[["Classificação","Atual (%)","Sugerida (%)","Ajuste (%)","Ação"]].values.tolist(),
                    colWidths=dif_colwidths, hAlign='LEFT')

    # >>> header com fundo igual ao da “Sugestão de Carteira” e texto preto
    dif_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),HEADER_BG),
        ('TEXTCOLOR',(0,0),(-1,0),colors.black),
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
        ('LINEABOVE',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,0),(-1,0),0.4,HLINE_COLOR),
        ('LINEBELOW',(0,1),(-1,-1),0.3,HLINE_COLOR),
    ]))
    # <<<

    elems.append(Paragraph("Diferenças entre Atual e Sugerida", ParagraphStyle(name="T", parent=styles["Heading2"], alignment=TA_CENTER, fontName=BOLD_FONT)))
    elems.append(dif_tbl)
    elems.append(Spacer(1, 18))

    # 2) Ativos Alocados / 3) Resgatados
    if "Valor Realocado" in ativos_df.columns:
        alocados = ativos_df.copy()
        for c in ["valor_atual", "Novo Valor", "Valor Realocado"]:
            if c in alocados.columns:
                alocados[c] = _to_float_br(alocados[c])
        alocados = alocados[alocados["Valor Realocado"] > 0].rename(columns={"estrategia": "Ativo"})

        elems.append(Paragraph("Ativos Alocados", ParagraphStyle(name="T2", parent=styles["Heading2"], alignment=TA_CENTER, fontName=BOLD_FONT)))
        if not alocados.empty:
            alocados["Valor Atual (R$)"]     = alocados["valor_atual"].apply(_format_number_br)
            alocados["Novo Valor (R$)"]      = alocados["Novo Valor"].apply(_format_number_br)
            alocados["Valor Realocado (R$)"] = alocados["Valor Realocado"].apply(_format_number_br)

            header_a = [Paragraph("Classificação", hdr9),
                        Paragraph("Ativo", hdr9),
                        Paragraph("Valor Atual", hdr9),
                        Paragraph("Realocado", hdr9),
                        Paragraph("Novo Valor", hdr9)]

            cols_a = ["Classificação", "Ativo", "Valor Atual (R$)", "Valor Realocado (R$)", "Novo Valor (R$)"]
            w_a = _cw_with_cushion([18, 46, 12, 12, 12])

            data_a = [header_a]
            for _, r in alocados[cols_a].iterrows():
                data_a.append([
                    r["Classificação"],
                    Paragraph(str(r["Ativo"]), cell_wrap),
                    r["Valor Atual (R$)"],
                    r["Valor Realocado (R$)"],
                    r["Novo Valor (R$)"],
                ])

            alocados_tbl = Table(data_a, colWidths=w_a, hAlign='LEFT')
            alocados_tbl.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),HEADER_BG),
                ('TEXTCOLOR',(0,0),(-1,0),colors.black),
                ('FONTNAME',(0,0),(-1,0),BOLD_FONT),
                ('FONTNAME',(0,1),(-1,-1),BASE_FONT),
                ('TEXTCOLOR',(0,1),(-1,-1),PRIMARY_COLOR),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('FONTSIZE',(0,0),(-1,0),10),
                ('FONTSIZE',(0,1),(-1,-1),8),
                ('LEFTPADDING',(0,0),(-1,-1),3),
                ('RIGHTPADDING',(0,0),(-1,-1),3),
                ('TOPPADDING',(0,0),(-1,0),4),
                ('BOTTOMPADDING',(0,0),(-1,0),4),
                ('LINEABOVE',(0,0),(-1,0),0.4,HLINE_COLOR),
                ('LINEBELOW',(0,0),(-1,0),0.4,HLINE_COLOR),
                ('LINEBELOW',(0,1),(-1,-1),0.3,HLINE_COLOR),
            ]))
            elems.append(alocados_tbl)
        else:
            elems.append(Paragraph("_Nenhum ativo alocado._", styles["Italic"]))
        elems.append(Spacer(1, 18))

        resgatados = ativos_df.copy()
        for c in ["valor_atual", "Novo Valor", "Valor Realocado"]:
            if c in resgatados.columns:
                resgatados[c] = _to_float_br(resgatados[c])
        resgatados = resgatados[resgatados["Valor Realocado"] < 0].rename(columns={"estrategia": "Ativo"})

        elems.append(Paragraph("Ativos Resgatados", ParagraphStyle(name="T3", parent=styles["Heading2"], alignment=TA_CENTER, fontName=BOLD_FONT)))
        if not resgatados.empty:
            resgatados["Valor Atual (R$)"]     = resgatados["valor_atual"].apply(_format_number_br)
            resgatados["Novo Valor (R$)"]      = resgatados["Novo Valor"].apply(_format_number_br)
            resgatados["Valor Realocado (R$)"] = resgatados["Valor Realocado"].apply(_format_number_br)

            header_r = [Paragraph("Classificação", hdr9),
                        Paragraph("Ativo", hdr9),
                        Paragraph("Valor Atual", hdr9),
                        Paragraph("Realocado", hdr9),
                        Paragraph("Novo Valor", hdr9)]

            cols_r = ["Classificação", "Ativo", "Valor Atual (R$)", "Valor Realocado (R$)", "Novo Valor (R$)"]
            w_r = _cw_with_cushion([18, 46, 12, 12, 12])

            data_r = [header_r]
            for _, r in resgatados[cols_r].iterrows():
                data_r.append([
                    r["Classificação"],
                    Paragraph(str(r["Ativo"]), cell_wrap),
                    r["Valor Atual (R$)"],
                    r["Valor Realocado (R$)"],
                    r["Novo Valor (R$)"],
                ])

            resgatados_tbl = Table(data_r, colWidths=w_r, hAlign='LEFT')
            resgatados_tbl.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),HEADER_BG),
                ('TEXTCOLOR',(0,0),(-1,0),colors.black),
                ('FONTNAME',(0,0),(-1,0),BOLD_FONT),
                ('FONTNAME',(0,1),(-1,-1),BASE_FONT),
                ('TEXTCOLOR',(0,1),(-1,-1),PRIMARY_COLOR),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('FONTSIZE',(0,0),(-1,0),10),
                ('FONTSIZE',(0,1),(-1,-1),8),
                ('LEFTPADDING',(0,0),(-1,-1),3),
                ('RIGHTPADDING',(0,0),(-1,-1),3),
                ('TOPPADDING',(0,0),(-1,0),4),
                ('BOTTOMPADDING',(0,0),(-1,0),4),
                ('LINEABOVE',(0,0),(-1,0),0.4,HLINE_COLOR),
                ('LINEBELOW',(0,0),(-1,0),0.4,HLINE_COLOR),
                ('LINEBELOW',(0,1),(-1,-1),0.3,HLINE_COLOR),
            ]))
            elems.append(resgatados_tbl)
        else:
            elems.append(Paragraph("_Nenhum ativo resgatado._", styles["Italic"]))
        elems.append(Spacer(1, 6))

    # --- Página seguinte — Sugestão de Carteira (detalhada)
    elems.append(PageBreak())
    elems.append(Paragraph("Sugestão de Carteira",
                           ParagraphStyle(name="H2", parent=styles["Heading2"], fontName=BOLD_FONT)))
    elems.append(Spacer(1, 12))

    data = [["Ativo","Capital Alocado","% PL"]]
    classification_rows = []; row_idx = 1
    total_sug = pd.to_numeric(ativos_df.get("Novo Valor", 0.0), errors="coerce").fillna(0.0).sum()

    class_sums = (ativos_df.assign(_novo=pd.to_numeric(ativos_df.get("Novo Valor", 0.0), errors="coerce").fillna(0.0))
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
        ("BACKGROUND",(0,0),(-1,0),colors.gray),
        ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),
        ("FONTNAME",(0,0),(-1,0),BOLD_FONT),
        ("FONTSIZE",(0,0),(-1,0),10),
        ("ALIGN",(0,0),(-1,0),"CENTER"),
        ("VALIGN",(0,0),(-1,0),"MIDDLE"),
        ("TEXTCOLOR",(0,1),(-1,-1),PRIMARY_COLOR),
        ("FONTNAME",(0,1),(-1,-1),BASE_FONT),
        ("FONTSIZE",(0,1),(-1,-1),8),
        ("ALIGN",(0,1),(0,-1),"LEFT"),
        ("ALIGN",(1,1),(-1,-1),"CENTER"),
        ("VALIGN",(0,1),(-1,-1),"MIDDLE"),
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

    # Concatenação final (capa/contra/última)
    base_dir  = os.path.dirname(__file__)
    writer = PdfWriter()
    for p in PdfReader(os.path.join(base_dir, "capa.pdf")).pages: writer.add_page(p)
    for p in PdfReader(os.path.join(base_dir, "contra_capa.pdf")).pages: writer.add_page(p)
    for p in PdfReader(buffer_relatorio).pages: writer.add_page(p)
    for p in PdfReader(os.path.join(base_dir, "ultima_pagina.pdf")).pages: writer.add_page(p)

    out = io.BytesIO(); writer.write(out); out.seek(0)
    return out.read()
