"""Backend do Leitor de Processos: as seis fases de leitura do documento (receive, extract, identify, search, validate,
finalize) e os usuários (userauths).

    uvicorn backend.main:app --reload       # a API
    python -m backend.userauths.cli ...     # gerência de usuários

Veja o mapa de pastas no cabeçalho de backend/main.py.
"""
