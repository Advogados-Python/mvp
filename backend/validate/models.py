"""As classes da fase 5: a conclusão, a escada do crédito que ela usa, e a tabela `conclusoes`."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, DataHoraUTC, agora

STAGE = "VALIDANDO"  # o código que a API de andamento informa enquanto esta fase roda


class RespostaDividaPaga(str, Enum):
    """A resposta objetiva à pergunta "a dívida já foi paga?" que cada fase do crédito dá quando é a fase final."""

    SIM = "SIM"
    PROVAVEL = "PROVAVEL"
    NAO = "NAO"
    SEM_INFORMACAO = "SEM_INFORMACAO"


@dataclass(frozen=True)
class Fase:
    """Um degrau da escada do crédito (sentença … quitado). A fase do processo é a MAIS ALTA que tiver evidência confiável."""
    codigo: str                          # a chave que as evidências e o banco guardam (ex.: "REQUISICAO")
    rotulo: str                          # nome curto para telas e chips
    descricao: str                       # o que significa, numa frase
    ordem: int                           # 0 = ponto de partida (sem informação) ... quanto maior, mais perto de "dívida paga"
    divida_paga: RespostaDividaPaga      # o que esta fase responde quando é a fase final do processo


@dataclass
class Conclusao:
    """O que a validação conclui das evidências: em que fase do crédito o processo está e se a dívida já foi paga."""
    fase: str                            # o código da fase final, ex.: "REQUISICAO"
    fase_descricao: str                  # o que essa fase significa, numa frase
    divida_paga: str                     # SIM, PROVAVEL, NAO ou SEM_INFORMACAO
    avisos: list = field(default_factory=list)   # o que o advogado precisa ler: alertas e menções ignoradas


class ConclusaoGravada(Base):
    """A tabela `conclusoes` (fase 5): a fase do crédito e a resposta sobre a dívida, uma linha por processo."""

    __tablename__ = "conclusoes"

    processo_id: Mapped[str] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), primary_key=True)
    fase: Mapped[str] = mapped_column(String(40))                         # o código do degrau final, ex.: "REQUISICAO"
    fase_descricao: Mapped[str] = mapped_column(Text)
    divida_paga: Mapped[str] = mapped_column(String(20), index=True)      # SIM, PROVAVEL, NAO ou SEM_INFORMACAO
    gravada_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora)
