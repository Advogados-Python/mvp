import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..nucleo.banco import Base, DataHoraUTC, agora


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

    # Campos copiados do resultado para poder filtrar/ordenar no banco.
    numero_processo: Mapped[Optional[str]] = mapped_column(String(40), index=True, default=None)
    tribunal: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    fase: Mapped[Optional[str]] = mapped_column(String(40), default=None)
    divida_paga: Mapped[Optional[str]] = mapped_column(String(20), index=True, default=None)

    # Resultado completo do leitor (partes, advogados, avisos, evidências...). Ver analise.montar_resultado.
    resultado: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
