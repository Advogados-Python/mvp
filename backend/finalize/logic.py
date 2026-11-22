"""Fase 6 da leitura, FINALIZANDO O RESULTADO: reúne o que as fases entregaram e grava no banco, cada parte na tabela da sua fase
(leituras, identificacoes, evidencias, conclusoes) e o fechamento em resultados, tudo no mesmo commit. É a única fase que escreve o
resultado, e só depois do commit o processo passa a CONCLUIDO (ou FALHOU, com o motivo em linguagem do usuário).

Também: a serialização do processo para a API (resumo e detalhe, montados a partir das tabelas), a exportação do resultado em
JSON/CSV e a migração dos resultados que antes ficavam numa coluna JSON de `processos`."""

import csv
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import selectinload, sessionmaker

from ..db import agora
from ..extract.models import ErroLeituraPdf, ErroPdfNaoEncontrado, ErroPdfProtegido, LeituraGravada
from ..identify.models import IdentificacaoGravada
from ..receive.logic import limpar_fases
from ..receive.models import Processo, StatusAnalise
from ..search.models import EvidenciaGravada
from ..search.schemas import EvidenciaSaida
from ..validate.models import ConclusaoGravada
from .models import ResultadoGravado, ResultadoProcesso
from .schemas import ProcessoDetalhe, ProcessoResumo, ProgressoSaida

if TYPE_CHECKING:  # só para o tipo: a esteira (pipeline.py) importa este módulo, não o contrário
    from ..pipeline import RegistroProgresso

# Mensagens mostradas ao usuário quando o leitor falha (a mensagem técnica fica só no log do servidor).
MENSAGEM_POR_ERRO = {
    ErroPdfProtegido: "O PDF está protegido por senha.",
    ErroLeituraPdf: "Não foi possível abrir o arquivo como PDF (corrompido ou formato inválido).",
    ErroPdfNaoEncontrado: "O arquivo do PDF não foi encontrado no servidor.",
}
MENSAGEM_ERRO_INESPERADO = "Erro inesperado ao analisar o arquivo. Tente de novo; se persistir, avise o suporte."

registro = logging.getLogger("ribeiro.finalize")


def mensagem_do_erro(erro: Exception) -> str:
    for tipo, mensagem in MENSAGEM_POR_ERRO.items():
        if isinstance(erro, tipo):
            return mensagem
    return MENSAGEM_ERRO_INESPERADO


def gravar_fases(processo: Processo, dados: dict) -> None:
    """Escreve, na tabela de cada fase, o resultado de uma análise (o ResultadoProcesso em dict).

    Tudo entra na Session de quem chama: o commit dela grava as cinco tabelas de uma vez, ou nenhuma."""
    processo.leitura = LeituraGravada(  # fase 2
        total_paginas=dados.get("total_paginas") or 0, paginas_sem_texto=dados.get("paginas_sem_texto") or 0
    )
    processo.identificacao = IdentificacaoGravada(  # fase 3
        numero_processo=dados.get("numero_processo"),
        tribunal=dados.get("tribunal"),
        classe=dados.get("classe"),
        orgao_julgador=dados.get("orgao_julgador"),
        valor_causa=dados.get("valor_causa"),
        valor_requisitado=dados.get("valor_requisitado"),
        data_emissao_pdf=dados.get("data_emissao_pdf"),
        partes=[{"nome": parte["nome"], "papel": parte["papel"]} for parte in dados.get("partes") or []],
        advogados=list(dados.get("advogados") or []),
        oabs=list(dados.get("oabs") or []),
        juiz=dados.get("juiz"),
    )
    evidencias = [  # fase 4
        EvidenciaGravada(
            ordem=posicao,
            fase=ev["fase"],
            termo=ev["termo"],
            pagina=ev["pagina"],
            trecho=ev["trecho"],
            tipo_documento=ev.get("tipo_documento"),
            hipotetico=bool(ev.get("hipotetico")),
            origem_confiavel=bool(ev.get("origem_confiavel", True)),
        )
        for posicao, ev in enumerate(dados.get("evidencias") or [])
    ]
    processo.evidencias = evidencias
    processo.conclusao = ConclusaoGravada(  # fase 5
        fase=dados["fase"], fase_descricao=dados["fase_descricao"], divida_paga=dados["divida_paga"]
    )
    principal = next((ev for ev in evidencias if ev.conta and ev.fase == dados["fase"]), None)  # a primeira que conta da fase final
    processo.resultado = ResultadoGravado(  # fase 6
        avisos=list(dados.get("avisos") or []),
        total_evidencias=len(evidencias),
        evidencias_que_contam=sum(1 for ev in evidencias if ev.conta),
        evidencia_principal=principal,
    )


def gravar_resultado(fabrica: sessionmaker, processo_id: str, resultado: Optional[ResultadoProcesso], erro: Optional[str]) -> bool:
    """Grava o fim da análise: CONCLUIDO com o resultado nas tabelas das fases, ou FALHOU com o `erro`. Devolve False se o
    processo foi apagado enquanto era analisado (nada a gravar)."""
    with fabrica() as db:
        processo = db.get(Processo, processo_id)
        if processo is None:  # o usuário apagou enquanto analisávamos
            return False
        limpar_fases(processo)  # nunca sobra linha de uma análise anterior
        db.flush()
        processo.concluido_em = agora()
        if resultado is None:
            processo.status = StatusAnalise.FALHOU.value
            processo.erro = erro
        else:
            gravar_fases(processo, resultado.para_dict())
            processo.status = StatusAnalise.CONCLUIDO.value
            processo.erro = None
        db.commit()
    return True


def migrar_resultados_antigos(motor: Engine, fabrica: sessionmaker) -> int:
    """Passa para as tabelas das fases os resultados que antes ficavam na coluna JSON `processos.resultado`. Devolve quantos migrou.

    Roda na subida e é segura para repetir: só mexe em processo que ainda não tem a linha de `leituras`, e nunca apaga a coluna
    antiga (ela fica no banco, sem uso, até alguém decidir removê-la). Num banco novo a coluna nem existe e nada acontece."""
    colunas = {coluna["name"] for coluna in inspect(motor).get_columns("processos")}
    if "resultado" not in colunas:
        return 0
    migrados = 0
    with fabrica() as db:
        for processo_id, bruto in db.execute(text("SELECT id, resultado FROM processos WHERE resultado IS NOT NULL")).all():
            dados = json.loads(bruto) if isinstance(bruto, (str, bytes)) else bruto
            processo = db.get(Processo, processo_id)
            if not isinstance(dados, dict) or processo is None or processo.leitura is not None:
                continue  # JSON null (análise que falhou), processo sumiu ou já migrado
            try:
                with db.begin_nested():
                    gravar_fases(processo, dados)
                migrados += 1
            except Exception:
                registro.exception("Não foi possível migrar o resultado do processo %s", processo_id)
        db.commit()
    if migrados:
        registro.info("%d resultado(s) migrado(s) da coluna JSON para as tabelas das fases", migrados)
    return migrados


# O que a lista carrega de uma vez (em vez de uma consulta por processo e por tabela).
CARREGAR_FASES = (
    selectinload(Processo.leitura),
    selectinload(Processo.identificacao),
    selectinload(Processo.conclusao),
    selectinload(Processo.resultado).selectinload(ResultadoGravado.evidencia_principal),
)


def _campo_progresso(processo: Processo, registro: Optional["RegistroProgresso"]) -> Optional[ProgressoSaida]:
    progresso = registro.visivel(processo.id, processo.status) if registro else None
    return ProgressoSaida(**asdict(progresso)) if progresso else None


def _campos_das_fases(processo: Processo) -> dict:
    """Os campos de resultado do resumo, lidos da tabela de cada fase. Sem análise CONCLUIDA vêm todos vazios."""
    pronto = processo.status == StatusAnalise.CONCLUIDO.value
    leitura = processo.leitura if pronto else None
    ident = processo.identificacao if pronto else None
    conclusao = processo.conclusao if pronto else None
    fechamento = processo.resultado if pronto else None
    principal = fechamento.evidencia_principal if fechamento else None
    return {
        "total_paginas": leitura.total_paginas if leitura else None,
        "paginas_sem_texto": leitura.paginas_sem_texto if leitura else None,
        "numero_processo": ident.numero_processo if ident else None,
        "tribunal": ident.tribunal if ident else None,
        "classe": ident.classe if ident else None,
        "orgao_julgador": ident.orgao_julgador if ident else None,
        "valor_causa": ident.valor_causa if ident else None,
        "valor_requisitado": ident.valor_requisitado if ident else None,
        "data_emissao_pdf": ident.data_emissao_pdf if ident else None,
        "partes": (ident.partes or []) if ident else [],
        "advogados": (ident.advogados or []) if ident else [],
        "oabs": (ident.oabs or []) if ident else [],
        "juiz": ident.juiz if ident else None,
        "fase": conclusao.fase if conclusao else None,
        "fase_descricao": conclusao.fase_descricao if conclusao else None,
        "divida_paga": conclusao.divida_paga if conclusao else None,
        "avisos": (fechamento.avisos or []) if fechamento else [],
        "evidencia_principal": EvidenciaSaida.model_validate(principal) if principal else None,
        "total_evidencias": fechamento.total_evidencias if fechamento else 0,
        "evidencias_que_contam": fechamento.evidencias_que_contam if fechamento else 0,
    }


def _campos_base(processo: Processo, registro: Optional["RegistroProgresso"]) -> dict:
    return {
        "id": processo.id,
        "arquivo": processo.arquivo,
        "tamanho_bytes": processo.tamanho_bytes,
        "criado_em": processo.criado_em,
        "concluido_em": processo.concluido_em,
        "status": processo.status,
        "erro": processo.erro,
        "progresso": _campo_progresso(processo, registro),
        **_campos_das_fases(processo),
    }


def para_resumo(processo: Processo, registro: Optional["RegistroProgresso"] = None) -> ProcessoResumo:
    return ProcessoResumo(**_campos_base(processo, registro))


def para_detalhe(processo: Processo, registro: Optional["RegistroProgresso"] = None) -> ProcessoDetalhe:
    pronto = processo.status == StatusAnalise.CONCLUIDO.value
    evidencias = [EvidenciaSaida.model_validate(ev) for ev in processo.evidencias] if pronto else []
    return ProcessoDetalhe(**_campos_base(processo, registro), evidencias=evidencias)


def formatar_resumo(r: ResultadoProcesso, max_evidencias: int = 3) -> str:
    """Texto legível para o terminal."""
    partes = "; ".join("{} ({})".format(p["nome"], p["papel"]) for p in r.partes) or "-"
    linhas = [
        f"=== {r.arquivo}",
        f"  Processo : {r.numero_processo or '-'}  ({r.tribunal or '-'})  | {r.total_paginas} páginas",
        f"  Classe   : {r.classe or '-'}  | Órgão: {r.orgao_julgador or '-'}",
        f"  Partes   : {partes}",
        f"  Advogados: {'; '.join(r.advogados) or '-'}",
        f"  OAB      : {'; '.join(r.oabs) or '-'}",
        f"  Juiz     : {r.juiz or '-'}",
        f"  Valores  : causa {r.valor_causa or '-'} | requisitado {r.valor_requisitado or '-'}",
        f"  FASE     : {r.fase} - {r.fase_descricao}",
        f"  DÍVIDA PAGA? {r.divida_paga}" + (f"   (PDF gerado em {r.data_emissao_pdf})" if r.data_emissao_pdf else ""),
    ]
    for aviso in r.avisos:
        linhas.append(f"  [!] {aviso}")
    principais = [ev for ev in r.evidencias if ev.conta and ev.fase == r.fase][:max_evidencias]
    for ev in principais:
        linhas.append(f"  > pág. {ev.pagina} [{ev.termo}]: ...{ev.trecho}...")
    return "\n".join(linhas)


def exportar_json(resultado: ResultadoProcesso, pasta) -> Path:
    """Um JSON completo (com todas as evidências) por PDF: output/<nome-do-pdf>.json"""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{Path(resultado.arquivo).stem}.json"
    destino.write_text(json.dumps(resultado.para_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def _celula_segura(valor) -> str:
    """Evita injeção de fórmula no Excel: texto vindo do PDF não pode começar com = + - @."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def exportar_csv(resultados: list, pasta) -> Path:
    """Uma linha por processo em output/resumo.csv (separador ';' e BOM: abre direto no Excel pt-BR)."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "resumo.csv"
    colunas = [
        "arquivo", "numero_processo", "tribunal", "classe", "orgao_julgador", "partes", "advogados", "oabs",
        "juiz", "valor_causa", "valor_requisitado", "fase", "divida_paga", "pagina_evidencia",
        "trecho_evidencia", "data_emissao_pdf", "avisos", "total_paginas",
    ]
    with destino.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(colunas)
        for r in resultados:
            ev = r.evidencia_principal()
            escritor.writerow([_celula_segura(v) for v in (
                r.arquivo, r.numero_processo, r.tribunal, r.classe, r.orgao_julgador,
                " | ".join(f"{p['nome']} ({p['papel']})" for p in r.partes),
                " | ".join(r.advogados), " | ".join(r.oabs), r.juiz, r.valor_causa, r.valor_requisitado,
                r.fase, r.divida_paga, ev.pagina if ev else "", ev.trecho if ev else "",
                r.data_emissao_pdf, " | ".join(r.avisos), r.total_paginas,
            )])
    return destino
