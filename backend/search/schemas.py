from typing import Optional

from pydantic import BaseModel, ConfigDict


class EvidenciaSaida(BaseModel):
    """Uma Evidencia como a API a entrega (veja search/models.py)."""

    model_config = ConfigDict(from_attributes=True)  # lê direto da linha da tabela `evidencias`

    fase: str
    termo: str
    pagina: int
    trecho: str
    tipo_documento: Optional[str] = None
    hipotetico: bool
    origem_confiavel: bool
    conta: bool  # só evidência que não é hipotética e vem do juízo decide a fase


class SearchOut(BaseModel):
    """O que a busca de termos reuniu: todas as Evidencia, contadas por fase do crédito (ou ALERTA)."""

    total_evidencias: int
    evidencias_que_contam: int
    evidencias_ignoradas: int  # hipotéticas ou de peça da parte: aparecem, mas não decidem a fase
    por_fase: dict[str, int]
    evidencias: list[EvidenciaSaida]
