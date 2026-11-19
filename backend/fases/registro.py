"""O registro das fases: quem existe e em que ordem.

É aqui (e só aqui) que a escada é montada, juntando os módulos. O leitor lê a escada e o dicionário de termos deste registro.
Se um módulo for acrescentado sem posição certa ou com código/termo repetido, o import falha na subida, não numa análise.
"""

from typing import Optional

from .alerta import ALERTA
from .cumprimento_de_sentenca import FASE as CUMPRIMENTO_DE_SENTENCA
from .modelos import Fase, ModuloDeAnalise
from .pagamento_disponibilizado import FASE as PAGAMENTO_DISPONIBILIZADO
from .quitado import FASE as QUITADO
from .requisicao import FASE as REQUISICAO
from .sem_informacao import FASE as SEM_INFORMACAO
from .sentenca import FASE as SENTENCA
from .transito_em_julgado import FASE as TRANSITO_EM_JULGADO

# A escada, do ponto de partida até "dívida paga". Quanto mais para o fim, mais perto de pago.
ESCADA: tuple[Fase, ...] = (
    SEM_INFORMACAO,
    SENTENCA,
    TRANSITO_EM_JULGADO,
    CUMPRIMENTO_DE_SENTENCA,
    REQUISICAO,
    PAGAMENTO_DISPONIBILIZADO,
    QUITADO,
)

# Todos os módulos de análise: a escada e, depois dela, o que está fora dela (o alerta). A ordem é a da busca de termos.
MODULOS: tuple[ModuloDeAnalise, ...] = (*ESCADA, ALERTA)


def por_codigo(codigo: str) -> Optional[ModuloDeAnalise]:
    return next((modulo for modulo in MODULOS if modulo.codigo == codigo), None)


def por_slug(slug: str) -> Optional[ModuloDeAnalise]:
    return next((modulo for modulo in MODULOS if modulo.slug == slug), None)


def fase_da_escada(codigo: Optional[str]) -> Optional[Fase]:
    """A fase com este código, ou None se ele não é um degrau da escada (inclusive "ALERTA")."""
    return next((fase for fase in ESCADA if fase.codigo == codigo), None)


def dicionario_de_termos() -> dict[str, dict[str, str]]:
    """{código do módulo: {nome do termo: expressão regular}}, na ordem dos módulos e sem os que não têm termos."""
    return {modulo.codigo: {termo.nome: termo.padrao for termo in modulo.termos} for modulo in MODULOS if modulo.termos}


def _validar() -> None:
    if [fase.ordem for fase in ESCADA] != list(range(len(ESCADA))):
        raise RuntimeError(f"A escada precisa ter as posições 0..{len(ESCADA) - 1} em ordem: {[(f.codigo, f.ordem) for f in ESCADA]}")
    for rotulo, valores in (("código", [m.codigo for m in MODULOS]), ("slug", [m.slug for m in MODULOS])):
        repetidos = {v for v in valores if valores.count(v) > 1}
        if repetidos:
            raise RuntimeError(f"Há módulos de fase com {rotulo} repetido: {sorted(repetidos)}")
    nomes = [termo.nome for modulo in MODULOS for termo in modulo.termos]
    repetidos = {nome for nome in nomes if nomes.count(nome) > 1}
    if repetidos:  # o nome do termo é o que aparece no relatório: dois módulos com o mesmo nome se confundiriam
        raise RuntimeError(f"Há termos com o mesmo nome em módulos diferentes: {sorted(repetidos)}")


_validar()
