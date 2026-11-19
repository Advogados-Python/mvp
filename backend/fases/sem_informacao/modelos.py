from ..modelos import Fase, RespostaDividaPaga, Termo
from .constantes import TERMOS


class SemInformacao(Fase):
    """Degrau 0, o ponto de partida: nenhuma fase foi encontrada nos autos. Nada pode ser afirmado sobre o crédito."""

    codigo = "SEM_INFORMACAO"
    rotulo = "Sem informação"
    descricao = "Nenhuma informação de fase encontrada"
    ordem = 0
    divida_paga = RespostaDividaPaga.SEM_INFORMACAO
    termos = tuple(Termo(nome, padrao) for nome, padrao in TERMOS.items())
