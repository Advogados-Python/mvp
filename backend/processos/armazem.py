"""PDFs enviados, guardados em disco como <pasta>/<id>.pdf (o id é gerado por nós, nunca vem do usuário)."""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import BinaryIO

from .constantes import BLOCO_LEITURA, RE_ID
from .erros import ErroEnvio


class ArmazemPdf:
    def __init__(self, pasta: Path, max_bytes: int):
        self.pasta = Path(pasta)
        self.max_bytes = max_bytes

    def caminho(self, id_: str) -> Path:
        if not RE_ID.match(id_):  # defesa extra: o id vira nome de arquivo
            raise ValueError("id de processo inválido")
        return self.pasta / f"{id_}.pdf"

    def receber(self, arquivo: BinaryIO):
        """Grava o upload num temporário (em blocos, sem carregar tudo na memória) e devolve (caminho, sha256, bytes).

        Valida tamanho e a assinatura '%PDF-': o PyMuPDF abre vários formatos pelo conteúdo, então sem essa
        checagem um arquivo de outro tipo renomeado para .pdf seria aceito.
        """
        self.pasta.mkdir(parents=True, exist_ok=True)
        resumo, total, primeiro = hashlib.sha256(), 0, True
        descritor, temporario = tempfile.mkstemp(dir=self.pasta, suffix=".tmp")  # 0600: só o dono lê
        try:
            with os.fdopen(descritor, "wb") as saida:
                while bloco := arquivo.read(BLOCO_LEITURA):
                    if primeiro and b"%PDF-" not in bloco[:1024]:
                        raise ErroEnvio("O arquivo não é um PDF.")
                    primeiro = False
                    total += len(bloco)
                    if total > self.max_bytes:
                        raise ErroEnvio(f"O arquivo passa do limite de {self.max_bytes // (1024 * 1024)} MB.")
                    resumo.update(bloco)
                    saida.write(bloco)
            if total == 0:
                raise ErroEnvio("O arquivo está vazio.")
        except BaseException:
            Path(temporario).unlink(missing_ok=True)
            raise
        return Path(temporario), resumo.hexdigest(), total

    def guardar(self, temporario: Path, id_: str) -> Path:
        destino = self.caminho(id_)
        os.replace(temporario, destino)
        return destino

    def descartar(self, temporario: Path) -> None:
        Path(temporario).unlink(missing_ok=True)

    def remover(self, id_: str) -> None:
        self.caminho(id_).unlink(missing_ok=True)
