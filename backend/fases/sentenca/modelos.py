from ..modelos import Fase, RespostaDividaPaga, Termo
from .constantes import TERMOS


class Sentenca(Fase):
    """Degrau 1: o pedido foi julgado procedente ou o ente público foi condenado. O crédito existe, mas ainda não é exigível."""

    codigo = "SENTENCA"
    rotulo = "Sentença"
    descricao = "Sentença/condenação proferida"
    ordem = 1
    divida_paga = RespostaDividaPaga.NAO
    termos = tuple(Termo(nome, padrao) for nome, padrao in TERMOS.items())
