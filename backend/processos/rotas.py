import asyncio
import json
import time
from dataclasses import asdict
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func, select

from ..autenticacao.dependencias import UsuarioLogado, usuario_do_pdf
from ..autenticacao.funcoes import criar_link_pdf
from ..nucleo.dependencias import Config, Sessao
from ..usuarios.modelos import Usuario
from . import funcoes
from .constantes import SSE_INTERVALO_MINIMO_SEGUNDOS, SSE_PING_SEGUNDOS
from .dependencias import Armazem, Fila, Progresso
from .erros import ErroEnvio
from .modelos import Processo, StatusAnalise
from .progresso import RegistroProgresso
from .schemas import FalhaEnvio, LinkPdf, ListaProcessos, ProcessoDetalhe, ProcessoResumo, RespostaEnvio

roteador = APIRouter(prefix="/api/processos", tags=["processos"])


@roteador.post(
    "",
    response_model=RespostaEnvio,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Envia PDFs. Responde na hora; a análise segue em segundo plano (consulte o status)",
)
def enviar(
    arquivos: Annotated[list[UploadFile], File(description="Um ou mais PDFs de autos de processo")],
    usuario: UsuarioLogado,
    db: Sessao,
    config: Config,
    armazem: Armazem,
    fila: Fila,
    registro: Progresso,
):
    if len(arquivos) > config.max_arquivos_por_envio:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Envie no máximo {config.max_arquivos_por_envio} PDFs por vez."
        )
    aceitos, falhas, para_analisar = [], [], []
    for arquivo in arquivos:
        nome = funcoes.nome_seguro(arquivo.filename)
        try:  # um arquivo ruim não derruba o lote
            temporario, sha256, tamanho = armazem.receber(arquivo.file)
        except ErroEnvio as erro:
            falhas.append(FalhaEnvio(arquivo=nome, erro=str(erro)))
            continue
        finally:
            arquivo.file.close()
        processo, analisar = funcoes.registrar_envio(db, armazem, usuario, nome, temporario, sha256, tamanho)
        aceitos.append(processo)
        if analisar:
            para_analisar.append(processo.id)

    ids_aceitos = [processo.id for processo in aceitos]
    for processo_id in para_analisar:  # só depois do commit: a thread lê o registro por outra sessão
        fila.enfileirar(processo_id)
    if config.fila_sincrona:  # a análise já rodou, em outra sessão: recarrega (e ignora o que foi apagado no meio)
        db.expire_all()
        aceitos = [processo for id_ in ids_aceitos if (processo := db.get(Processo, id_))]
    return RespostaEnvio(processos=[funcoes.para_resumo(p, registro) for p in aceitos], falhas=falhas)


@roteador.get("", response_model=ListaProcessos, summary="Lista os seus processos (mais novos primeiro)")
def listar(
    usuario: UsuarioLogado,
    db: Sessao,
    registro: Progresso,
    status_analise: Annotated[Optional[StatusAnalise], Query(alias="status")] = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 200,
    deslocamento: Annotated[int, Query(ge=0)] = 0,
):
    filtros = [Processo.dono_id == usuario.id]
    if status_analise:
        filtros.append(Processo.status == status_analise.value)
    total = db.scalar(select(func.count()).select_from(Processo).where(*filtros)) or 0
    linhas = db.scalars(
        select(Processo).where(*filtros).order_by(Processo.criado_em.desc()).limit(limite).offset(deslocamento)
    ).all()
    return ListaProcessos(processos=[funcoes.para_resumo(p, registro) for p in linhas], total=total)


@roteador.get("/{processo_id}", response_model=ProcessoDetalhe, summary="Resultado completo, com as evidências")
def detalhar(processo_id: str, usuario: UsuarioLogado, db: Sessao, registro: Progresso):
    return funcoes.para_detalhe(funcoes.obter_do_usuario(db, usuario, processo_id), registro)


@roteador.post(
    "/{processo_id}/reanalisar",
    response_model=ProcessoResumo,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Refaz a análise (por exemplo, depois de ensinar termos novos ao dicionário)",
)
def reanalisar(processo_id: str, usuario: UsuarioLogado, db: Sessao, fila: Fila, config: Config, registro: Progresso):
    processo = funcoes.obter_do_usuario(db, usuario, processo_id)
    if StatusAnalise(processo.status).em_andamento:
        return funcoes.para_resumo(processo, registro)
    funcoes.reiniciar(processo)
    db.commit()
    fila.enfileirar(processo.id)
    if config.fila_sincrona:  # a análise já rodou, em outra sessão: recarrega
        db.expire_all()
        processo = funcoes.obter_do_usuario(db, usuario, processo_id)
    return funcoes.para_resumo(processo, registro)


@roteador.delete("/{processo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Apaga o PDF e o resultado")
def excluir(processo_id: str, usuario: UsuarioLogado, db: Sessao, armazem: Armazem, registro: Progresso):
    funcoes.excluir(db, armazem, funcoes.obter_do_usuario(db, usuario, processo_id))
    registro.descartar(processo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _evento(nome: str, dados: dict) -> str:
    return f"event: {nome}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


def _estado_atual(fabrica, registro: RegistroProgresso, processo_id: str) -> Optional[dict]:
    """{"status", "progresso"} de agora, ou None se o processo foi apagado. Roda numa thread (consulta o banco).

    Enquanto a análise roda, o registro basta (só existe entrada sem falha durante ela) e o banco nem é consultado:
    um PDF de mil páginas gera milhares de avisos, e cada um custaria uma consulta.
    """
    progresso = registro.obter(processo_id)
    if progresso is not None and not progresso.falhou:
        return {"status": StatusAnalise.ANALISANDO.value, "progresso": asdict(progresso)}
    with fabrica() as db:
        processo = db.get(Processo, processo_id)
        situacao = processo.status if processo else None
    if situacao is None:
        return None
    visivel = registro.visivel(processo_id, situacao)
    return {"status": situacao, "progresso": asdict(visivel) if visivel else None}


async def _transmitir(fabrica, registro: RegistroProgresso, processo_id: str, duracao_maxima: float):
    """Eventos: `estado` (a cada mudança), `fim` (CONCLUIDO/FALHOU: o resultado vem do GET normal), `removido` e
    `reconectar` (o limite de duração foi atingido: abra de novo). A primeira mensagem já é o estado de agora."""
    inicio = time.monotonic()
    ultimo = None
    with registro.assinar(processo_id) as mudou:  # assina ANTES de ler: nada que aconteça no meio se perde
        while True:
            mudou.clear()
            estado = await asyncio.to_thread(_estado_atual, fabrica, registro, processo_id)
            if estado is None:
                yield _evento("removido", {})
                return
            if estado != ultimo:
                ultimo = estado
                terminou = estado["status"] in (StatusAnalise.CONCLUIDO.value, StatusAnalise.FALHOU.value)
                yield _evento("fim" if terminou else "estado", estado)
                if terminou:
                    return
            restante = duracao_maxima - (time.monotonic() - inicio)
            if restante <= 0:
                yield _evento("reconectar", {})
                return
            try:
                await asyncio.wait_for(mudou.wait(), timeout=min(SSE_PING_SEGUNDOS, restante))
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            await asyncio.sleep(SSE_INTERVALO_MINIMO_SEGUNDOS)  # junta as mudanças que vierem em rajada


@roteador.get(
    "/{processo_id}/eventos",
    response_class=StreamingResponse,
    summary="Acompanha a análise ao vivo (Server-Sent Events); o resultado em si vem de GET /{processo_id}",
)
def acompanhar(processo_id: str, request: Request, usuario: UsuarioLogado, db: Sessao, registro: Progresso, config: Config):
    funcoes.obter_do_usuario(db, usuario, processo_id)  # 404 para quem não é o dono, como nas demais rotas
    db.close()  # a transmissão dura segundos: não segura uma conexão do banco esse tempo todo
    return StreamingResponse(
        _transmitir(request.app.state.fabrica, registro, processo_id, config.sse_duracao_maxima),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},  # sem cache e sem buffer em proxy (nginx)
    )


@roteador.post("/{processo_id}/pdf-link", response_model=LinkPdf, summary="Link assinado e de vida curta para abrir o PDF")
def link_do_pdf(processo_id: str, request: Request, usuario: UsuarioLogado, db: Sessao, config: Config):
    processo = funcoes.obter_do_usuario(db, usuario, processo_id)
    token, expira = criar_link_pdf(usuario, processo.id, request.app.state.segredo, config.link_pdf_segundos)
    return LinkPdf(url=f"/api/processos/{processo.id}/pdf?assinatura={token}", expira_em=expira)


@roteador.get("/{processo_id}/pdf", summary="O PDF original (login ou link assinado; use #page=N para abrir na página)")
def baixar_pdf(
    processo_id: str,
    usuario: Annotated[Usuario, Depends(usuario_do_pdf)],
    db: Sessao,
    armazem: Armazem,
):
    processo = funcoes.obter_do_usuario(db, usuario, processo_id)
    caminho = armazem.caminho(processo.id)
    if not caminho.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF não encontrado.")
    return FileResponse(
        caminho,
        media_type="application/pdf",
        filename=processo.arquivo,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},  # autos têm dados pessoais: nada de cache compartilhado
    )
