"""Fase 2, EXTRAINDO CONTEÚDO: abre o PDF e lê o texto de cada página, na ordem natural de leitura.

    models.py    Pagina, Leitura e os erros de leitura (PDF protegido, corrompido, não encontrado)
    logic.py     ler_pdf, extrair_conteudo (a fase inteira), normalizar_espacos, listar_pdfs
    schemas.py   api.py   GET /api/processos/{id}/extract: o que foi lido deste PDF

É a única fase que abre o arquivo. Só precisa do PyMuPDF.
"""
