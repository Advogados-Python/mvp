from typing import Any, Iterable

from . import registro
from .constantes import SIGNIFICADO_DIVIDA_PAGA
from .modelos import Fase, FaseNoProcesso, ModuloDeAnalise
from .schemas import (
    EvidenciaSaida,
    FaseNoProcessoSaida,
    FaseSaida,
    FasesSaida,
    ModuloDetalhe,
    SignificadoDivida,
    TermoSaida,
)


def montar_fases() -> FasesSaida:
    return FasesSaida(
        fases=[
            FaseSaida(codigo=fase.codigo, rotulo=fase.rotulo, descricao=fase.descricao, ordem=fase.ordem)
            for fase in registro.ESCADA
        ],
        divida_paga=[
            SignificadoDivida(valor=resposta.value, significado=significado, acao=acao)
            for resposta, (significado, acao) in SIGNIFICADO_DIVIDA_PAGA.items()
        ],
    )


def detalhar_modulo(modulo: ModuloDeAnalise) -> ModuloDetalhe:
    detalhe = ModuloDetalhe(
        codigo=modulo.codigo,
        rotulo=modulo.rotulo,
        descricao=modulo.descricao,
        termos=[TermoSaida(nome=termo.nome, padrao=termo.padrao) for termo in modulo.termos],
    )
    if isinstance(modulo, Fase):  # só quem está na escada tem posição e responde sobre a dívida
        significado, acao = SIGNIFICADO_DIVIDA_PAGA[modulo.divida_paga]
        detalhe.ordem = modulo.ordem
        detalhe.divida_paga = modulo.divida_paga.value
        detalhe.significado, detalhe.acao = significado, acao
    return detalhe


def avaliar_no_processo(modulo: ModuloDeAnalise, codigo_da_fase_do_processo: str | None, evidencias: Iterable[Any]) -> FaseNoProcessoSaida:
    """O módulo visto por um processo: `codigo_da_fase_do_processo` é a fase final dele e `evidencias` são todas as que ele tem."""
    atual = registro.fase_da_escada(codigo_da_fase_do_processo) or registro.ESCADA[0]  # sem fase conhecida: o ponto de partida
    return _saida(modulo.no_processo(atual, evidencias))


def _saida(visao: FaseNoProcesso) -> FaseNoProcessoSaida:
    return FaseNoProcessoSaida(
        codigo=visao.modulo.codigo,
        rotulo=visao.modulo.rotulo,
        situacao=visao.situacao.value if visao.situacao else None,
        evidencias=[EvidenciaSaida.model_validate(ev) for ev in visao.evidencias],
        evidencia_principal=EvidenciaSaida.model_validate(visao.evidencia_principal) if visao.evidencia_principal else None,
        total_evidencias=len(visao.evidencias),
        evidencias_que_contam=visao.evidencias_que_contam,
    )
