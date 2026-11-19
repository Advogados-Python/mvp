from ..modelos import Fase, RespostaDividaPaga, Termo
from .constantes import TERMOS


class Quitado(Fase):
    """Degrau 6, o último: há evidência de levantamento ou de extinção da execução por pagamento. A dívida foi paga."""

    codigo = "QUITADO"
    rotulo = "Quitado"
    descricao = "Dívida paga/liquidada (levantamento ou extinção por pagamento)"
    ordem = 6
    divida_paga = RespostaDividaPaga.SIM
    termos = tuple(Termo(nome, padrao) for nome, padrao in TERMOS.items())
