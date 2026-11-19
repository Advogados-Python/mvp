from ..modelos import Alerta as ModuloAlerta
from ..modelos import Termo
from .constantes import TERMOS


class Alerta(ModuloAlerta):
    """Fora da escada: um sinal de que talvez não exista crédito a receber (ex.: "julgo improcedente").
    Vira um aviso para o advogado conferir; nunca muda a fase."""

    codigo = "ALERTA"
    rotulo = "Alerta"
    descricao = "Sinal de que pode não haver crédito a receber (ex.: pedido julgado improcedente)"
    termos = tuple(Termo(nome, padrao) for nome, padrao in TERMOS.items())
