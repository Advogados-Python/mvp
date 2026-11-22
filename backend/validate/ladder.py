"""A escada do crédito: os degraus, na ordem, e o que cada um diz sobre a dívida.

Quanto mais para o fim, mais perto de "dívida paga". Os termos que identificam cada degrau estão em search/terms.py.
Se a ordem ou os códigos estiverem errados, o import falha na subida, não numa análise.
"""

from .models import Fase, RespostaDividaPaga

SEM_INFORMACAO = Fase("SEM_INFORMACAO", "Sem informação", "Nenhuma informação de fase encontrada", 0, RespostaDividaPaga.SEM_INFORMACAO)
SENTENCA = Fase("SENTENCA", "Sentença", "Sentença/condenação proferida", 1, RespostaDividaPaga.NAO)
TRANSITO_EM_JULGADO = Fase("TRANSITO_EM_JULGADO", "Trânsito em julgado", "Transitou em julgado", 2, RespostaDividaPaga.NAO)
CUMPRIMENTO_DE_SENTENCA = Fase(
    "CUMPRIMENTO_DE_SENTENCA", "Cumprimento de sentença", "Em cumprimento de sentença / cálculos", 3, RespostaDividaPaga.NAO
)
REQUISICAO = Fase(
    "REQUISICAO", "Requisição (RPV/precatório)",
    "Requisição (RPV/OPV/precatório) determinada ou expedida - aguardando pagamento", 4, RespostaDividaPaga.NAO,
)
PAGAMENTO_DISPONIBILIZADO = Fase(
    "PAGAMENTO_DISPONIBILIZADO", "Pagamento disponibilizado",
    "Valor depositado/disponibilizado - aguardando levantamento", 5, RespostaDividaPaga.PROVAVEL,
)
QUITADO = Fase(
    "QUITADO", "Quitado", "Dívida paga/liquidada (levantamento ou extinção por pagamento)", 6, RespostaDividaPaga.SIM
)

ESCADA = (SEM_INFORMACAO, SENTENCA, TRANSITO_EM_JULGADO, CUMPRIMENTO_DE_SENTENCA, REQUISICAO, PAGAMENTO_DISPONIBILIZADO, QUITADO)

FASES = tuple((fase.codigo, fase.descricao) for fase in ESCADA)   # (código, descrição), do ponto de partida até "quitado"
ORDEM_FASE = {fase.codigo: fase.ordem for fase in ESCADA}
DESCRICAO_FASE = dict(FASES)

DIVIDA_PAGA_SIM = RespostaDividaPaga.SIM.value
DIVIDA_PAGA_PROVAVEL = RespostaDividaPaga.PROVAVEL.value
DIVIDA_PAGA_NAO = RespostaDividaPaga.NAO.value
DIVIDA_PAGA_SEM_INFO = RespostaDividaPaga.SEM_INFORMACAO.value

# Mesma tabela do README ("Como ler divida_paga"): resposta -> (significado, ação sugerida).
SIGNIFICADO_DIVIDA_PAGA = {
    RespostaDividaPaga.SIM: ("Há evidência de levantamento ou extinção por pagamento.", "Conferir a página indicada."),
    RespostaDividaPaga.PROVAVEL: (
        "Valor depositado ou disponibilizado; falta confirmar o levantamento.",
        "Conferir a página indicada.",
    ),
    RespostaDividaPaga.NAO: ("O crédito ainda não foi pago; a fase diz em que ponto está.", "Acompanhar a fase."),
    RespostaDividaPaga.SEM_INFORMACAO: ("Nenhum termo de fase foi encontrado no PDF.", "Ler o PDF e verificar os avisos."),
}


def fase_da_escada(codigo):
    """A fase com este código, ou None se ele não é um degrau da escada (inclusive "ALERTA")."""
    return next((fase for fase in ESCADA if fase.codigo == codigo), None)


def _validar() -> None:
    if [fase.ordem for fase in ESCADA] != list(range(len(ESCADA))):
        raise RuntimeError(f"A escada precisa ter as posições 0..{len(ESCADA) - 1} em ordem: {[(f.codigo, f.ordem) for f in ESCADA]}")
    codigos = [fase.codigo for fase in ESCADA]
    if len(set(codigos)) != len(codigos):
        raise RuntimeError(f"Há fases com código repetido: {codigos}")


_validar()
