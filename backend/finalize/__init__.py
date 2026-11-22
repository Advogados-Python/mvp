"""Fase 6, FINALIZANDO O RESULTADO: reúne o que as fases entregaram, grava no banco e fecha o processo (CONCLUIDO ou FALHOU).

    models.py    ResultadoProcesso (tudo o que o sistema descobriu sobre um PDF)
    logic.py     gravar_resultado (a fase), montar_resultado, mensagens de erro, serialização para a API, exportar JSON/CSV
    schemas.py   api.py   GET /api/processos, GET /api/processos/{id} (o processo completo) e GET /api/processos/{id}/finalize
"""
