"""A camada de IA, ponta a ponta: sanitiza o pedido, roda o grafo e monta a resposta.

`preparar` é a única porta para o modelo: tudo o que o grafo vê passou por ela. Nada daqui grava no banco nem em disco, e nenhum
log leva texto dos autos (o texto tem dados pessoais: LGPD).
"""

import logging

from fastapi import HTTPException, status

from ..config import Configuracoes
from ..validate.ladder import DESCRICAO_FASE
from ..validate.logic import responder_divida_paga
from .sanitize import ErroCabecalho, anonimizar, remover_cabecalho
from .schemas import AnaliseIA, PaginaEntrada, PedidoIA, ProcessoEntrada

registro = logging.getLogger("ribeiro.ia")

MENSAGEM_FALHA_DO_MODELO = "Não foi possível obter o parecer da IA agora. Tente novamente em instantes."


def preparar(pedido: PedidoIA, limite_caracteres: int) -> tuple:
    """(processo, páginas, páginas de capa retiradas): o que de fato pode seguir para o modelo.

    - ordena as páginas e tira a capa dos autos (se o chamador já tirou, não há o que tirar);
    - mascara CPF, CNPJ, e-mail, telefone e número do processo no texto, nos trechos e nos avisos;
    - descarta evidências de páginas que não seguem (as da capa, por exemplo): o trecho delas viria de texto que não deve sair.
    """
    ordenadas = sorted(pedido.paginas, key=lambda pagina: pagina.numero)
    try:
        sem_capa, removidas = remover_cabecalho(ordenadas)
    except ErroCabecalho as erro:
        raise HTTPException(422, str(erro)) from None

    paginas = [PaginaEntrada(numero=pagina.numero, texto=anonimizar(pagina.texto)) for pagina in sem_capa if pagina.texto.strip()]
    if not paginas:
        raise HTTPException(422, "Não sobrou texto para analisar depois de retirar o cabeçalho.")
    caracteres = sum(len(pagina.texto) for pagina in paginas)
    if caracteres > limite_caracteres:
        raise HTTPException(
            413,
            f"O texto tem {caracteres} caracteres e o limite da camada de IA é {limite_caracteres}.",
        )

    enviadas = {pagina.numero for pagina in paginas}
    processo: ProcessoEntrada = pedido.processo.model_copy(update={
        "avisos": [anonimizar(aviso) for aviso in pedido.processo.avisos],
        "evidencias": [
            evidencia.model_copy(update={"trecho": anonimizar(evidencia.trecho)})
            for evidencia in pedido.processo.evidencias if evidencia.pagina in enviadas
        ],
    })
    return processo, paginas, removidas


async def analisar(pedido: PedidoIA, grafo, config: Configuracoes) -> AnaliseIA:
    processo, paginas, removidas = preparar(pedido, config.ia_max_caracteres)
    try:
        estado = await grafo.ainvoke({"processo": processo, "paginas": paginas})
    except Exception as erro:
        # Só o tipo do erro vai para o log: a mensagem de uma falha de validação pode trazer um pedaço da resposta do modelo
        # (que cita os autos), e a de uma falha de rede, o endereço e a chave.
        registro.error("A camada de IA falhou: %s", type(erro).__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, MENSAGEM_FALHA_DO_MODELO) from None

    parecer = estado["parecer"]
    return AnaliseIA(
        modelo=config.ia_modelo,
        fase_sugerida=parecer.fase,
        fase_descricao=DESCRICAO_FASE[parecer.fase],
        divida_paga_sugerida=responder_divida_paga(parecer.fase),
        concorda_com_regras=parecer.fase == processo.fase,
        confianca=estado["confianca"],
        resumo=parecer.resumo.strip(),
        justificativa=parecer.justificativa.strip(),
        evidencias=estado["evidencias"],
        pontos_de_atencao=estado["pontos_de_atencao"],
        paginas_analisadas=len(paginas),
        paginas_cabecalho_removidas=removidas,
        caracteres_enviados=sum(len(pagina.texto) for pagina in paginas),
    )
