"""Progresso das análises em andamento: em que etapa cada PDF está (e, quando faz sentido, quantas páginas já foram).

Fica só na memória, de propósito: a fila também vive na memória de UM processo (veja fila.py) e, se o servidor cair,
`FilaAnalise.recuperar()` devolve tudo para PENDENTE e a análise recomeça do zero. Gravar isto no banco exigiria
uma coluna nova (e o create_all não altera tabelas existentes) para guardar algo que só vale por alguns segundos.

Regra de ouro: só o que o pipeline de fato informou entra aqui. Nada é estimado nem simulado.
O banco continua sendo a verdade sobre o STATUS; este registro só diz "onde" a análise está enquanto ela roda.
"""

import asyncio
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

from ..leitor.constantes import ETAPA_ANALISANDO_FASES, ETAPA_IDENTIFICANDO, ETAPA_LENDO_PDF, ETAPA_VALIDANDO

ETAPA_FINALIZANDO = "FINALIZANDO"  # gravar o resultado no banco (analise.py); o leitor já terminou

# Ordem real de execução. O front espelha esta lista (frontend/src/lib/tipos.ts, ETAPAS): mantenha os dois lados em sincronia.
ETAPAS = (ETAPA_LENDO_PDF, ETAPA_IDENTIFICANDO, ETAPA_ANALISANDO_FASES, ETAPA_VALIDANDO, ETAPA_FINALIZANDO)

MAX_REGISTROS = 1000  # teto de segurança: entradas de falha ficam até alguém reanalisar ou apagar


@dataclass(frozen=True)
class Progresso:
    etapa: str
    atual: Optional[int] = None  # páginas já processadas na etapa (só nas etapas que andam página a página)
    total: Optional[int] = None
    falhou: bool = False         # a análise parou nesta etapa


class RegistroProgresso:
    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._estado: dict[str, Progresso] = {}
        self._ouvintes: dict[str, set] = {}

    # ---- quem analisa (threads da fila)
    def atualizar(self, processo_id: str, etapa: str, atual: Optional[int] = None, total: Optional[int] = None) -> None:
        with self._trava:
            self._estado.pop(processo_id, None)  # reinserir no fim: o mais antigo é o primeiro a sair do teto
            self._estado[processo_id] = Progresso(etapa, atual, total)
            while len(self._estado) > MAX_REGISTROS:
                self._estado.pop(next(iter(self._estado)))
        self._avisar(processo_id)

    def falhar(self, processo_id: str) -> None:
        """A análise parou: guarda em que etapa (para a tela dizer onde falhou) até reanalisarem ou apagarem."""
        with self._trava:
            atual = self._estado.get(processo_id)
            if atual is None:
                return
            self._estado[processo_id] = Progresso(atual.etapa, atual.atual, atual.total, falhou=True)
        self._avisar(processo_id)

    def descartar(self, processo_id: str) -> None:
        """Terminou (ou o processo foi apagado): não há mais o que acompanhar."""
        with self._trava:
            existia = self._estado.pop(processo_id, None) is not None
        if existia:
            self._avisar(processo_id)

    # ---- quem consulta
    def obter(self, processo_id: str) -> Optional[Progresso]:
        with self._trava:
            return self._estado.get(processo_id)

    def visivel(self, processo_id: str, status: str) -> Optional[Progresso]:
        """O progresso que vale mostrar para este status: em ANALISANDO, o andamento; em FALHOU, onde parou.

        Qualquer outro caso é None, e isso também esconde sobras de uma execução anterior (por exemplo, a falha
        antiga de um processo que acabou de ser reenviado para a fila).
        """
        progresso = self.obter(processo_id)
        if progresso is None:
            return None
        if status == "ANALISANDO" and not progresso.falhou:
            return progresso
        if status == "FALHOU" and progresso.falhou:
            return progresso
        return None

    @contextmanager
    def assinar(self, processo_id: str) -> Iterator[asyncio.Event]:
        """Para código assíncrono (o SSE): devolve um Event que é acionado a cada mudança deste processo.

        Chame de dentro do loop de eventos. As threads da fila acionam o Event com call_soon_threadsafe.
        """
        ouvinte = (asyncio.get_running_loop(), asyncio.Event())
        with self._trava:
            self._ouvintes.setdefault(processo_id, set()).add(ouvinte)
        try:
            yield ouvinte[1]
        finally:
            with self._trava:
                conjunto = self._ouvintes.get(processo_id)
                if conjunto is not None:
                    conjunto.discard(ouvinte)
                    if not conjunto:
                        del self._ouvintes[processo_id]

    def _avisar(self, processo_id: str) -> None:
        with self._trava:
            ouvintes = list(self._ouvintes.get(processo_id, ()))
        for loop, evento in ouvintes:
            try:
                loop.call_soon_threadsafe(evento.set)
            except RuntimeError:  # o loop já foi fechado (servidor encerrando)
                pass
