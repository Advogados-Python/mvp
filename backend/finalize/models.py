"""As classes da fase 6: o resultado completo de um PDF, reunido, e a tabela `resultados`."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, DataHoraUTC, agora
from ..search.models import Evidencia, EvidenciaGravada
from ..validate.ladder import DESCRICAO_FASE, DIVIDA_PAGA_SEM_INFO

STAGE = "FINALIZANDO"  # o código que a API de andamento informa enquanto esta fase roda


@dataclass
class ResultadoProcesso:
    """Tudo o que o sistema descobriu sobre um PDF."""
    arquivo: str
    total_paginas: int = 0
    paginas_sem_texto: int = 0
    numero_processo: Optional[str] = None
    tribunal: Optional[str] = None
    classe: Optional[str] = None
    orgao_julgador: Optional[str] = None
    valor_causa: Optional[str] = None
    valor_requisitado: Optional[str] = None
    data_emissao_pdf: Optional[str] = None   # "posição" do processo quando o PDF foi gerado
    partes: list = field(default_factory=list)       # [{"nome": ..., "papel": ...}]
    advogados: list = field(default_factory=list)    # nomes
    oabs: list = field(default_factory=list)         # ["OAB/GO 12345", ...] mais frequentes
    juiz: Optional[str] = None
    fase: str = "SEM_INFORMACAO"
    fase_descricao: str = DESCRICAO_FASE["SEM_INFORMACAO"]
    divida_paga: str = DIVIDA_PAGA_SEM_INFO
    avisos: list = field(default_factory=list)
    evidencias: list = field(default_factory=list)   # list[Evidencia]

    def evidencia_principal(self) -> Optional[Evidencia]:
        """A evidência (que conta) da fase final: o que o advogado deve conferir primeiro."""
        for ev in self.evidencias:
            if ev.conta and ev.fase == self.fase:
                return ev
        return None

    def para_dict(self) -> dict:
        return asdict(self)


class ResultadoGravado(Base):
    """A tabela `resultados` (fase 6): o fechamento da análise, uma linha por processo concluído.

    Guarda o que só existe depois de juntar as fases: os avisos de todas elas, as contagens de evidências (para a lista
    não precisar carregar cada evidência) e qual evidência é a principal. O resto do resultado mora na tabela de cada fase.
    """

    __tablename__ = "resultados"

    processo_id: Mapped[str] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), primary_key=True)
    avisos: Mapped[list] = mapped_column(JSON, default=list)       # os avisos das fases 2, 3 e 5, juntos
    total_evidencias: Mapped[int] = mapped_column(default=0)
    evidencias_que_contam: Mapped[int] = mapped_column(default=0)
    evidencia_principal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("evidencias.id", ondelete="SET NULL"), default=None)
    gravado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora)

    evidencia_principal: Mapped[Optional[EvidenciaGravada]] = relationship(foreign_keys=[evidencia_principal_id])
