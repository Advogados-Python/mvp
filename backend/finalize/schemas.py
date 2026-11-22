from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from ..identify.schemas import ParteSaida
from ..receive.models import StatusAnalise
from ..search.schemas import EvidenciaSaida
from ..validate.schemas import DividaPaga


class ProgressoSaida(BaseModel):
    """Onde a análise está. Só existe de verdade: `atual`/`total` (páginas) vêm nas etapas que andam página a página."""

    etapa: str                      # LENDO_PDF | IDENTIFICANDO | BUSCANDO_TERMOS | VALIDANDO | FINALIZANDO
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


class FinalizeOut(BaseModel):
    """O que a finalização gravou: o fim do processo (`processos`) e o fechamento (`resultados`). Existe em qualquer status: FALHOU traz o motivo."""

    status: str
    concluido_em: Optional[datetime] = None
    erro: Optional[str] = None  # o motivo da falha, em linguagem do usuário (só quando FALHOU)
    numero_processo: Optional[str] = None
    tribunal: Optional[str] = None
    fase: Optional[str] = None
    divida_paga: Optional[str] = None
    resultado_gravado: bool  # o fechamento (tabela `resultados`) está no banco
