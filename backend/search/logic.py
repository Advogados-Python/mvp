"""Fase 4 da leitura, BUSCANDO OS TERMOS: procura, página a página, os termos do dicionário e guarda cada achado como uma
Evidencia (página + trecho), já dizendo se a frase é hipotética e se veio do juízo."""

from collections import Counter
from typing import Optional

from ..extract.logic import AvisoDeEtapa, normalizar_espacos
from . import terms
from .models import STAGE, Evidencia


def _origem_confiavel(tipo_documento) -> bool:
    """Sem tipo (capa/e-SAJ) é aceito; com tipo, só documentos do juízo."""
    return tipo_documento is None or bool(terms.RE_TIPO_DOC_DO_JUIZO.search(tipo_documento))


def _eh_hipotetico(texto: str, inicio: int) -> bool:
    """True se, na frase que antecede o termo, há palavra de condição/futuro, ou uma negação colada nele."""
    janela = texto[max(0, inicio - terms.JANELA_CONTEXTO): inicio]
    frase_atual = terms.RE_FRONTEIRA_DE_FRASE.split(janela)[-1]
    return bool(
        terms.RE_CONTEXTO_HIPOTETICO.search(frase_atual)
        or terms.RE_NEGACAO_PROXIMA.search(frase_atual[-terms.JANELA_NEGACAO:])
    )


def buscar_termos(paginas: list, aviso: Optional[AvisoDeEtapa] = None) -> list:
    """Procura todos os termos do DICIONARIO_TERMOS e devolve Evidencias (página + trecho).

    `aviso`, se dado, recebe (STAGE, páginas analisadas, total de páginas) a cada página.
    """
    evidencias = []
    guardadas = Counter()
    metade = terms.TAMANHO_TRECHO // 2

    for analisadas, pagina in enumerate(paginas):
        if aviso:
            aviso(STAGE, analisadas, len(paginas))
        texto = normalizar_espacos(pagina.texto)
        confiavel = _origem_confiavel(pagina.tipo_documento)
        for fase, termo, regex in terms.TERMOS_COMPILADOS:
            for achado in regex.finditer(texto):
                hipotetico = _eh_hipotetico(texto, achado.start())
                chave = (termo, hipotetico, confiavel)
                if guardadas[chave] >= terms.MAX_EVIDENCIAS_POR_TERMO:
                    continue
                guardadas[chave] += 1
                evidencias.append(Evidencia(
                    fase=fase,
                    termo=termo,
                    pagina=pagina.numero,
                    trecho=texto[max(0, achado.start() - metade): achado.end() + metade],
                    tipo_documento=pagina.tipo_documento,
                    hipotetico=hipotetico,
                    origem_confiavel=confiavel,
                ))
    if aviso:
        aviso(STAGE, len(paginas), len(paginas))
    return evidencias
