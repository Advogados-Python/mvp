"""Fila de análises em segundo plano: threads do próprio processo + o estado gravado no banco.

Por que assim: a análise de um PDF leva segundos e o resultado fica no banco, então não precisamos de
Redis/Celery. A fila é só um conjunto de threads; quem manda é a coluna `status`. Se o servidor cair no meio,
ao subir `recuperar()` devolve os processos "ANALISANDO" para a fila e nada se perde.

Limite: a fila vive na memória de UM processo. Rode o servidor com um único worker do uvicorn.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from .analise import analisar_processo
from .armazem import ArmazemPdf
from .modelos import Processo, StatusAnalise
from .progresso import RegistroProgresso

registro = logging.getLogger("ribeiro.fila")


class FilaAnalise:
    def __init__(
        self, fabrica: sessionmaker, armazem: ArmazemPdf, workers: int = 2, progresso: Optional[RegistroProgresso] = None
    ):
        self._fabrica = fabrica
        self._armazem = armazem
        self.progresso = progresso or RegistroProgresso()  # em que etapa está cada análise em andamento
        self._executor = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="analise")

    def enfileirar(self, processo_id: str) -> None:
        self._executor.submit(self._rodar, processo_id)

    def _rodar(self, processo_id: str) -> None:
        try:
            analisar_processo(self._fabrica, self._armazem, processo_id, self.progresso)
        except Exception:  # a thread não pode morrer calada: o processo ficaria preso em ANALISANDO
            registro.exception("Falha ao executar a análise de %s", processo_id)

    def recuperar(self) -> int:
        """Na subida: o que estava ANALISANDO ficou pela metade (o processo caiu); volta para a fila junto com os PENDENTES."""
        with self._fabrica() as db:
            db.execute(
                update(Processo)
                .where(Processo.status == StatusAnalise.ANALISANDO.value)
                .values(status=StatusAnalise.PENDENTE.value)
            )
            db.commit()
            ids = list(db.scalars(select(Processo.id).where(Processo.status == StatusAnalise.PENDENTE.value)))
        for id_ in ids:
            self.enfileirar(id_)
        if ids:
            registro.info("%d análise(s) pendente(s) devolvida(s) à fila", len(ids))
        return len(ids)

    def encerrar(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class FilaSincrona(FilaAnalise):
    """Analisa dentro da chamada: testes e depuração (RIBEIRO_FILA_SINCRONA=true)."""

    def __init__(self, fabrica: sessionmaker, armazem: ArmazemPdf, progresso: Optional[RegistroProgresso] = None):
        self._fabrica = fabrica
        self._armazem = armazem
        self.progresso = progresso or RegistroProgresso()

    def enfileirar(self, processo_id: str) -> None:
        self._rodar(processo_id)

    def encerrar(self) -> None:
        pass
