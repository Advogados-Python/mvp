from typing import Annotated, Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from ..db import Sessao
from ..pipeline import Andamento
from ..receive import logic
from ..receive.models import Processo, StatusAnalise
from ..userauths.deps import UsuarioLogado
from .logic import CARREGAR_FASES, para_detalhe, para_resumo
from .schemas import FinalizeOut, ListaProcessos, ProcessoDetalhe

router = APIRouter(prefix="/api/processos", tags=["6 · finalize"])


@router.get("", response_model=ListaProcessos, summary="Lista os seus processos (mais novos primeiro)")
def listar(
    usuario: UsuarioLogado,
    db: Sessao,
    registro: Andamento,
    status_analise: Annotated[Optional[StatusAnalise], Query(alias="status")] = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 200,
    deslocamento: Annotated[int, Query(ge=0)] = 0,
):
    filtros = [Processo.dono_id == usuario.id]
    if status_analise:
        filtros.append(Processo.status == status_analise.value)
    total = db.scalar(select(func.count()).select_from(Processo).where(*filtros)) or 0
    linhas = db.scalars(
        select(Processo).where(*filtros).options(*CARREGAR_FASES).order_by(Processo.criado_em.desc()).limit(limite).offset(deslocamento)
    ).all()
    return ListaProcessos(processos=[para_resumo(p, registro) for p in linhas], total=total)


@router.get("/{processo_id}", response_model=ProcessoDetalhe, summary="Resultado completo, com as evidências")
def detalhar(processo_id: str, usuario: UsuarioLogado, db: Sessao, registro: Andamento):
    return para_detalhe(logic.obter_do_usuario(db, usuario, processo_id), registro)



@router.get("/{processo_id}/finalize", response_model=FinalizeOut, summary="Fase 6, finalizar o resultado: o que foi gravado no fim")
def finalize(processo_id: str, usuario: UsuarioLogado, db: Sessao):
    processo = logic.obter_do_usuario(db, usuario, processo_id)
    identificacao, conclusao = processo.identificacao, processo.conclusao
    return FinalizeOut(
        status=processo.status,
        concluido_em=processo.concluido_em,
        erro=processo.erro,
        numero_processo=identificacao.numero_processo if identificacao else None,
        tribunal=identificacao.tribunal if identificacao else None,
        fase=conclusao.fase if conclusao else None,
        divida_paga=conclusao.divida_paga if conclusao else None,
        resultado_gravado=processo.resultado is not None,
    )
