"""Fase 3, IDENTIFICANDO O PROCESSO: descobre de que peça é cada página (PJe) e extrai os dados do processo
(número, tribunal, partes, advogados, OAB, juiz, valores). Só regex, nada de IA.

    models.py    Parte, Identificacao        rules.py   as regex e as tabelas (tribunais) desta fase
    logic.py     identificar_processo (a fase inteira), identificar_documentos, extrair_metadados...
    schemas.py   api.py   GET /api/processos/{id}/identify: o que foi identificado neste processo
"""
