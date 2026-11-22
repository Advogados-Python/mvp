"""Fase 4, BUSCANDO OS TERMOS: procura, página a página, os termos do dicionário e guarda cada achado como uma Evidencia
(página + trecho), já dizendo se a frase é hipotética e se veio do juízo. Não decide nada: só reúne as provas.

    models.py    Evidencia                   terms.py   o DICIONÁRIO de termos por fase do crédito + as regras de contexto
    logic.py     buscar_termos               schemas.py   api.py   GET /api/processos/{id}/search: as evidências reunidas
"""
