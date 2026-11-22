from datetime import datetime

from pydantic import BaseModel

from ..finalize.schemas import ProcessoResumo


class FalhaEnvio(BaseModel):
    arquivo: str
    erro: str


class RespostaEnvio(BaseModel):
    processos: list[ProcessoResumo]  # aceitos; a análise segue em segundo plano
    falhas: list[FalhaEnvio]         # recusados na hora (vazio, grande demais, não é PDF)


class LinkPdf(BaseModel):
    url: str            # caminho relativo à API, com a assinatura
    expira_em: datetime


class ReceiveOut(BaseModel):
    """O que o recebimento guardou do PDF. Existe para qualquer processo, em qualquer status."""

    arquivo: str
    tamanho_bytes: int
    recebido_em: datetime
    status: str  # onde o processo está agora (PENDENTE, ANALISANDO, CONCLUIDO ou FALHOU)
