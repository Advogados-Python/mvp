"""Os termos que identificam a REQUISIÇÃO DE PAGAMENTO (RPV/OPV/precatório) nos autos: {nome do termo: expressão regular}."""

TERMOS = {
    "oficio_requisitorio": r"of[íi]cio\s+requisit[óo]rio",
    "oficio_requisicao_pagamento": r"of[íi]cio\s+requisi[çc][ãa]o\s+de\s+pagamento",
    "expedicao_rpv_precatorio": r"(?:expedi[çc][ãa]o|juntada)\s+de\s+(?:RPV|OPV|precat[óo]rio)",
    "expedir_precatorio": r"expedi(?:r|do|da|u)\b[^.]{0,30}precat[óo]rio",
    # Número de requisição no padrão TRF1/PJe, ex.: 2026.0000.000.000001
    "requisicao_pagamento_numerada": r"requisi[çc][ãa]o\s+de\s+pagamento\s+\d{4}\.\d{4}\.\d{3}\.\d{6}",
}
