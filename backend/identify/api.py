from fastapi import APIRouter

from ..db import Sessao
from ..receive.logic import exigir, obter_concluido
from ..userauths.deps import UsuarioLogado
from .schemas import IdentifyOut

router = APIRouter(prefix="/api/processos", tags=["3 · identify"])


@router.get("/{processo_id}/identify", response_model=IdentifyOut, summary="Fase 3, identificar o processo: o que foi identificado")
def identify(processo_id: str, usuario: UsuarioLogado, db: Sessao):
    identificacao = exigir(obter_concluido(db, usuario, processo_id).identificacao)  # a linha de `identificacoes`
    return IdentifyOut.model_validate(identificacao)
