from fastapi import APIRouter

from ..db import Sessao
from ..receive.logic import exigir, obter_concluido
from ..userauths.deps import UsuarioLogado
from .models import PERCENTUAL_SEM_TEXTO_PARA_ALERTA
from .schemas import ExtractOut

router = APIRouter(prefix="/api/processos", tags=["2 · extract"])


@router.get("/{processo_id}/extract", response_model=ExtractOut, summary="Fase 2, extrair conteúdo: o que foi lido deste PDF")
def extract(processo_id: str, usuario: UsuarioLogado, db: Sessao):
    leitura = exigir(obter_concluido(db, usuario, processo_id).leitura)  # a linha de `leituras`
    total, sem_texto = leitura.total_paginas, leitura.paginas_sem_texto
    percentual = sem_texto / total if total else 0.0
    return ExtractOut(
        total_paginas=total,
        paginas_lidas=total - sem_texto,
        paginas_sem_texto=sem_texto,
        percentual_sem_texto=percentual,
        pouco_legivel=total > 0 and percentual >= PERCENTUAL_SEM_TEXTO_PARA_ALERTA,
    )
