import io
import os
import base64
from typing import Any, Dict, List
import pandas as pd
import matplotlib.pyplot as plt

from jinja2 import Environment, BaseLoader, select_autoescape

# Tenta usar WeasyPrint; se não, orientação para fallback com Playwright
USE_WEASYPRINT = True
try:
    if USE_WEASYPRINT:
        from weasyprint import HTML
except Exception as _e:
    USE_WEASYPRINT = False

# Paleta existente no seu projeto
try:
    from utils.cores import PALETTE  # mantém sua paleta atual
except Exception:
    # fallback simples se módulo não estiver acessível em ambiente de teste
    PALETTE = ["#0F2B56", "#2A6F97", "#468FAF", "#89C2D9", "#A9D6E5", "#5E6472", "#9CA3AF"]

# ==============================
# TEMPLATE HTML (Lovable) embutido
# ==============================

TEMPLATE_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Realocação de Carteira - {{cliente_nome}}</title>
<style>
  @page{
    size:A4;
    margin:20mm 15mm 20mm 15mm;
    @top-center{content:element(header)}
    @bottom-center{content:element(footer)}
  }

  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:"Segoe UI","Inter",Arial,sans-serif;font-size:11px;line-height:1.4;color:#000;background:#fff}

  /* ===== HEADER (running) ===== */
  .header{position:running(header);background:#0F2B56;height:40px;display:flex;align-items:center;justify-content:space-between;padding:0 12px 0 12px}
  .header .logo{width:125px;height:auto;max-height:30px}
  .header .title{color:#fff;font-size:20px;font-weight:600}

  .header-info{display:flex;justify-content:space-between;align-items:flex-start;margin:10px 0 10px 0;padding-bottom:10px;border-bottom:0.5px solid #000}
  .client-info{font-size:14px;font-weight:700}
  .metadata{text-align:right;font-size:11px}
  .metadata .label{font-weight:600;color:#666}
  .metadata .value{margin-left:8px}

  /* ===== FOOTER (running) ===== */
  .footer{position:running(footer);background:#f5f5f5;padding:10px 20px;text-align:center}
  .disclaimer{font-size:9px;color:#000;max-width:90%;margin:0 auto 6px;line-height:1.3}
  .institutional{font-size:8px;color:#666}

  /* ===== PAGE CONTENT BOX ===== */
  .page-content{margin-top:60px; margin-bottom:70px}
  .page-title{text-align:center;font-size:18px;font-weight:600;margin:18px 0 20px 0;color:#0F2B56}

  /* ===== GRIDS ===== */
  .three-col-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:16px}
  .two-col-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}

  /* ===== CARDS ===== */
  .card{border:1px solid #e5e7eb;border-radius:8px;padding:10px;background:#fff}
  .card-title{font-size:12px;font-weight:600;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid #e5e7eb;text-align:center}

  .chart-container{text-align:center;margin-top:6px}
  .chart-container img{max-width:100%;height:auto}

  /* ===== TABLES ===== */
  table{width:100%;border-collapse:collapse;font-size:9px;page-break-inside:auto;table-layout:fixed}
  thead{display:table-header-group}
  thead th{
    background:#9CA3AF;color:#fff;padding:7px 6px;text-align:center;font-weight:600;font-size:9px;border-bottom:1px solid #666;
    white-space:nowrap; /* evita quebra no cabeçalho */
  }
  tbody td{padding:6px 8px;border-bottom:1px solid #e5e7eb;font-size:8.5px;overflow-wrap:anywhere}
  .txt-left{text-align:left}
  .txt-center{text-align:center}
  .txt-right{text-align:right}

  /* Subcabeçalho de classificação (grupo) */
  tbody.group{display:table-row-group;page-break-inside:avoid}
  .subheader{background:#f3f4f6}
  .subheader td{font-weight:700;font-size:9px;border-top:1px solid #d1d5db;padding:8px}

  /* Tabela comparativa central com barras */
  .comparative-table td{vertical-align:middle}
  .bar-wrap{display:flex;align-items:center;gap:6px}
  .bar{height:10px;border-radius:3px;background:#0F2B56;width:0;}
  .bar[data-w]{width:calc(var(--w,0) * 1%)}
  .bar-val{min-width:36px;text-align:center}

  /* Tabelas detalhadas lado a lado */
  .detail-table thead th{background:#888}

  /* Liquidez sugerida box */
  .liquidez-box{font-size:10px;color:#374151;margin-top:6px;text-align:right}
  .liquidez-box b{font-weight:700}

  /* Quebras */
  .page-break{page-break-before:always}
</style>
</head>
<body>

  <!-- ===== Running Header ===== -->
  <div class="header">
    <img src="{{logo_url}}" alt="Logo" class="logo">
    <div class="title">Realocação de Carteira</div>
  </div>

  <div class="page-content">
    <!-- Linha abaixo do header -->
    <div class="header-info">
      <div class="client-info">{{cliente_nome | upper}}</div>
      <div class="metadata">
        <div><span class="label">Assessor de Investimentos:</span><span class="value">{{nome_assessor}}</span></div>
        <div><span class="label">Patrimônio Total:</span><span class="value">{{patrimonio_total_brl}}</span></div>
      </div>
    </div>

    <!-- ===== PÁGINA 1 ===== -->
    <h1 class="page-title">Proposta de Alocação de Carteira</h1>

    <!-- Grids: gráfico - comparativo - gráfico -->
    <div class="three-col-grid">
      <div class="card">
        <div class="card-title">CARTEIRA ATUAL</div>
        <div class="chart-container">
          <img src="{{grafico_atual_src}}" alt="Gráfico Carteira Atual">
        </div>
      </div>

      <div class="card">
        <table class="comparative-table">
          <thead>
            <tr>
              <th>Atual (%)</th>
              <th>Classificação</th>
              <th>Modelo (%)</th>
            </tr>
          </thead>
          <tbody>
            {% for lin in comparativo %}
            <tr>
              <td class="txt-center">
                <div class="bar-wrap">
                  <div class="bar" data-w style="--w: {{ lin.atual_perc_num | default(0) }};"></div>
                  <span class="bar-val">{{ lin.atual_perc }}</span>
                </div>
              </td>
              <td class="txt-left">{{ lin.classificacao }}</td>
              <td class="txt-center">
                <div class="bar-wrap" style="justify-content:flex-end">
                  <span class="bar-val">{{ lin.modelo_perc }}</span>
                  <div class="bar" data-w style="--w: {{ lin.modelo_perc_num | default(0) }};"></div>
                </div>
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-title">CARTEIRA PROPOSTA</div>
        <div class="chart-container">
          <img src="{{grafico_proposta_src}}" alt="Gráfico Carteira Proposta">
        </div>
      </div>
    </div>

    <!-- Tabelas lado a lado -->
    <div class="two-col-grid">
      <div class="card">
        <div class="card-title">Carteira Atual</div>
        <table class="detail-table">
          <thead>
            <tr>
              <th class="txt-left">Classificação</th>
              <th class="txt-right">Valor</th>
              <th class="txt-right">% PL</th>
            </tr>
          </thead>
          <tbody>
            {% for lin in comp_atual %}
            <tr>
              <td class="txt-left">{{ lin.classificacao }}</td>
              <td class="txt-right">{{ lin.valor_brl }}</td>
              <td class="txt-right">{{ lin.perc_pl }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-title">Carteira Proposta</div>
        <table class="detail-table">
          <thead>
            <tr>
              <th class="txt-left">Classificação</th>
              <th class="txt-right">Valor</th>
              <th class="txt-right">% PL</th>
            </tr>
          </thead>
          <tbody>
            {% for lin in comp_proposta %}
            <tr>
              <td class="txt-left">{{ lin.classificacao }}</td>
              <td class="txt-right">{{ lin.valor_brl }}</td>
              <td class="txt-right">{{ lin.perc_pl }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
        <div class="liquidez-box">Liquidez do portfólio sugerido (R$): <b>{{ liquidez_sugerida_brl }}</b></div>
      </div>
    </div>

    <!-- ===== PÁGINA 2 ===== -->
    <div class="page-break"></div>

    {% if diferencas %}
    <div class="card" style="margin-bottom:14px">
      <div class="card-title" style="text-align:left">Diferença entre Portfólio Atual e Sugerido</div>
      <table class="detail-table">
        <thead>
          <tr>
            <th class="txt-left">Classificação</th>
            <th class="txt-center">Atual (%)</th>
            <th class="txt-center">Sugerida (%)</th>
            <th class="txt-center">Ajuste</th>
            <th class="txt-center">Ação</th>
          </tr>
        </thead>
        <tbody>
          {% for d in diferencas %}
          <tr>
            <td class="txt-left">{{ d.classificacao }}</td>
            <td class="txt-center">{{ d.atual_perc }}</td>
            <td class="txt-center">{{ d.sugerida_perc }}</td>
            <td class="txt-center">{{ d.ajuste_perc }}</td>
            <td class="txt-center">{{ d.acao }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% endif %}

    <!-- Sugestão detalhada por classificação: um <tbody> por grupo -->
    <div class="card">
      <div class="card-title" style="text-align:left">Sugestão de Carteira</div>
      <table class="detail-table">
        <thead>
          <tr>
            <th class="txt-left">Ativo</th>
            <th class="txt-right">Capital Alocado</th>
            <th class="txt-right">% PL</th>
          </tr>
        </thead>

        {% for grupo in sugestao_detalhada %}
        <tbody class="group">
          <tr class="subheader">
            <td class="txt-left"><b>{{ grupo.classificacao | upper }}</b></td>
            <td class="txt-right"><b>{{ grupo.total_brl }}</b></td>
            <td class="txt-right"><b>{{ grupo.total_perc }}</b></td>
          </tr>
          {% for ativo in grupo.ativos %}
          <tr>
            <td class="txt-left">{{ ativo.nome }}</td>
            <td class="txt-right">{{ ativo.valor_brl }}</td>
            <td class="txt-right">{{ ativo.perc_pl }}</td>
          </tr>
          {% endfor %}
        </tbody>
        {% endfor %}
      </table>
    </div>
  </div>

  <!-- ===== Running Footer ===== -->
  <div class="footer">
    <div class="disclaimer">{{disclaimer_texto}}</div>
    {% if rodape_institucional %}
      <div class="institutional">{{rodape_institucional}}</div>
    {% endif %}
  </div>
</body>
</html>
"""

# ==============================
# HELPERS
# ==============================

def _format_brl(v: float) -> str:
    try:
        s = f"{float(v):,.2f}"
    except Exception:
        return str(v)
    inteiro, dec = s.split(".")
    inteiro = inteiro.replace(",", ".")
    return f"R$ {inteiro},{dec}"

def _format_pct(v: float) -> str:
    try:
        return f"{float(v):.1f}%".replace(".", ",")
    except Exception:
        return str(v)

def _pct_to_num(p: Any) -> float:
    """
    Converte '74,3%' -> 74.3 (para largura das barras).
    Aceita float já numérico.
    """
    if p is None:
        return 0.0
    if isinstance(p, (int, float)):
        return float(p)
    s = str(p).strip().replace("%", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def _img_buf_to_data_url(buf: io.BytesIO) -> str:
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

def _make_donut(labels: List[str], sizes: List[float], color_map: Dict[str, str]) -> io.BytesIO:
    colors_list = [color_map.get(lbl, PALETTE[i % len(PALETTE)]) for i, lbl in enumerate(labels)]
    b = io.BytesIO()
    fig, ax = plt.subplots(figsize=(3.6, 3.6))  # um pouco menor p/ caber bem
    ax.pie(
        sizes,
        labels=None,
        startangle=90,
        counterclock=False,
        colors=colors_list,
        wedgeprops={"width": 0.3, "edgecolor": "white"},
    )
    ax.axis("equal")
    plt.tight_layout()
    fig.savefig(b, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    b.seek(0)
    return b

# ==============================
# PIPE: DataFrames -> Contexto Jinja2
# ==============================

def _build_context(
    dist_df: pd.DataFrame,
    modelo_df: pd.DataFrame,
    resumo_df: pd.DataFrame,
    sugestao: Dict[str, Any],
    ativos_df: pd.DataFrame,
    logo_url: str,
    disclaimer_texto: str,
    rodape_institucional: str = ""
) -> Dict[str, Any]:
    # --- Metadados do header ---
    cliente = sugestao.get("cliente_nome") or sugestao.get("CLIENTE_NOME") or ""
    assessor = sugestao.get("nome_assessor") or sugestao.get("NOME_ASSESSOR") or ""
    liquidez_sugerida = sugestao.get("liquidez_sugerida") or sugestao.get("LIQUIDEZ_SUGERIDA") or 0.0

    patrimonio_total = 0.0
    if "valor" in dist_df.columns:
        try:
            patrimonio_total = float(dist_df["valor"].astype(str).str.replace(".","", regex=False).str.replace(",",".", regex=False).astype(float).sum())
        except Exception:
            patrimonio_total = dist_df["valor"].sum()

    # --- Mapa de cores por classificação a partir da carteira atual ---
    # (replicamos a lógica do seu código para manter cores consistentes entre os dois donuts)
    dist_sorted = dist_df.copy()
    if "Percentual" in dist_sorted.columns:
        dist_sorted = dist_sorted.sort_values(by="Percentual", ascending=False)
    labels_atual = dist_sorted["Classificação"].astype(str).tolist()
    sizes_atual = dist_sorted.get("Percentual", pd.Series([0]*len(labels_atual))).astype(float).tolist()

    color_map = {}
    for i, lbl in enumerate(labels_atual):
        color_map[lbl] = PALETTE[i % len(PALETTE)]

    # garantir cores também para classes da carteira modelo
    for lbl in modelo_df["Classificação"].astype(str).tolist():
        color_map.setdefault(lbl, PALETTE[len(color_map) % len(PALETTE)])

    # --- Donuts como data URLs ---
    buf_atual = _make_donut(labels_atual, sizes_atual, color_map)
    grafico_atual_src = _img_buf_to_data_url(buf_atual)

    modelo_sorted = modelo_df.copy().sort_values(by="Percentual Ideal", ascending=False)
    labels_modelo = modelo_sorted["Classificação"].astype(str).tolist()
    sizes_modelo = modelo_sorted["Percentual Ideal"].astype(float).tolist()
    buf_modelo = _make_donut(labels_modelo, sizes_modelo, color_map)
    grafico_proposta_src = _img_buf_to_data_url(buf_modelo)

    # --- Tabela comparativa central ---
    # união de classificações de atual + modelo
    todas_cls = list(dict.fromkeys(list(dist_df["Classificação"].astype(str)) + list(modelo_df["Classificação"].astype(str))))
    # map atual %
    map_atual = dist_df.groupby("Classificação")["Percentual"].sum().to_dict()
    # map modelo %
    map_modelo = modelo_df.groupby("Classificação")["Percentual Ideal"].sum().to_dict()

    comparativo = []
    for cls in todas_cls:
        a = float(map_atual.get(cls, 0.0))
        m = float(map_modelo.get(cls, 0.0))
        comparativo.append({
            "classificacao": cls,
            "atual_perc": _format_pct(a),            # ex.: "74,3%"
            "atual_perc_num": round(a, 2),           # p/ barra
            "modelo_perc": _format_pct(m),
            "modelo_perc_num": round(m, 2),
        })

    # --- Tabelas laterais: atual e proposta ---
    # Atual
    dist_fmt = dist_df.copy()
    dist_fmt = dist_fmt.sort_values(by="valor", ascending=False)
    dist_fmt["valor_brl"] = dist_fmt["valor"].apply(_format_brl)
    dist_fmt["perc_pl"] = dist_fmt["Percentual"].apply(_format_pct)
    comp_atual = [
        {"classificacao": r["Classificação"], "valor_brl": r["valor_brl"], "perc_pl": r["perc_pl"]}
        for _, r in dist_fmt[["Classificação", "valor_brl", "perc_pl"]].iterrows()
    ]
    # Proposta
    modelo_fmt = modelo_df.copy()
    modelo_fmt = modelo_fmt.rename(columns={"Percentual Ideal": "Percentual", "Valor Ideal (R$)": "valor"})
    if "valor" in modelo_fmt.columns:
        modelo_fmt = modelo_fmt.sort_values(by="valor", ascending=False)
        modelo_fmt["valor_brl"] = modelo_fmt["valor"].apply(_format_brl)
    else:
        modelo_fmt["valor_brl"] = "—"
    modelo_fmt["perc_pl"] = modelo_fmt["Percentual"].apply(_format_pct)
    comp_proposta = [
        {"classificacao": r["Classificação"], "valor_brl": r["valor_brl"], "perc_pl": r["perc_pl"]}
        for _, r in modelo_fmt[["Classificação", "valor_brl", "perc_pl"]].iterrows()
    ]

    # --- Diferenças (opcional): resumo_df já vem calculado no seu fluxo ---
    diferencas = []
    if isinstance(resumo_df, pd.DataFrame) and not resumo_df.empty:
        # esperamos colunas: Classificação, Atual (%), Sugerida (%), Ajuste, Ação  (se forem outras, adapte abaixo)
        cand_cols = resumo_df.columns.str.lower().tolist()
        def pick(colopts: List[str]) -> str:
            for c in resumo_df.columns:
                if c.lower() in colopts:
                    return c
            return colopts[0]

        col_cls = pick(["classificação","classificacao"])
        col_atual = pick(["% do pl atual (%)","atual (%)","atual"])
        col_sug = pick(["% do pl sugerida (%)","sugerida (%)","sugerida"])
        col_adj = pick(["ajuste (%)","ajuste"])
        col_acao = pick(["ação","acao"])

        for _, r in resumo_df.iterrows():
            diferencas.append({
                "classificacao": str(r.get(col_cls, "")),
                "atual_perc": str(r.get(col_atual, "")),
                "sugerida_perc": str(r.get(col_sug, "")),
                "ajuste_perc": str(r.get(col_adj, "")),
                "acao": str(r.get(col_acao, "")),
            })

    # --- Sugestão detalhada (ativos_df) agrupada por classificação ---
    sugestao_detalhada: List[Dict[str, Any]] = []
    if isinstance(ativos_df, pd.DataFrame) and not ativos_df.empty:
        # Espera colunas: "Classificação", "Novo Valor", "estrategia" (nome do ativo) e opcional "% PL"
        df = ativos_df.copy()
        # garante float
        try:
            df["Novo Valor"] = df["Novo Valor"].astype(str).str.replace(".","", regex=False).str.replace(",",".", regex=False).astype(float)
        except Exception:
            pass

        total_sug = float(df["Novo Valor"].fillna(0).sum())

        for cls, g in df.groupby("Classificação"):
            soma = float(g["Novo Valor"].fillna(0).sum())
            grupo = {
                "classificacao": str(cls),
                "total_brl": _format_brl(soma),
                "total_perc": _format_pct((soma/total_sug*100) if total_sug else 0.0),
                "ativos": []
            }
            # ordena ativos desc por valor
            g2 = g.sort_values("Novo Valor", ascending=False)
            for _, r in g2.iterrows():
                nome = str(r.get("estrategia", r.get("Ativo", ""))).replace("\uFFFD","").replace("\xa0"," ").strip()
                valor = float(r.get("Novo Valor", 0.0))
                # se já existir %PL da linha, usa; senão calcula
                if "% PL" in g2.columns:
                    perc_pl_str = str(r["% PL"])
                else:
                    perc_pl_str = _format_pct((valor/total_sug*100) if total_sug else 0.0)
                grupo["ativos"].append({
                    "nome": nome,
                    "valor_brl": _format_brl(valor),
                    "perc_pl": perc_pl_str
                })
            sugestao_detalhada.append(grupo)

    contexto = {
        # Header
        "logo_url": logo_url,
        "cliente_nome": cliente,
        "nome_assessor": assessor,
        "patrimonio_total_brl": _format_brl(patrimonio_total),
        # Gráficos
        "grafico_atual_src": grafico_atual_src,
        "grafico_proposta_src": grafico_proposta_src,
        # Pág.1 comparativo + tabelas
        "comparativo": comparativo,
        "comp_atual": comp_atual,
        "comp_proposta": comp_proposta,
        "liquidez_sugerida_brl": _format_brl(liquidez_sugerida),
        # Pág.2 diferenças + sugestão detalhada
        "diferencas": diferencas,
        "sugestao_detalhada": sugestao_detalhada,
        # Footer
        "disclaimer_texto": disclaimer_texto,
        "rodape_institucional": rodape_institucional,
    }
    return contexto

# ==============================
# RENDER HTML -> PDF
# ==============================

def _render_html(template_str: str, context: Dict[str, Any]) -> str:
    env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.from_string(template_str)
    return tpl.render(**context)

def _html_to_pdf_bytes(html: str, base_url: str = ".") -> bytes:
    if USE_WEASYPRINT:
        return HTML(string=html, base_url=base_url).write_pdf()
    # Fallback com Playwright (se quiser habilitar):
    # from playwright.sync_api import sync_playwright
    # with sync_playwright() as p:
    #     browser = p.chromium.launch()
    #     page = browser.new_page()
    #     page.set_content(html, wait_until="load")
    #     pdf_bytes = page.pdf(format="A4", margin={"top":"20mm","right":"15mm","bottom":"20mm","left":"15mm"})
    #     browser.close()
    #     return pdf_bytes
    raise RuntimeError("WeasyPrint não disponível. Ative o fallback com Playwright (ver comentário no código).")

# ==============================
# FUNÇÃO PÚBLICA
# ==============================

def generate_pdf(
    dist_df: pd.DataFrame,
    modelo_df: pd.DataFrame,
    resumo_df: pd.DataFrame,
    sugestao: Dict[str, Any],
    ativos_df: pd.DataFrame,
    output_path: str = "relatorio_carteira.pdf",
    logo_url: str = "",  # pode ser 'file:///C:/.../logo.png' ou data:image/png;base64,...
    disclaimer_texto: str = "",
    rodape_institucional: str = ""
) -> str:
    """
    Gera o PDF final no caminho `output_path` a partir dos DataFrames e metadados.
    Retorna o caminho gerado.

    Mantém a mesma assinatura conceitual do seu gerador anterior (dist_df, modelo_df, resumo_df, sugestao, ativos_df).
    """
    # 1) Monta contexto Jinja2 a partir dos DataFrames
    contexto = _build_context(
        dist_df=dist_df,
        modelo_df=modelo_df,
        resumo_df=resumo_df,
        sugestao=sugestao,
        ativos_df=ativos_df,
        logo_url=logo_url,
        disclaimer_texto=disclaimer_texto,
        rodape_institucional=rodape_institucional,
    )

    # 2) Renderiza HTML
    html = _render_html(TEMPLATE_HTML, contexto)

    # 3) Converte para PDF
    pdf_bytes = _html_to_pdf_bytes(html)

    # 4) Salva em disco
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    return output_path

