from ..modelos import Fase, RespostaDividaPaga, Termo
from .constantes import TERMOS


class TransitoEmJulgado(Fase):
    """Degrau 2: não cabe mais recurso. A sentença passa a poder ser executada."""

    codigo = "TRANSITO_EM_JULGADO"
    rotulo = "Trânsito em julgado"
    descricao = "Transitou em julgado"
    ordem = 2
    divida_paga = RespostaDividaPaga.NAO
    termos = tuple(Termo(nome, padrao) for nome, padrao in TERMOS.items())
