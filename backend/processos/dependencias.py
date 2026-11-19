from typing import Annotated

from fastapi import Depends, Request

from .armazem import ArmazemPdf
from .fila import FilaAnalise
from .progresso import RegistroProgresso


def obter_armazem(request: Request) -> ArmazemPdf:
    return request.app.state.armazem


def obter_fila(request: Request) -> FilaAnalise:
    return request.app.state.fila


def obter_progresso(request: Request) -> RegistroProgresso:
    return request.app.state.fila.progresso


Armazem = Annotated[ArmazemPdf, Depends(obter_armazem)]
Fila = Annotated[FilaAnalise, Depends(obter_fila)]
Progresso = Annotated[RegistroProgresso, Depends(obter_progresso)]
