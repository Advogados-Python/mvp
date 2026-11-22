from typing import Optional

from pydantic import BaseModel, ConfigDict


class ParteSaida(BaseModel):
    nome: str
    papel: str


class IdentifyOut(BaseModel):
    """A Identificacao do processo: o que foi achado nos autos (o que não foi achado vem vazio)."""

    model_config = ConfigDict(from_attributes=True)  # lê direto da linha da tabela `identificacoes`

    numero_processo: Optional[str] = None
    tribunal: Optional[str] = None
    classe: Optional[str] = None
    orgao_julgador: Optional[str] = None
    valor_causa: Optional[str] = None
    valor_requisitado: Optional[str] = None
    data_emissao_pdf: Optional[str] = None
    partes: list[ParteSaida] = []
    advogados: list[str] = []
    oabs: list[str] = []
    juiz: Optional[str] = None
