from ..modelos import Fase, RespostaDividaPaga, Termo
from .constantes import TERMOS


class CumprimentoDeSentenca(Fase):
    """Degrau 3: a execução começou e os valores estão sendo apurados (cálculos, contas de liquidação, homologação)."""

    codigo = "CUMPRIMENTO_DE_SENTENCA"
    rotulo = "Cumprimento de sentença"
    descricao = "Em cumprimento de sentença / cálculos"
    ordem = 3
    divida_paga = RespostaDividaPaga.NAO
    termos = tuple(Termo(nome, padrao) for nome, padrao in TERMOS.items())
