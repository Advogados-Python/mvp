"""Processos: receber o PDF, guardar, analisar em segundo plano (fila) e servir o resultado.

    constantes.py   limites e mensagens          armazem.py   PDFs em disco
    erros.py        ErroEnvio                    fila.py      fila de análises (threads)
    modelos.py      tabela `processos`           analise.py   o job que roda o leitor e grava o resultado
    schemas.py      formatos da API              funcoes.py   regras: registrar, consultar, apagar, serializar
    dependencias.py armazém e fila no FastAPI    rotas.py     /api/processos
"""
