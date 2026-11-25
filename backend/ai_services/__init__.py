"""Camada de IA: a última camada depois das seis fases de leitura. Confere, com um modelo de linguagem, a fase do crédito e a
resposta "a dívida já foi paga?" lendo o texto inteiro dos autos SEM o cabeçalho (que traz os dados sensíveis).

    sanitize.py   a barreira de privacidade: tira a capa dos autos e mascara CPF/CNPJ/e-mail/telefone
    schemas.py    entrada (resultado das fases + páginas), o contrato do modelo e a saída
    prompt.py     os prompts (escada do crédito, regras de prova, formato do texto)
    graph.py      o grafo LangGraph (analisar → verificar) e o modelo
    logic.py      orquestra: sanitiza, roda o grafo, trata os erros
    api.py        POST /api/ia/analise
"""
