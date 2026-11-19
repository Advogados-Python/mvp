from ..modelos import Fase, RespostaDividaPaga, Termo
from .constantes import TERMOS


class Requisicao(Fase):
    """Degrau 4: a requisição de pagamento (RPV, OPV ou precatório) foi determinada ou expedida. O pagamento ainda não saiu."""

    codigo = "REQUISICAO"
    rotulo = "Requisição (RPV/precatório)"
    descricao = "Requisição (RPV/OPV/precatório) determinada ou expedida - aguardando pagamento"
    ordem = 4
    divida_paga = RespostaDividaPaga.NAO
    termos = tuple(Termo(nome, padrao) for nome, padrao in TERMOS.items())
