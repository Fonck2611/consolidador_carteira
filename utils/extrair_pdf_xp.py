from PyPDF2 import PdfReader
import re
import pandas as pd

def extrair_texto_ativos(file):
    reader = PdfReader(file)
    texto_total = ""
    entrou_na_secao = False

    for page in reader.pages:
        texto_pagina = page.extract_text()
        if not texto_pagina:
            continue

        if not entrou_na_secao and "POSIÇÃO DETALHADA DOS ATIVOS" in texto_pagina:
            entrou_na_secao = True

        if entrou_na_secao:
            if "MOVIMENTAÇÕES" in texto_pagina:
                break
            texto_total += "\n[NEWPAGE]\n" + texto_pagina

    return texto_total

def limpar_num(n):
    return float(n.replace(".", "").replace(",", "."))

def parse_ativos(texto):
    classificacoes_validas = [
        "Pós Fixado", "Inﬂação", "Pré Fixado", "Multimercado",
        "Renda Variável Brasil", "Alternativo", "Renda Variável Global",
        "Renda Fixa Global", "Fundos Listados"
    ]

    dados = []
    classificacao_atual = None
    numero_regex = r"-?[\d.]+(?:,\d+)?"
    paginas = texto.split("[NEWPAGE]")

    for pagina in paginas:
        linha_acumulada = ""
        permitido_capturar = False
        contador_cdi = 0

        for linha in pagina.splitlines():
            linha = linha.strip()
            if not linha:
                continue

            contador_cdi += linha.count("%CDI")
            if not permitido_capturar and contador_cdi >= 3:
                permitido_capturar = True
                continue

            atualizou_classificacao = False
            for c in classificacoes_validas:
                if linha.startswith(c):
                    classificacao_atual = c
                    atualizou_classificacao = True
                    if "R$" in linha:
                        break
                    break
            if atualizou_classificacao:
                continue

            if not permitido_capturar:
                continue

            linha_acumulada += " " + linha

            if "R$" not in linha_acumulada:
                continue

            partes = re.split(r"R\$\s*", linha_acumulada, maxsplit=1)
            if len(partes) < 2:
                continue

            estrategia = partes[0].strip()

            if classificacao_atual and estrategia.strip() == classificacao_atual.strip():
                linha_acumulada = ""
                continue

            numeros = re.findall(numero_regex, partes[1])
            if len(numeros) >= 2:
                try:
                    registro = {
                        "classificacao": classificacao_atual,
                        "estrategia": estrategia,
                        "saldo_bruto": limpar_num(numeros[0]),
                        "quantidade": float(numeros[1].replace(",", ".")),
                    }

                    campos = [
                        "rentabilidade_mes_atual",
                        "porcentagem_cdi_mes_atual",
                        "rentabilidade_ano",
                        "porcentagem_cdi_ano",
                        "rentabilidade_24m",
                        "porcentagem_cdi_24m"
                    ]

                    for i, campo in enumerate(campos, start=3):
                        if i < len(numeros):
                            registro[campo] = limpar_num(numeros[i])
                        else:
                            registro[campo] = None

                    dados.append(registro)
                except:
                    pass

            linha_acumulada = ""

    df = pd.DataFrame(dados)
    df = df.replace("ﬂ", "fl", regex=True)
    return df
