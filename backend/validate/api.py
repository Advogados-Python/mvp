from fastapi import APIRouter

from ..db import Sessao
from ..receive.logic import exigir, obter_concluido
from ..search.schemas import EvidenciaSaida
from ..userauths.deps import UsuarioLogado
from .logic import montar_fases
from .schemas import FasesSaida, ValidateOut

router = APIRouter(prefix="/api", tags=["5 · validate"])


@router.get("/fases", response_model=FasesSaida, summary="A escada de fases do crédito e o significado de divida_paga (pública)")
def fases():
    return montar_fases()


@router.get("/processos/{processo_id}/validate", response_model=ValidateOut, summary="Fase 5, validar evidências: o que foi concluído")
def validate(processo_id: str, usuario: UsuarioLogado, db: Sessao):
    processo = obter_concluido(db, usuario, processo_id)
    conclusao = exigir(processo.conclusao)  # a linha de `conclusoes`
    fechamento = exigir(processo.resultado)  # os avisos e as contagens estão no fechamento (`resultados`)
    principal = fechamento.evidencia_principal
    return ValidateOut(
        fase=conclusao.fase,
        fase_descricao=conclusao.fase_descricao,
        divida_paga=conclusao.divida_paga,
        avisos=fechamento.avisos or [],
        evidencia_principal=EvidenciaSaida.model_validate(principal) if principal else None,
        evidencias_que_contam=fechamento.evidencias_que_contam,
        evidencias_ignoradas=fechamento.total_evidencias - fechamento.evidencias_que_contam,
    )
