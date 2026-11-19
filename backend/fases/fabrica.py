"""A API padrão de um módulo de fase. Cada <fase>/rotas.py chama `criar_roteador` com a sua fase: todos os módulos têm
as mesmas duas rotas, cada uma sob o seu próprio prefixo (/api/fases/<slug>)."""

from fastapi import APIRouter, HTTPException, status

from ..autenticacao.dependencias import UsuarioLogado
from ..nucleo.dependencias import Sessao
from ..processos import funcoes as funcoes_processos
from ..processos.modelos import StatusAnalise
from . import funcoes
from .modelos import ModuloDeAnalise
from .schemas import FaseNoProcessoSaida, ModuloDetalhe


def criar_roteador(modulo: ModuloDeAnalise) -> APIRouter:
    roteador = APIRouter(prefix=f"/{modulo.slug}", tags=[f"fase · {modulo.slug}"])

    @roteador.get("", response_model=ModuloDetalhe, summary=f"{modulo.rotulo}: o que é e como o sistema a reconhece")
    def definicao(_usuario: UsuarioLogado):
        return funcoes.detalhar_modulo(modulo)

    @roteador.get(
        "/processos/{processo_id}",
        response_model=FaseNoProcessoSaida,
        summary=f"{modulo.rotulo}: a situação do processo nela e as evidências que a sustentam",
    )
    def no_processo(processo_id: str, usuario: UsuarioLogado, db: Sessao):
        processo = funcoes_processos.obter_do_usuario(db, usuario, processo_id)  # 404 para processo de outra pessoa
        if processo.status == StatusAnalise.FALHOU.value:
            raise HTTPException(status.HTTP_409_CONFLICT, "A análise deste processo falhou: não há fase para consultar.")
        if processo.status != StatusAnalise.CONCLUIDO.value:
            raise HTTPException(status.HTTP_409_CONFLICT, "A análise deste processo ainda não terminou.")
        evidencias = (processo.resultado or {}).get("evidencias", [])
        return funcoes.avaliar_no_processo(modulo, processo.fase, evidencias)

    return roteador
