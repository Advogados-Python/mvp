"""Fase 1, DOCUMENTO RECEBIDO: recebe o PDF enviado, confere, guarda em disco e registra o processo na fila.

    models.py    Processo (a tabela `processos`), StatusAnalise, PdfRecebido, ErroEnvio
    store.py     ArmazemPdf: os PDFs em disco        logic.py   registrar o envio, consultar com dono, apagar, refazer
    schemas.py   api.py   POST/DELETE /api/processos..., /reanalisar, /pdf-link, /pdf  e  GET /api/processos/{id}/receive
"""
