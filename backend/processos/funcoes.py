"""Regras dos processos: registrar o envio, consultar com dono, apagar e converter para os formatos da API."""

import re
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..usuarios.modelos import Usuario
from .armazem import ArmazemPdf
from .modelos import Processo, StatusAnalise, novo_id
from .progresso import RegistroProgresso
from .schemas import ProcessoDetalhe, ProcessoResumo, ProgressoSaida


def nome_seguro(nome_enviado: Optional[str], padrao: str = "arquivo.pdf") -> str:
    """Só o nome do arquivo (sem pasta), sem caracteres de controle, com no máximo 200 caracteres."""
    nome = Path((nome_enviado or "").replace("\\", "/")).name
    nome = re.sub(r"[\x00-\x1f\x7f]", "", nome).strip()[:200]
    return nome or padrao


def reiniciar(processo: Processo) -> None:
    """Volta o processo para a fila, sem resultado: PENDENTE nunca mostra dados de uma análise antiga."""
    processo.status = StatusAnalise.PENDENTE.value
    processo.erro = None
    processo.iniciado_em = processo.concluido_em = None
    processo.resultado = None
    processo.numero_processo = processo.tribunal = processo.fase = processo.divida_paga = None


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


def _campos_do_resultado(processo: Processo) -> dict:
    resultado = processo.resultado or {}
    evidencias = resultado.get("evidencias", [])
    return {
        "total_paginas": resultado.get("total_paginas"),
        "paginas_sem_texto": resultado.get("paginas_sem_texto"),
        "classe": resultado.get("classe"),
        "orgao_julgador": resultado.get("orgao_julgador"),
        "valor_causa": resultado.get("valor_causa"),
        "valor_requisitado": resultado.get("valor_requisitado"),
        "data_emissao_pdf": resultado.get("data_emissao_pdf"),
        "partes": resultado.get("partes", []),
        "advogados": resultado.get("advogados", []),
        "oabs": resultado.get("oabs", []),
        "juiz": resultado.get("juiz"),
        "fase_descricao": resultado.get("fase_descricao"),
        "avisos": resultado.get("avisos", []),
        "evidencia_principal": resultado.get("evidencia_principal"),
        "total_evidencias": len(evidencias),
        "evidencias_que_contam": sum(1 for ev in evidencias if ev.get("conta")),
    }


def _campo_progresso(processo: Processo, registro: Optional[RegistroProgresso]) -> Optional[ProgressoSaida]:
    progresso = registro.visivel(processo.id, processo.status) if registro else None
    return ProgressoSaida(**asdict(progresso)) if progresso else None


def _campos_base(processo: Processo, registro: Optional[RegistroProgresso]) -> dict:
    return {
        "id": processo.id,
        "arquivo": processo.arquivo,
        "tamanho_bytes": processo.tamanho_bytes,
        "criado_em": processo.criado_em,
        "concluido_em": processo.concluido_em,
        "status": processo.status,
        "erro": processo.erro,
        "progresso": _campo_progresso(processo, registro),
        "numero_processo": processo.numero_processo,
        "tribunal": processo.tribunal,
        "fase": processo.fase,
        "divida_paga": processo.divida_paga,
        **_campos_do_resultado(processo),
    }


def para_resumo(processo: Processo, registro: Optional[RegistroProgresso] = None) -> ProcessoResumo:
    return ProcessoResumo(**_campos_base(processo, registro))


def para_detalhe(processo: Processo, registro: Optional[RegistroProgresso] = None) -> ProcessoDetalhe:
    return ProcessoDetalhe(**_campos_base(processo, registro), evidencias=(processo.resultado or {}).get("evidencias", []))
