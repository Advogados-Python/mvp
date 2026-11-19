"""Dependências do FastAPI que não pertencem a nenhum domínio: configuração e sessão do banco."""

from typing import Annotated, Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import Configuracoes


def obter_config(request: Request) -> Configuracoes:
    return request.app.state.config


def obter_sessao(request: Request) -> Iterator[Session]:
    """Uma Session por requisição, fechada ao final."""
    with request.app.state.fabrica() as sessao:
        yield sessao


Sessao = Annotated[Session, Depends(obter_sessao)]
Config = Annotated[Configuracoes, Depends(obter_config)]
