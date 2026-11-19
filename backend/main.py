"""Ponto de entrada da API.

    uvicorn backend.main:app --reload          # http://127.0.0.1:8000  (documentação em /docs)

Rode com UM worker do uvicorn: a fila de análises vive na memória do processo (veja processos/fila.py).

Mapa do pacote (um papel por pasta; dentro de cada uma, os mesmos nomes de arquivo do leitor):
    nucleo/         configuração, banco, dependências comuns, /api/saude
    leitor/         o pipeline que lê o PDF (regex + dicionário de termos); usado também pelo CLI main.py da raiz
    fases/          a escada do crédito: cada fase é um módulo (sentenca/, requisicao/, quitado/...) com as suas classes e a sua API
    usuarios/       tabela de usuários e administração
    autenticacao/   login, tokens JWT, links assinados, proteção das rotas
    processos/      upload, armazenamento, fila de análise e resultados
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .autenticacao import rotas as rotas_auth
from .autenticacao.classes import LimitadorLogin
from .fases import rotas as rotas_fases
from .nucleo import banco, rotas as rotas_nucleo
from .nucleo.config import Configuracoes, obter_configuracoes
from .nucleo.validacao import tratar_erro_de_validacao
from .processos import modelos as _modelos_processos  # noqa: F401  (registra a tabela para o create_all)
from .processos import rotas as rotas_processos
from .processos.armazem import ArmazemPdf
from .processos.fila import FilaAnalise, FilaSincrona
from .usuarios import modelos as _modelos_usuarios  # noqa: F401
from .usuarios import rotas as rotas_usuarios
from .usuarios.funcoes import garantir_administrador_inicial

registro = logging.getLogger("ribeiro.main")


def criar_app(config: Optional[Configuracoes] = None) -> FastAPI:
    config = config or obter_configuracoes()
    segredo = config.segredo_jwt()  # em produção, falha aqui (na subida) se não houver segredo

    motor = banco.criar_motor(config.url_do_banco)
    fabrica = banco.criar_fabrica_sessoes(motor)
    armazem = ArmazemPdf(config.pasta_dados / "pdfs", config.max_pdf_bytes)
    fila = FilaSincrona(fabrica, armazem) if config.fila_sincrona else FilaAnalise(fabrica, armazem, config.workers_analise)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI):
        config.pasta_dados.mkdir(parents=True, exist_ok=True)
        # create_all cria o que falta, mas não altera tabelas existentes: mudanças de esquema pedem Alembic.
        banco.Base.metadata.create_all(motor)
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
    for modulo in (rotas_nucleo, rotas_fases, rotas_auth, rotas_usuarios, rotas_processos):
        app.include_router(modulo.roteador)
    return app


app = criar_app()
