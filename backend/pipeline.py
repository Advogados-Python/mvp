"""A esteira: encadeia as seis fases de leitura, roda em segundo plano e informa em que etapa cada PDF está.

    1 receive ─► 2 extract ─► 3 identify ─► 4 search ─► 5 validate ─► 6 finalize
    (o upload)   (texto)      (processo)    (termos)     (conclusão)    (grava)

Aqui só se COMPÕE o que as fases entregam: a lógica de cada uma mora na pasta dela.
    processar_pdf      roda as fases 2 a 5 num PDF e devolve o ResultadoProcesso (não toca no banco: serve ao terminal e ao notebook)
    analisar_processo  o job: reivindica o processo, roda as fases, grava o resultado nas tabelas das fases (fase 6) e anuncia o fim
    FilaAnalise        a fila: threads do próprio processo (o banco manda no status)
    RegistroProgresso  em que etapa está cada análise em andamento, em memória
    router             GET /api/processos/{id}/eventos: o andamento ao vivo (SSE)
"""

import asyncio
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Iterator, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from .config import Config
from .db import Sessao, agora
from .extract.logic import AvisoDeEtapa, extrair_conteudo
from .extract.models import STAGE as STAGE_EXTRACT
from .extract.models import ErroRibeiro
from .finalize.logic import MENSAGEM_ERRO_INESPERADO, gravar_resultado, mensagem_do_erro
from .finalize.models import STAGE as STAGE_FINALIZE
from .finalize.models import ResultadoProcesso
from .identify.logic import identificar_processo
from .identify.models import STAGE as STAGE_IDENTIFY
from .receive.logic import obter_do_usuario
from .receive.models import Processo, StatusAnalise
from .receive.store import ArmazemPdf
from .search.logic import buscar_termos
from .search.models import STAGE as STAGE_SEARCH
from .userauths.deps import UsuarioLogado
from .validate.logic import validar_evidencias
from .validate.models import STAGE as STAGE_VALIDATE

# Os códigos de andamento, na ordem real de execução (o recebimento fica de fora: é o status PENDENTE, não uma etapa).
# O front espelha esta lista (frontend/src/lib/tipos.ts, ETAPAS): mantenha os dois lados em sincronia.
ETAPAS = (STAGE_EXTRACT, STAGE_IDENTIFY, STAGE_SEARCH, STAGE_VALIDATE, STAGE_FINALIZE)

SSE_PING_SEGUNDOS = 15                # comentário periódico para a conexão não parecer ociosa
SSE_INTERVALO_MINIMO_SEGUNDOS = 0.2   # no máximo ~5 eventos por segundo, mesmo que o PDF tenha mil páginas

registro = logging.getLogger("ribeiro.analise")
registro_fila = logging.getLogger("ribeiro.fila")


# ======================================================================================
# O andamento: em que etapa cada PDF está (só na memória, de propósito)
# ======================================================================================
# Só o que o pipeline de fato informou entra aqui. Nada é estimado nem simulado. O banco continua sendo a verdade sobre o
# STATUS; este registro só diz "onde" a análise está enquanto ela roda. Se o servidor cair, a fila devolve tudo para PENDENTE
# e a análise recomeça do zero: gravar isto no banco exigiria uma coluna nova para guardar algo que só vale por segundos.
MAX_REGISTROS = 1000  # teto de segurança: entradas de falha ficam até alguém reanalisar ou apagar


@dataclass(frozen=True)
class Progresso:
    etapa: str
    atual: Optional[int] = None  # páginas já processadas na etapa (só nas etapas que andam página a página)
    total: Optional[int] = None
    falhou: bool = False         # a análise parou nesta etapa


class RegistroProgresso:
    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._estado: dict[str, Progresso] = {}
        self._ouvintes: dict[str, set] = {}

    # ---- quem analisa (threads da fila)
    def atualizar(self, processo_id: str, etapa: str, atual: Optional[int] = None, total: Optional[int] = None) -> None:
        with self._trava:
            self._estado.pop(processo_id, None)  # reinserir no fim: o mais antigo é o primeiro a sair do teto
            self._estado[processo_id] = Progresso(etapa, atual, total)
            while len(self._estado) > MAX_REGISTROS:
                self._estado.pop(next(iter(self._estado)))
        self._avisar(processo_id)

    def falhar(self, processo_id: str) -> None:
        """A análise parou: guarda em que etapa (para a tela dizer onde falhou) até reanalisarem ou apagarem."""
        with self._trava:
            atual = self._estado.get(processo_id)
            if atual is None:
                return
            self._estado[processo_id] = Progresso(atual.etapa, atual.atual, atual.total, falhou=True)
        self._avisar(processo_id)

    def descartar(self, processo_id: str) -> None:
        """Terminou (ou o processo foi apagado): não há mais o que acompanhar."""
        with self._trava:
            existia = self._estado.pop(processo_id, None) is not None
        if existia:
            self._avisar(processo_id)

    # ---- quem consulta
    def obter(self, processo_id: str) -> Optional[Progresso]:
        with self._trava:
            return self._estado.get(processo_id)

    def visivel(self, processo_id: str, status: str) -> Optional[Progresso]:
        """O progresso que vale mostrar para este status: em ANALISANDO, o andamento; em FALHOU, onde parou.

        Qualquer outro caso é None, e isso também esconde sobras de uma execução anterior (por exemplo, a falha
        antiga de um processo que acabou de ser reenviado para a fila).
        """
        progresso = self.obter(processo_id)
        if progresso is None:
            return None
        if status == "ANALISANDO" and not progresso.falhou:
            return progresso
        if status == "FALHOU" and progresso.falhou:
            return progresso
        return None

    @contextmanager
    def assinar(self, processo_id: str) -> Iterator[asyncio.Event]:
        """Para código assíncrono (o SSE): devolve um Event que é acionado a cada mudança deste processo.

        Chame de dentro do loop de eventos. As threads da fila acionam o Event com call_soon_threadsafe.
        """
        ouvinte = (asyncio.get_running_loop(), asyncio.Event())
        with self._trava:
            self._ouvintes.setdefault(processo_id, set()).add(ouvinte)
        try:
            yield ouvinte[1]
        finally:
            with self._trava:
                conjunto = self._ouvintes.get(processo_id)
                if conjunto is not None:
                    conjunto.discard(ouvinte)
                    if not conjunto:
                        del self._ouvintes[processo_id]

    def _avisar(self, processo_id: str) -> None:
        with self._trava:
            ouvintes = list(self._ouvintes.get(processo_id, ()))
        for loop, evento in ouvintes:
            try:
                loop.call_soon_threadsafe(evento.set)
            except RuntimeError:  # o loop já foi fechado (servidor encerrando)
                pass


# ======================================================================================
# As fases 2 a 5, compostas
# ======================================================================================
def processar_pdf(caminho, aviso: Optional[AvisoDeEtapa] = None) -> ResultadoProcesso:
    """Roda as fases de leitura em um PDF (extrair, identificar, buscar, validar) e devolve o ResultadoProcesso.

    `aviso`, se dado, é chamado ao entrar em cada fase (o STAGE de cada fase) e, nas que andam página a página, a cada página.
    A fase só é anunciada quando ela realmente começa: quem acompanha pode tratar as anteriores como feitas.
    """
    def informar(etapa, atual=None, total=None):
        if aviso:
            aviso(etapa, atual, total)

    caminho = Path(caminho)

    informar(STAGE_EXTRACT)
    leitura = extrair_conteudo(caminho, aviso)
    resultado = ResultadoProcesso(arquivo=caminho.name, total_paginas=leitura.total_paginas, paginas_sem_texto=leitura.paginas_sem_texto)
    resultado.avisos.extend(leitura.avisos)

    informar(STAGE_IDENTIFY)
    processo = identificar_processo(leitura.paginas)
    for nome in ("numero_processo", "tribunal", "classe", "orgao_julgador", "valor_causa", "valor_requisitado", "data_emissao_pdf", "juiz"):
        setattr(resultado, nome, getattr(processo, nome))
    resultado.partes = [asdict(parte) for parte in processo.partes]
    resultado.advogados = processo.advogados
    resultado.oabs = processo.oabs
    resultado.avisos.extend(processo.avisos)

    informar(STAGE_SEARCH, 0, len(leitura.paginas))
    resultado.evidencias = buscar_termos(leitura.paginas, aviso)

    informar(STAGE_VALIDATE)
    conclusao = validar_evidencias(resultado.evidencias)
    resultado.fase = conclusao.fase
    resultado.fase_descricao = conclusao.fase_descricao
    resultado.divida_paga = conclusao.divida_paga
    resultado.avisos.extend(conclusao.avisos)
    return resultado


# ======================================================================================
# O job e a fila
# ======================================================================================
def analisar_processo(
    fabrica: sessionmaker, armazem: ArmazemPdf, processo_id: str, progresso: Optional[RegistroProgresso] = None
) -> None:
    """PENDENTE -> ANALISANDO -> CONCLUIDO | FALHOU. Não faz nada se outro worker já pegou o processo.

    `progresso` recebe a etapa em que a análise está. O fim (CONCLUIDO/FALHOU) só é anunciado DEPOIS do commit:
    quem acompanha lê o banco ao ser avisado e precisa encontrar o status final lá.
    """
    progresso = progresso or RegistroProgresso()  # sem ninguém acompanhando, vai para um registro descartável
    with fabrica() as db:
        # "Reivindica" com um UPDATE condicional: se dois workers pegarem o mesmo id, só um ganha.
        pegou = db.execute(
            update(Processo)
            .where(Processo.id == processo_id, Processo.status == StatusAnalise.PENDENTE.value)
            .values(status=StatusAnalise.ANALISANDO.value, iniciado_em=agora(), erro=None)
        ).rowcount
        db.commit()
    if not pegou:
        return

    def informar(etapa: str, atual: Optional[int] = None, total: Optional[int] = None) -> None:
        progresso.atualizar(processo_id, etapa, atual, total)

    informar(STAGE_EXTRACT)  # já com a análise reivindicada: a falha de uma execução anterior deixa de valer
    erro, resultado = None, None
    try:
        resultado = processar_pdf(armazem.caminho(processo_id), informar)
    except ErroRibeiro as falha:
        erro = mensagem_do_erro(falha)
    except Exception:
        registro.exception("Falha inesperada ao analisar o processo %s", processo_id)
        erro = MENSAGEM_ERRO_INESPERADO

    if resultado is not None:
        informar(STAGE_FINALIZE)
    if not gravar_resultado(fabrica, processo_id, resultado, erro):  # fase 6: grava o resultado (ou a falha) e fecha o processo
        progresso.descartar(processo_id)  # o usuário apagou enquanto analisávamos
        return

    if resultado is None:
        progresso.falhar(processo_id)  # guarda em que etapa parou, para a tela dizer onde falhou
    else:
        progresso.descartar(processo_id)


class FilaAnalise:
    def __init__(
        self, fabrica: sessionmaker, armazem: ArmazemPdf, workers: int = 2, progresso: Optional[RegistroProgresso] = None
    ):
        self._fabrica = fabrica
        self._armazem = armazem
        self.progresso = progresso or RegistroProgresso()  # em que etapa está cada análise em andamento
        self._executor = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="analise")

    def enfileirar(self, processo_id: str) -> None:
        self._executor.submit(self._rodar, processo_id)

    def _rodar(self, processo_id: str) -> None:
        try:
            analisar_processo(self._fabrica, self._armazem, processo_id, self.progresso)
        except Exception:  # a thread não pode morrer calada: o processo ficaria preso em ANALISANDO
            registro_fila.exception("Falha ao executar a análise de %s", processo_id)

    def recuperar(self) -> int:
        """Na subida: o que estava ANALISANDO ficou pela metade (o processo caiu); volta para a fila junto com os PENDENTES."""
        with self._fabrica() as db:
            db.execute(
                update(Processo)
                .where(Processo.status == StatusAnalise.ANALISANDO.value)
                .values(status=StatusAnalise.PENDENTE.value)
            )
            db.commit()
            ids = list(db.scalars(select(Processo.id).where(Processo.status == StatusAnalise.PENDENTE.value)))
        for id_ in ids:
            self.enfileirar(id_)
        if ids:
            registro_fila.info("%d análise(s) pendente(s) devolvida(s) à fila", len(ids))
        return len(ids)

    def encerrar(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class FilaSincrona(FilaAnalise):
    """Analisa dentro da chamada: testes e depuração (RIBEIRO_FILA_SINCRONA=true)."""

    def __init__(self, fabrica: sessionmaker, armazem: ArmazemPdf, progresso: Optional[RegistroProgresso] = None):
        self._fabrica = fabrica
        self._armazem = armazem
        self.progresso = progresso or RegistroProgresso()

    def enfileirar(self, processo_id: str) -> None:
        self._rodar(processo_id)

    def encerrar(self) -> None:
        pass


# ======================================================================================
# Dependências do FastAPI e o andamento ao vivo (SSE)
# ======================================================================================
def obter_armazem(request: Request) -> ArmazemPdf:
    return request.app.state.armazem


def obter_fila(request: Request) -> FilaAnalise:
    return request.app.state.fila


def obter_progresso(request: Request) -> RegistroProgresso:
    return request.app.state.fila.progresso


Armazem = Annotated[ArmazemPdf, Depends(obter_armazem)]
Fila = Annotated[FilaAnalise, Depends(obter_fila)]
Andamento = Annotated[RegistroProgresso, Depends(obter_progresso)]

router = APIRouter(prefix="/api/processos", tags=["pipeline"])


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


@router.get(
    "/{processo_id}/eventos",
    response_class=StreamingResponse,
    summary="Acompanha a análise ao vivo (Server-Sent Events); o resultado em si vem de GET /{processo_id}",
)
def acompanhar(processo_id: str, request: Request, usuario: UsuarioLogado, db: Sessao, registro: Andamento, config: Config):
    obter_do_usuario(db, usuario, processo_id)  # 404 para quem não é o dono, como nas demais rotas
    db.close()  # a transmissão dura segundos: não segura uma conexão do banco esse tempo todo
    return StreamingResponse(
        _transmitir(request.app.state.fabrica, registro, processo_id, config.sse_duracao_maxima),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},  # sem cache e sem buffer em proxy (nginx)
    )
