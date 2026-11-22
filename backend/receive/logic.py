"""Fase 1 da leitura, DOCUMENTO RECEBIDO: registra o PDF recebido como um processo na fila (o mesmo PDF da mesma conta reaproveita
o registro), devolve o processo à fila quando a análise é refeita, consulta com dono e apaga. O PDF em si é guardado por store.py.

O que as fases seguintes gravam fica em tabelas próprias, ligadas ao processo; `limpar_fases` as esvazia e `obter_concluido` / `exigir`
protegem as APIs dessas fases."""

import re
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..userauths.models import Usuario
from .models import Processo, StatusAnalise, novo_id
from .store import ArmazemPdf


def nome_seguro(nome_enviado: Optional[str], padrao: str = "arquivo.pdf") -> str:
    """Só o nome do arquivo (sem pasta), sem caracteres de controle, com no máximo 200 caracteres."""
    nome = Path((nome_enviado or "").replace("\\", "/")).name
    nome = re.sub(r"[\x00-\x1f\x7f]", "", nome).strip()[:200]
    return nome or padrao


def limpar_fases(processo: Processo) -> None:
    """Apaga o que as fases 2 a 6 gravaram para este processo (as linhas das tabelas leituras, identificacoes, evidencias,
    conclusoes e resultados). Vale depois do próximo commit."""
    processo.resultado = None
    processo.conclusao = None
    processo.evidencias = []
    processo.identificacao = None
    processo.leitura = None


def reiniciar(processo: Processo) -> None:
    """Volta o processo para a fila, sem resultado: PENDENTE nunca mostra dados de uma análise antiga."""
    processo.status = StatusAnalise.PENDENTE.value
    processo.erro = None
    processo.iniciado_em = processo.concluido_em = None
    limpar_fases(processo)


def registrar_envio(
    db: Session, armazem: ArmazemPdf, usuario: Usuario, nome: str, temporario: Path, sha256: str, tamanho: int
):
    """Cria o registro do PDF recebido. Devolve (processo, precisa_analisar).

    O mesmo PDF (mesmo SHA-256) enviado de novo pelo mesmo usuário reaproveita o registro: se a análise
    já terminou, ela é refeita (útil depois de ensinar termos novos ao dicionário); se está na fila, nada muda.
    """
    consulta = select(Processo).where(Processo.dono_id == usuario.id, Processo.sha256 == sha256)
    existente = db.scalar(consulta)
    if existente is None:
        processo = Processo(id=novo_id(), dono_id=usuario.id, arquivo=nome, sha256=sha256, tamanho_bytes=tamanho)
        db.add(processo)
        try:
            db.flush()  # é aqui que a restrição de unicidade (dono + sha256) dispara
            armazem.guardar(temporario, processo.id)
            db.commit()
            return processo, True
        except IntegrityError:  # dois envios idênticos ao mesmo tempo: o outro chegou primeiro
            db.rollback()
            armazem.descartar(temporario)
            armazem.remover(processo.id)
            existente = db.scalar(consulta)
        except BaseException:
            db.rollback()
            armazem.descartar(temporario)
            armazem.remover(processo.id)
            raise
    else:
        armazem.descartar(temporario)  # já temos o mesmo conteúdo guardado

    if existente is None:  # corrida improvável: o outro envio também falhou
        raise HTTPException(status.HTTP_409_CONFLICT, "Não foi possível registrar o arquivo. Tente de novo.")
    if StatusAnalise(existente.status).em_andamento:
        return existente, False
    reiniciar(existente)
    existente.arquivo = nome
    db.commit()
    return existente, True


def obter_do_usuario(db: Session, usuario: Usuario, processo_id: str) -> Processo:
    """404 (e não 403) para processo de outra pessoa: não revela que o id existe."""
    processo = db.get(Processo, processo_id)
    if processo is None or processo.dono_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Processo não encontrado.")
    return processo


def excluir(db: Session, armazem: ArmazemPdf, processo: Processo) -> None:
    armazem.remover(processo.id)
    db.delete(processo)
    db.commit()


def obter_concluido(db: Session, usuario: Usuario, processo_id: str) -> Processo:
    """O processo, para as APIs das fases 2 a 5, que só existem para análise CONCLUIDA (409 nos demais casos)."""
    processo = obter_do_usuario(db, usuario, processo_id)
    if processo.status == StatusAnalise.FALHOU.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "A análise deste processo falhou: esta fase não produziu resultado.")
    if processo.status != StatusAnalise.CONCLUIDO.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "A análise deste processo ainda não terminou.")
    return processo


def exigir(linha):
    """A linha que a fase gravou na sua tabela. Se um processo CONCLUIDO não a tem, algo ficou pela metade: 409, não erro 500."""
    if linha is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O resultado desta fase não está gravado. Refaça a análise.")
    return linha
