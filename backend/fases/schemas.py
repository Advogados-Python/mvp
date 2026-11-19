from typing import Literal, Optional

from pydantic import BaseModel

DividaPaga = Literal["SIM", "PROVAVEL", "NAO", "SEM_INFORMACAO"]
SituacaoNaEscadaSaida = Literal["ALCANCADA", "ATUAL", "NAO_ALCANCADA"]


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


class TermoSaida(BaseModel):
    nome: str
    padrao: str  # a expressão regular, em texto


class ModuloDetalhe(BaseModel):
    """O que um módulo é e como o sistema o reconhece. Fora da escada (o alerta) `ordem` e o que diz da dívida ficam vazios."""

    codigo: str
    rotulo: str
    descricao: str
    ordem: Optional[int] = None
    divida_paga: Optional[DividaPaga] = None
    significado: Optional[str] = None
    acao: Optional[str] = None
    termos: list[TermoSaida]


class EvidenciaSaida(BaseModel):
    fase: str
    termo: str
    pagina: int
    trecho: str
    tipo_documento: Optional[str] = None
    hipotetico: bool
    origem_confiavel: bool
    conta: bool  # só evidência que não é hipotética e vem do juízo decide a fase


class FaseNoProcessoSaida(BaseModel):
    """Como um processo se relaciona com um módulo. `situacao` é a da escada; fora dela (o alerta) fica vazia."""

    codigo: str
    rotulo: str
    situacao: Optional[SituacaoNaEscadaSaida] = None
    evidencias: list[EvidenciaSaida]
    evidencia_principal: Optional[EvidenciaSaida] = None  # só na fase atual
    total_evidencias: int
    evidencias_que_contam: int
