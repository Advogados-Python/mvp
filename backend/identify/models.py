"""As classes da fase 3: o que foi identificado no processo, e a tabela `identificacoes`."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, DataHoraUTC, agora

STAGE = "IDENTIFICANDO"  # o código que a API de andamento informa enquanto esta fase roda


@dataclass
class Parte:
    """Uma parte do processo, como aparece na capa dos autos."""
    nome: str          # o nome, como está nos autos
    papel: str         # AUTOR, RÉU, EXEQUENTE, EXECUTADO...


@dataclass
class Identificacao:
    """Os dados que identificam o processo, extraídos do texto. O que não foi achado fica vazio (e o aviso diz)."""
    numero_processo: Optional[str] = None
    tribunal: Optional[str] = None           # sigla deduzida do número (ex.: TRF1, TJSP)
    classe: Optional[str] = None
    orgao_julgador: Optional[str] = None
    valor_causa: Optional[str] = None
    valor_requisitado: Optional[str] = None
    data_emissao_pdf: Optional[str] = None   # a "posição" do processo: a data em que o PDF foi gerado
    partes: list = field(default_factory=list)       # list[Parte]
    advogados: list = field(default_factory=list)    # nomes
    oabs: list = field(default_factory=list)         # ["OAB/GO 12345 (30x)", ...] as mais citadas
    juiz: Optional[str] = None
    avisos: list = field(default_factory=list)       # ex.: número do processo não encontrado


class IdentificacaoGravada(Base):
    """A tabela `identificacoes` (fase 3): os dados que identificam o processo, uma linha por processo."""

    __tablename__ = "identificacoes"

    processo_id: Mapped[str] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), primary_key=True)
    numero_processo: Mapped[Optional[str]] = mapped_column(String(40), index=True, default=None)
    tribunal: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    classe: Mapped[Optional[str]] = mapped_column(Text, default=None)
    orgao_julgador: Mapped[Optional[str]] = mapped_column(Text, default=None)
    valor_causa: Mapped[Optional[str]] = mapped_column(Text, default=None)
    valor_requisitado: Mapped[Optional[str]] = mapped_column(Text, default=None)
    data_emissao_pdf: Mapped[Optional[str]] = mapped_column(Text, default=None)
    partes: Mapped[list] = mapped_column(JSON, default=list)       # [{"nome": ..., "papel": ...}]
    advogados: Mapped[list] = mapped_column(JSON, default=list)    # nomes
    oabs: Mapped[list] = mapped_column(JSON, default=list)         # ["OAB/GO 12345 (30x)", ...]
    juiz: Mapped[Optional[str]] = mapped_column(Text, default=None)
    gravada_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora)
