import threading
import time
from collections import defaultdict, deque


class LimitadorLogin:
    """Bloqueia uma chave (IP + e-mail) após N falhas dentro de uma janela. Fica na memória do processo:
    reiniciar zera, e com vários processos cada um conta o seu. Barra tentativa em massa, não é um WAF."""

    def __init__(self, max_tentativas: int, janela_segundos: int):
        self.max_tentativas = max_tentativas
        self.janela = janela_segundos
        self._falhas: dict = defaultdict(deque)
        self._trava = threading.Lock()

    def _limpar(self, chave: str, agora: float) -> deque:
        fila = self._falhas[chave]
        while fila and agora - fila[0] > self.janela:
            fila.popleft()
        return fila

    def segundos_de_bloqueio(self, chave: str) -> int:
        """0 = liberado; senão, quantos segundos faltam."""
        with self._trava:
            agora = time.monotonic()
            fila = self._limpar(chave, agora)
            if len(fila) < self.max_tentativas:
                return 0
            return max(1, int(self.janela - (agora - fila[0])))

    def registrar_falha(self, chave: str) -> None:
        with self._trava:
            agora = time.monotonic()
            self._limpar(chave, agora).append(agora)

    def limpar(self, chave: str) -> None:
        with self._trava:
            self._falhas.pop(chave, None)
