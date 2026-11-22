from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from ..config import Config
from ..db import Sessao
from ..finalize.logic import para_resumo
from ..finalize.schemas import ProcessoResumo
from ..pipeline import Andamento, Armazem, Fila
from ..userauths.deps import UsuarioLogado, usuario_do_pdf
from ..userauths.logic import criar_link_pdf
from ..userauths.models import Usuario
from . import logic
from .models import ErroEnvio, Processo, StatusAnalise
from .schemas import FalhaEnvio, LinkPdf, ReceiveOut, RespostaEnvio

router = APIRouter(prefix="/api/processos", tags=["1 · receive"])


@router.post(
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
    registro: Andamento,
):
    if len(arquivos) > config.max_arquivos_por_envio:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Envie no máximo {config.max_arquivos_por_envio} PDFs por vez."
        )
    aceitos, falhas, para_analisar = [], [], []
    for arquivo in arquivos:
        nome = logic.nome_seguro(arquivo.filename)
        try:  # um arquivo ruim não derruba o lote
            recebido = armazem.receber(arquivo.file)  # PdfRecebido
        except ErroEnvio as erro:
            falhas.append(FalhaEnvio(arquivo=nome, erro=str(erro)))
            continue
        finally:
            arquivo.file.close()
        processo, analisar = logic.registrar_envio(
            db, armazem, usuario, nome, recebido.temporario, recebido.sha256, recebido.tamanho_bytes
        )
        aceitos.append(processo)
        if analisar:
            para_analisar.append(processo.id)

    ids_aceitos = [processo.id for processo in aceitos]
    for processo_id in para_analisar:  # só depois do commit: a thread lê o registro por outra sessão
        fila.enfileirar(processo_id)
    if config.fila_sincrona:  # a análise já rodou, em outra sessão: recarrega (e ignora o que foi apagado no meio)
        db.expire_all()
        aceitos = [processo for id_ in ids_aceitos if (processo := db.get(Processo, id_))]
    return RespostaEnvio(processos=[para_resumo(p, registro) for p in aceitos], falhas=falhas)


@router.post(
    "/{processo_id}/reanalisar",
    response_model=ProcessoResumo,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Refaz a análise (por exemplo, depois de ensinar termos novos ao dicionário)",
)
def reanalisar(processo_id: str, usuario: UsuarioLogado, db: Sessao, fila: Fila, config: Config, registro: Andamento):
    processo = logic.obter_do_usuario(db, usuario, processo_id)
    if StatusAnalise(processo.status).em_andamento:
        return para_resumo(processo, registro)
    logic.reiniciar(processo)
    db.commit()
    fila.enfileirar(processo.id)
    if config.fila_sincrona:  # a análise já rodou, em outra sessão: recarrega
        db.expire_all()
        processo = logic.obter_do_usuario(db, usuario, processo_id)
    return para_resumo(processo, registro)


@router.delete("/{processo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Apaga o PDF e o resultado")
def excluir(processo_id: str, usuario: UsuarioLogado, db: Sessao, armazem: Armazem, registro: Andamento):
    logic.excluir(db, armazem, logic.obter_do_usuario(db, usuario, processo_id))
    registro.descartar(processo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{processo_id}/pdf-link", response_model=LinkPdf, summary="Link assinado e de vida curta para abrir o PDF")
def link_do_pdf(processo_id: str, request: Request, usuario: UsuarioLogado, db: Sessao, config: Config):
    processo = logic.obter_do_usuario(db, usuario, processo_id)
    token, expira = criar_link_pdf(usuario, processo.id, request.app.state.segredo, config.link_pdf_segundos)
    return LinkPdf(url=f"/api/processos/{processo.id}/pdf?assinatura={token}", expira_em=expira)


@router.get("/{processo_id}/pdf", summary="O PDF original (login ou link assinado; use #page=N para abrir na página)")
def baixar_pdf(
    processo_id: str,
    usuario: Annotated[Usuario, Depends(usuario_do_pdf)],
    db: Sessao,
    armazem: Armazem,
):
    processo = logic.obter_do_usuario(db, usuario, processo_id)
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



@router.get("/{processo_id}/receive", response_model=ReceiveOut, summary="Fase 1, receber o documento: o que foi guardado do PDF")
def receive(processo_id: str, usuario: UsuarioLogado, db: Sessao):
    processo = logic.obter_do_usuario(db, usuario, processo_id)
    return ReceiveOut(arquivo=processo.arquivo, tamanho_bytes=processo.tamanho_bytes, recebido_em=processo.criado_em, status=processo.status)
