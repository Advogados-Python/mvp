"""O job de análise: lê o PDF com o leitor e grava o resultado no banco.

Roda numa thread da fila, longe da requisição. O PDF é lido FORA de qualquer transação aberta,
para não segurar uma conexão do banco durante a leitura de centenas de páginas.
"""

import logging
from dataclasses import asdict
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from ..leitor.classes import ResultadoProcesso
from ..leitor.constantes import ETAPA_LENDO_PDF
from ..leitor.erros import ErroRibeiro
from ..leitor.funcoes import processar_pdf
from ..nucleo.banco import agora
from .armazem import ArmazemPdf
from .constantes import MENSAGEM_ERRO_INESPERADO, MENSAGEM_POR_ERRO
from .modelos import Processo, StatusAnalise
from .progresso import ETAPA_FINALIZANDO, RegistroProgresso

registro = logging.getLogger("ribeiro.analise")


def mensagem_do_erro(erro: Exception) -> str:
    for tipo, mensagem in MENSAGEM_POR_ERRO.items():
        if isinstance(erro, tipo):
            return mensagem
    return MENSAGEM_ERRO_INESPERADO


def montar_resultado(resultado: ResultadoProcesso) -> dict:
    """O que fica no banco (coluna JSON): o ResultadoProcesso + o campo `conta` de cada evidência + a principal."""
    dados = resultado.para_dict()
    dados.pop("arquivo", None)  # o nome original já está na coluna `arquivo`
    principal = resultado.evidencia_principal()
    dados["evidencias"] = [{**asdict(ev), "conta": ev.conta} for ev in resultado.evidencias]
    dados["evidencia_principal"] = {**asdict(principal), "conta": True} if principal else None
    return dados


def analisar_processo(
    fabrica: sessionmaker, armazem: ArmazemPdf, processo_id: str, progresso: Optional[RegistroProgresso] = None
) -> None:
    """PENDENTE -> ANALISANDO -> CONCLUIDO | FALHOU. Não faz nada se outro worker já pegou o processo.

    `progresso` recebe a etapa em que a análise está. O fim (CONCLUIDO/FALHOU) só é anunciado DEPOIS do commit:
    quem acompanha lê o banco ao ser avisado e precisa encontrar o status final lá.
    """
    progresso = progresso or RegistroProgresso()  # sem ninguém acompanhando, vai para um registro descartável
    with fabrica() as db:
        # "Reivindica" com um UPDATE condicional: se dois workers pegarem o mesmo id, só um ganha.
        pegou = db.execute(
            update(Processo)
            .where(Processo.id == processo_id, Processo.status == StatusAnalise.PENDENTE.value)
            .values(status=StatusAnalise.ANALISANDO.value, iniciado_em=agora(), erro=None)
        ).rowcount
        db.commit()
    if not pegou:
        return

    def informar(etapa: str, atual: Optional[int] = None, total: Optional[int] = None) -> None:
        progresso.atualizar(processo_id, etapa, atual, total)

    informar(ETAPA_LENDO_PDF)  # já com a análise reivindicada: a falha de uma execução anterior deixa de valer
    erro, resultado = None, None
    try:
        resultado = processar_pdf(armazem.caminho(processo_id), informar)
    except ErroRibeiro as falha:
        erro = mensagem_do_erro(falha)
    except Exception:
        registro.exception("Falha inesperada ao analisar o processo %s", processo_id)
        erro = MENSAGEM_ERRO_INESPERADO

    if resultado is not None:
        informar(ETAPA_FINALIZANDO)
    with fabrica() as db:
        processo = db.get(Processo, processo_id)
        if processo is None:  # o usuário apagou enquanto analisávamos
            progresso.descartar(processo_id)
            return
        processo.concluido_em = agora()
        if resultado is None:
            processo.status = StatusAnalise.FALHOU.value
            processo.erro = erro
            processo.resultado = None
            processo.numero_processo = processo.tribunal = processo.fase = processo.divida_paga = None
        else:
            processo.status = StatusAnalise.CONCLUIDO.value
            processo.erro = None
            processo.resultado = montar_resultado(resultado)
            processo.numero_processo = resultado.numero_processo
            processo.tribunal = resultado.tribunal
            processo.fase = resultado.fase
            processo.divida_paga = resultado.divida_paga
        db.commit()

    if resultado is None:
        progresso.falhar(processo_id)  # guarda em que etapa parou, para a tela dizer onde falhou
    else:
        progresso.descartar(processo_id)
