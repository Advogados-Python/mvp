"""Leitor de processos: o pipeline que lê o PDF e responde fase + dívida paga (regex + dicionário de termos, sem IA).

Organização (um papel por arquivo):
    constantes.py   regex, parâmetros e a escada/dicionário (lidos de backend/fases/, onde cada fase tem o seu módulo)
    classes.py      Pagina, Evidencia, ResultadoProcesso
    erros.py        erros próprios do pipeline
    funcoes.py      ler -> extrair -> buscar -> classificar -> exportar
"""

from .classes import *
from .erros import *
from .constantes import *
from .funcoes import *
