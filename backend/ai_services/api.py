from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import Config
from ..db import Sessao
from ..userauths.deps import UsuarioLogado
from . import logic
from .graph import IANaoConfigurada, construir_grafo, criar_modelo
from .schemas import AnaliseIA, PedidoIA

router = APIRouter(prefix="/api/ia", tags=["7 · ai_services"])


def obter_grafo(request: Request):
    """O grafo da IA, montado na primeira chamada e guardado no app (nada por requisição em variável de módulo).
    Sem chave ou sem as bibliotecas, só esta rota responde 503: o resto da API não depende da IA."""
    estado = request.app.state
    if getattr(estado, "grafo_ia", None) is None:
        try:
            estado.grafo_ia = construir_grafo(criar_modelo(estado.config))
        except IANaoConfigurada as erro:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(erro)) from None
    return estado.grafo_ia


GrafoIA = Annotated[Any, Depends(obter_grafo)]


@router.post(
    "/analise",
    response_model=AnaliseIA,
    summary="Camada de IA: confere a fase do crédito lendo o texto inteiro dos autos, sem o cabeçalho",
)
async def analise(pedido: PedidoIA, usuario: UsuarioLogado, db: Sessao, grafo: GrafoIA, config: Config):
    """Recebe o resultado das fases de leitura (`processo`) e o texto inteiro, página a página (`paginas`), sem o cabeçalho.

    A API retira por conta própria a capa dos autos que ainda venha no texto e mascara CPF, CNPJ, e-mail, telefone e número do
    processo; número, partes, advogados, OABs, juiz e nome do arquivo de `processo` são descartados e nunca chegam ao modelo.
    Nada é gravado. Cada trecho que a IA cita é conferido, letra por letra, contra a página (`verificada`).
    """
    db.close()  # a chamada ao modelo leva dezenas de segundos: não segura uma conexão do banco esse tempo todo
    return await logic.analisar(pedido, grafo, config)
