def get_modelo_carteira(tipo):
    modelos = {
        "Conservadora": {
            "Pós Fixado": 70,
            "Pré Fixado": 5,
            "Inflação": 15,
            "Renda Fixa Global": 10
        },
        "Moderada": {
            "Pós Fixado": 35,
            "Pré Fixado": 7.5,
            "Inflação": 20,
            "Multimercado": 5,
            "Renda Variável Brasil": 10,
            "Fundos Listados": 5,
            "Alternativos": 2.5,
            "Renda Fixa Global": 10,
            "Renda Variável Global": 5
        },
        "Sofisticada": {
            "Pós Fixado": 15,
            "Pré Fixado": 10,
            "Inflação": 25,
            "Multimercado": 5,
            "Renda Variável Brasil": 15,
            "Fundos Listados": 7.5,
            "Alternativos": 7.5,
            "Renda Fixa Global": 5,
            "Renda Variável Global": 10
        }
    }
    return modelos.get(tipo, {})
