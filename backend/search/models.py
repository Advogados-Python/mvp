"""As classes da fase 4: o que a busca de termos reúne, e a tabela `evidencias`."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base

STAGE = "BUSCANDO_TERMOS"  # o código que a API de andamento informa enquanto esta fase roda


@dataclass
class Evidencia:
    """Um trecho do PDF que casou com um termo do dicionário. É a 'prova' mostrada ao advogado."""
    fase: str                                # a fase do crédito (ou "ALERTA") a que o termo pertence, ex.: "REQUISICAO"
    termo: str                               # nome do termo (ex.: "oficio_requisitorio")
    pagina: int
    trecho: str
    tipo_documento: Optional[str] = None
    hipotetico: bool = False                 # frase condicional/futura/negada ("aguarde-se o pagamento")
    origem_confiavel: bool = True            # False = veio de peça da parte (petição, manifestação...)

    @property
    def conta(self) -> bool:
        """Só evidências não hipotéticas e vindas do juízo decidem a fase."""
        return not self.hipotetico and self.origem_confiavel


class EvidenciaGravada(Base):
    """A tabela `evidencias` (fase 4): um achado do dicionário, uma linha por evidência, na ordem em que foram achadas."""

    __tablename__ = "evidencias"
    __table_args__ = (UniqueConstraint("processo_id", "ordem", name="uq_evidencia_processo_ordem"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[str] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"))
    ordem: Mapped[int]                                      # 0 = a primeira achada
    fase: Mapped[str] = mapped_column(String(40))           # degrau do crédito do termo, ou "ALERTA"
    termo: Mapped[str] = mapped_column(String(80))
    pagina: Mapped[int]
    trecho: Mapped[str] = mapped_column(Text)
    tipo_documento: Mapped[Optional[str]] = mapped_column(Text, default=None)
    hipotetico: Mapped[bool] = mapped_column(default=False)
    origem_confiavel: Mapped[bool] = mapped_column(default=True)

    @property
    def conta(self) -> bool:
        """Só evidências não hipotéticas e vindas do juízo decidem a fase."""
        return not self.hipotetico and self.origem_confiavel
