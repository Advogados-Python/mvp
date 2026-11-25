"""Ponto de entrada da API.

    uvicorn backend.main:app --reload          # http://127.0.0.1:8000  (documentação em /docs)

Rode com UM worker do uvicorn: a fila de análises vive na memória do processo (veja pipeline.py).

O backend são as seis fases de leitura do documento, na ordem em que rodam, mais os usuários. Cada pasta é um módulo com as
suas classes (models.py), a sua lógica (logic.py) e a sua API (schemas.py + api.py):

    receive/     1  Documento recebido        guarda o PDF e registra o processo na fila      POST /api/processos...
    extract/     2  Extraindo conteúdo        o texto de cada página                          GET  /api/processos/{id}/extract
    identify/    3  Identificando o processo  número, tribunal, partes, juiz, valores         GET  /api/processos/{id}/identify
    search/      4  Buscando os termos        o dicionário: cada achado, com página e trecho   GET  /api/processos/{id}/search
    validate/    5  Validando evidências      a fase do crédito, "dívida paga?" e os avisos    GET  /api/fases e .../validate
    finalize/    6  Finalizando resultado     grava o resultado; a lista e o detalhe           GET  /api/processos e .../{id}
    ai_services/ 7  Camada de IA (opcional)   o modelo confere a fase lendo o texto sem o cabeçalho POST /api/ia/analise
    userauths/   usuários e login (e a CLI: python -m backend.userauths.cli)

    main.py      este arquivo: monta o app          config.py   o ambiente (variáveis RIBEIRO_*)       db.py   o banco
    pipeline.py  a esteira: encadeia as fases, a fila de threads e o andamento ao vivo (SSE)
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from . import db, pipeline
from .ai_services import api as ai_services_api
from .config import Configuracoes, obter_configuracoes
from .db import Sessao
from .extract import api as extract_api
from .finalize import api as finalize_api
from .finalize.logic import migrar_resultados_antigos
from .identify import api as identify_api
from .pipeline import FilaAnalise, FilaSincrona
from .receive import api as receive_api
from .receive import models as _modelos_processos  # noqa: F401  (registra as tabelas das seis fases para o create_all)
from .receive.store import ArmazemPdf
from .search import api as search_api
from .userauths import api as userauths_api
from .userauths import models as _modelos_usuarios  # noqa: F401
from .userauths.logic import garantir_administrador_inicial, tratar_erro_de_validacao
from .userauths.models import LimitadorLogin
from .validate import api as validate_api

registro = logging.getLogger("ribeiro.main")


def criar_app(config: Optional[Configuracoes] = None) -> FastAPI:
    config = config or obter_configuracoes()
    segredo = config.segredo_jwt()  # em produção, falha aqui (na subida) se não houver segredo

    motor = db.criar_motor(config.url_do_banco)
    fabrica = db.criar_fabrica_sessoes(motor)
    armazem = ArmazemPdf(config.pasta_dados / "pdfs", config.max_pdf_bytes)
    fila = FilaSincrona(fabrica, armazem) if config.fila_sincrona else FilaAnalise(fabrica, armazem, config.workers_analise)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI):
        config.pasta_dados.mkdir(parents=True, exist_ok=True)
        # create_all cria o que falta, mas não altera tabelas existentes: mudanças de esquema pedem Alembic.
        db.Base.metadata.create_all(motor)
        migrar_resultados_antigos(motor, fabrica)  # resultado que estava na coluna JSON de `processos` passa para as tabelas das fases
        garantir_administrador_inicial(fabrica, config)
        fila.recuperar()
        yield
        fila.encerrar()
        motor.dispose()

    app = FastAPI(title="Ribeiro e Souza - Leitor de Processos", version="0.2.0", lifespan=ciclo_de_vida)
    app.state.config = config
    app.state.segredo = segredo
    app.state.motor = motor
    app.state.fabrica = fabrica
    app.state.armazem = armazem
    app.state.fila = fila
    app.state.limitador = LimitadorLogin(config.login_max_tentativas, config.login_janela_segundos)

    app.add_exception_handler(RequestValidationError, tratar_erro_de_validacao)  # sem ecoar o valor enviado (senha)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origens_cors,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    # As seis fases de leitura, na ordem, mais a camada de IA, a esteira (andamento ao vivo) e os usuários.
    for roteador in (
        receive_api.router,
        extract_api.router,
        identify_api.router,
        search_api.router,
        validate_api.router,
        finalize_api.router,
        ai_services_api.router,
        pipeline.router,
        userauths_api.auth_router,
        userauths_api.users_router,
    ):
        app.include_router(roteador)

    @app.get("/api/saude", tags=["geral"], summary="Confere se a API e o banco estão no ar (usado pelo healthcheck)")
    def saude(sessao: Sessao):
        try:
            sessao.execute(text("SELECT 1"))
        except Exception:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Banco de dados indisponível.") from None
        return {"status": "ok"}

    return app


app = criar_app()
