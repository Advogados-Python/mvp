"""As classes da fase 2: o texto das páginas, os erros de leitura e a tabela `leituras`."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, DataHoraUTC, agora

STAGE = "LENDO_PDF"                      # o código que a API de andamento informa enquanto esta fase roda
MIN_CARACTERES_PAGINA = 30               # página com menos texto que isso é tratada como "sem texto" (scan)
PERCENTUAL_SEM_TEXTO_PARA_ALERTA = 0.5   # se >= 50% das páginas estão sem texto, avisa que precisa de OCR


class ErroRibeiro(Exception):
    """Base de todos os erros do projeto (permite um único `except ErroRibeiro` no main)."""
    def __init__(self, mensagem):
        self.__msg = mensagem

    def __str__(self):
        return f"{type(self).__name__} ({self.__msg})"


# Leitura de PDF
class ErroPdfNaoEncontrado(ErroRibeiro):
    """O caminho informado não existe ou não é um arquivo."""


class ErroPdfProtegido(ErroRibeiro):
    """O PDF está protegido por senha."""


class ErroLeituraPdf(ErroRibeiro):
    """O arquivo não pôde ser aberto como PDF (corrompido, formato inválido...)."""


@dataclass
class Pagina:
    """Uma página do PDF já convertida em texto."""
    numero: int                              # 1 = primeira página
    texto: str
    documento_id: Optional[str] = None       # PJe: id do documento a que a página pertence (preenchido na fase 3)
    tipo_documento: Optional[str] = None     # PJe: "Sentença Tipo A", "Petição inicial"... (idem)
    assinante: Optional[str] = None          # PJe: quem assinou o documento (idem)

    @property
    def sem_texto(self) -> bool:
        return len(self.texto.strip()) < MIN_CARACTERES_PAGINA


@dataclass
class Leitura:
    """O que a extração entrega: as páginas, quantas não têm texto e o aviso de qualidade da leitura, se houver."""
    paginas: list = field(default_factory=list)       # list[Pagina]
    paginas_sem_texto: int = 0                        # só imagem (scan): não puderam ser lidas
    avisos: list = field(default_factory=list)        # list[str]

    @property
    def total_paginas(self) -> int:
        return len(self.paginas)


class LeituraGravada(Base):
    """A tabela `leituras` (fase 2): o que foi lido do PDF, uma linha por processo. O texto das páginas não é guardado, só a contagem."""

    __tablename__ = "leituras"

    processo_id: Mapped[str] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), primary_key=True)
    total_paginas: Mapped[int]
    paginas_sem_texto: Mapped[int]                   # só imagem (scan): não puderam ser lidas
    gravada_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora)
