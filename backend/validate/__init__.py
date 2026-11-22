"""Fase 5, VALIDANDO AS EVIDÊNCIAS: pesa as evidências (só as que "contam" decidem), conclui a fase do crédito, responde "a dívida já
foi paga?" e levanta os avisos que o advogado precisa ler.

    models.py    Conclusao, Fase (um degrau da escada) e RespostaDividaPaga       ladder.py   a ESCADA do crédito
    logic.py     validar_evidencias (a fase inteira), classificar_fase...          schemas.py  api.py
                 GET /api/fases (a escada, pública) e GET /api/processos/{id}/validate (o que foi concluído)
"""
