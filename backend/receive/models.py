import enum
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, DataHoraUTC, agora


class StatusAnalise(str, enum.Enum):
    PENDENTE = "PENDENTE"        # na fila
    ANALISANDO = "ANALISANDO"    # uma thread está lendo o PDF
    CONCLUIDO = "CONCLUIDO"
    FALHOU = "FALHOU"

    @property
    def em_andamento(self) -> bool:
        return self in (StatusAnalise.PENDENTE, StatusAnalise.ANALISANDO)


def novo_id() -> str:
    return uuid.uuid4().hex


class Processo(Base):
    """Um PDF enviado. Cada processo pertence a um usuário e só ele o enxerga."""

    __tablename__ = "processos"
    __table_args__ = (
        UniqueConstraint("dono_id", "sha256", name="uq_processo_dono_sha256"),  # o mesmo PDF não duplica
        Index("ix_processos_dono_criado", "dono_id", "criado_em"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    dono_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    arquivo: Mapped[str] = mapped_column(String(255))  # nome original do upload
    sha256: Mapped[str] = mapped_column(String(64))
    tamanho_bytes: Mapped[int] = mapped_column(BigInteger)

    status: Mapped[str] = mapped_column(String(12), default=StatusAnalise.PENDENTE.value, index=True)
    erro: Mapped[Optional[str]] = mapped_column(Text, default=None)
    criado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora)
    iniciado_em: Mapped[Optional[datetime]] = mapped_column(DataHoraUTC, default=None)
    concluido_em: Mapped[Optional[datetime]] = mapped_column(DataHoraUTC, default=None)

    # O que cada fase de leitura produziu mora na tabela dela, ligada a este processo (1 linha por processo, menos as evidências).
    # Só existe com a análise CONCLUIDA; reiniciar a análise apaga tudo isto.
    leitura: Mapped[Optional["LeituraGravada"]] = relationship(uselist=False, cascade="all, delete-orphan")                    # 2 extract
    identificacao: Mapped[Optional["IdentificacaoGravada"]] = relationship(uselist=False, cascade="all, delete-orphan")        # 3 identify
    evidencias: Mapped[list["EvidenciaGravada"]] = relationship(cascade="all, delete-orphan", order_by="EvidenciaGravada.ordem")  # 4 search
    conclusao: Mapped[Optional["ConclusaoGravada"]] = relationship(uselist=False, cascade="all, delete-orphan")                # 5 validate
    resultado: Mapped[Optional["ResultadoGravado"]] = relationship(uselist=False, cascade="all, delete-orphan")                # 6 finalize


STAGE = "RECEBIDO"  # o recebimento não é uma "etapa" da API de andamento: é o status PENDENTE (o PDF chegou e espera a vez)


@dataclass(frozen=True)
class PdfRecebido:
    """O PDF que acabou de chegar, já gravado num arquivo temporário e conferido (é um PDF, não está vazio, cabe no limite)."""
    temporario: Path       # onde o PDF está até ser guardado com o id do processo
    sha256: str            # a impressão digital do conteúdo
    tamanho_bytes: int


class ErroEnvio(Exception):
    """Problema com o arquivo enviado (vazio, grande demais, não é PDF). A mensagem é mostrada ao usuário."""


# As tabelas das outras fases precisam estar registradas quando o mapeador resolve as relações de Processo.
# Elas só apontam para "processos.id" por texto, então este import no fim não faz volta.
from ..extract.models import LeituraGravada  # noqa: E402,F401
from ..finalize.models import ResultadoGravado  # noqa: E402,F401
from ..identify.models import IdentificacaoGravada  # noqa: E402,F401
from ..search.models import EvidenciaGravada  # noqa: E402,F401
from ..validate.models import ConclusaoGravada  # noqa: E402,F401
