from fastapi import APIRouter

from ..db import Sessao
from ..receive.logic import exigir, obter_concluido
from ..userauths.deps import UsuarioLogado
from .schemas import EvidenciaSaida, SearchOut

router = APIRouter(prefix="/api/processos", tags=["4 · search"])


@router.get("/{processo_id}/search", response_model=SearchOut, summary="Fase 4, buscar os termos: as evidências reunidas neste processo")
def search(processo_id: str, usuario: UsuarioLogado, db: Sessao):
    processo = obter_concluido(db, usuario, processo_id)
    exigir(processo.resultado)  # sem o fechamento gravado, uma lista vazia enganaria: seria "nada achado"
    evidencias = processo.evidencias  # as linhas de `evidencias`, na ordem em que foram achadas
    por_fase: dict[str, int] = {}
    for ev in evidencias:
        por_fase[ev.fase] = por_fase.get(ev.fase, 0) + 1
    contam = sum(1 for ev in evidencias if ev.conta)
    return SearchOut(
        total_evidencias=len(evidencias),
        evidencias_que_contam=contam,
        evidencias_ignoradas=len(evidencias) - contam,
        por_fase=por_fase,
        evidencias=[EvidenciaSaida.model_validate(ev) for ev in evidencias],
    )
