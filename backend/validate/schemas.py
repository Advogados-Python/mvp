from typing import Literal, Optional

from pydantic import BaseModel

from ..search.schemas import EvidenciaSaida

DividaPaga = Literal["SIM", "PROVAVEL", "NAO", "SEM_INFORMACAO"]


class FaseSaida(BaseModel):
    codigo: str
    rotulo: str
    descricao: str
    ordem: int


class SignificadoDivida(BaseModel):
    valor: DividaPaga
    significado: str
    acao: str


class FasesSaida(BaseModel):
    fases: list[FaseSaida]
    divida_paga: list[SignificadoDivida]


class ValidateOut(BaseModel):
    """A Conclusao da validação para um processo: a fase do crédito, a resposta sobre a dívida e o que ler antes de confiar."""

    fase: str
    fase_descricao: str
    divida_paga: DividaPaga
    avisos: list[str]
    evidencia_principal: Optional[EvidenciaSaida] = None  # a primeira evidência que conta da fase final
    evidencias_que_contam: int
    evidencias_ignoradas: int
