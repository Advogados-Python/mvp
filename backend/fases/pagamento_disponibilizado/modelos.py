from ..modelos import Fase, RespostaDividaPaga, Termo
from .constantes import TERMOS


class PagamentoDisponibilizado(Fase):
    """Degrau 5: o valor foi depositado ou disponibilizado, mas falta o levantamento. A dívida provavelmente está paga."""

    codigo = "PAGAMENTO_DISPONIBILIZADO"
    rotulo = "Pagamento disponibilizado"
    descricao = "Valor depositado/disponibilizado - aguardando levantamento"
    ordem = 5
    divida_paga = RespostaDividaPaga.PROVAVEL
    termos = tuple(Termo(nome, padrao) for nome, padrao in TERMOS.items())
