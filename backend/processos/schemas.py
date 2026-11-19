from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from ..fases.schemas import DividaPaga, EvidenciaSaida  # a evidência é o que prova a fase: mora com as fases
from .modelos import StatusAnalise


class ParteSaida(BaseModel):
    nome: str
    papel: str


class ProgressoSaida(BaseModel):
    """Onde a análise está. Só existe de verdade: `atual`/`total` (páginas) vêm nas etapas que andam página a página."""

    etapa: str                      # LENDO_PDF | IDENTIFICANDO | ANALISANDO_FASES | VALIDANDO | FINALIZANDO
    atual: Optional[int] = None
    total: Optional[int] = None
    falhou: bool = False            # status FALHOU: a análise parou nesta etapa


class ProcessoResumo(BaseModel):
    """Versão leve (listas). Enquanto a análise não termina, os campos do resultado vêm vazios."""

    id: str
    arquivo: str
    tamanho_bytes: int
    criado_em: datetime
    concluido_em: Optional[datetime] = None
    status: StatusAnalise
    erro: Optional[str] = None
    # Em ANALISANDO: a etapa atual. Em FALHOU: onde parou (some se o servidor reiniciou). Nos demais status: None.
    progresso: Optional[ProgressoSaida] = None

    total_paginas: Optional[int] = None
    paginas_sem_texto: Optional[int] = None
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
    fase: Optional[str] = None
    fase_descricao: Optional[str] = None
    divida_paga: Optional[DividaPaga] = None
    avisos: list[str] = []
    evidencia_principal: Optional[EvidenciaSaida] = None
    total_evidencias: int = 0
    evidencias_que_contam: int = 0


class ProcessoDetalhe(ProcessoResumo):
    evidencias: list[EvidenciaSaida] = []


class ListaProcessos(BaseModel):
    processos: list[ProcessoResumo]
    total: int


class FalhaEnvio(BaseModel):
    arquivo: str
    erro: str


class RespostaEnvio(BaseModel):
    processos: list[ProcessoResumo]  # aceitos; a análise segue em segundo plano
    falhas: list[FalhaEnvio]         # recusados na hora (vazio, grande demais, não é PDF)


class LinkPdf(BaseModel):
    url: str            # caminho relativo à API, com a assinatura
    expira_em: datetime
