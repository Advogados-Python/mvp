"""Fase 2 da leitura, EXTRAINDO CONTEÚDO: abre o PDF e devolve o texto de cada página, na ordem natural de leitura."""

import re
from pathlib import Path
from typing import Callable, Optional

import pymupdf

from .models import (
    PERCENTUAL_SEM_TEXTO_PARA_ALERTA,
    STAGE,
    ErroLeituraPdf,
    ErroPdfNaoEncontrado,
    ErroPdfProtegido,
    Leitura,
    Pagina,
)

# Quem chama pode acompanhar a leitura: aviso(etapa, atual, total). `atual`/`total` (páginas) só vêm nas fases que
# trabalham página a página; nas demais ficam None. É só observação: não muda nenhum resultado.
AvisoDeEtapa = Callable[[str, Optional[int], Optional[int]], None]


def ler_pdf(caminho, aviso: Optional[AvisoDeEtapa] = None) -> list:
    """Lê o PDF e devolve uma lista de Pagina (texto por página, na ordem natural de leitura). Só o texto: a identificação
    dos documentos (tipo e assinante de cada página) é a fase 3.

    Levanta ErroPdfNaoEncontrado, ErroPdfProtegido ou ErroLeituraPdf.
    PDFs escaneados (só imagem) não dão erro: voltam com páginas `sem_texto`.
    `aviso`, se dado, recebe (ETAPA_LENDO_PDF, páginas lidas, total de páginas) a cada página.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroPdfNaoEncontrado(f"Arquivo não encontrado: {caminho}")
    try:
        documento = pymupdf.open(caminho)
    except Exception as erro:  # pymupdf lança vários tipos (FileDataError, EmptyFileError...)
        raise ErroLeituraPdf(f"Não foi possível abrir '{caminho.name}': {erro}") from erro

    with documento:
        if documento.needs_pass:
            raise ErroPdfProtegido(f"'{caminho.name}' está protegido por senha")
        total = documento.page_count
        paginas = []
        if aviso:
            aviso(STAGE, 0, total)  # o total já é conhecido antes da primeira página
        for i, pagina in enumerate(documento.pages(), start=1):
            paginas.append(Pagina(numero=i, texto=_texto_da_pagina(pagina)))
            if aviso:
                aviso(STAGE, i, total)

    return paginas  # só o texto: descobrir de que peça é cada página é a fase seguinte (identificacao/)


def _texto_da_pagina(pagina) -> str:
    """Texto da página na ordem natural de leitura, SEM as linhas rotacionadas.

    O e-SAJ (TJSP) imprime a assinatura digital na vertical, na margem. Se entrar no texto,
    palavras da margem se misturam às da petição ("...DO ROBERTO ESTADO DE SÃO PAULO").
    `dir` é o vetor de direção da linha: (1, 0) = horizontal, esquerda para direita.
    sort=True ordena de cima para baixo / esquerda para direita.
    """
    linhas = []
    for bloco in pagina.get_text("dict", sort=True)["blocks"]:
        for linha in bloco.get("lines", []):  # blocos de imagem não têm "lines"
            if linha["dir"][0] >= 0.9:
                linhas.append("".join(span["text"] for span in linha["spans"]))
    return "\n".join(linhas)


def _aviso_paginas_sem_texto(paginas: list, sem_texto: int) -> str:
    """Páginas que são só imagem (scan) NÃO foram lidas: o que estiver escrito nelas não entra no resultado."""
    numeros = [p.numero for p in paginas if p.sem_texto]
    lista = ", ".join(map(str, numeros[:12])) + ("..." if len(numeros) > 12 else "")
    aviso = f"{sem_texto}/{len(paginas)} páginas sem texto (imagem/scan) NÃO foram lidas: pág. {lista}. Rode OCR para lê-las (veja README)."
    if sem_texto / len(paginas) >= PERCENTUAL_SEM_TEXTO_PARA_ALERTA:
        aviso += " Mais da metade do PDF não foi lida: resultado pouco confiável."
    return aviso


def extrair_conteudo(caminho, aviso: Optional[AvisoDeEtapa] = None) -> Leitura:
    """A fase inteira: lê o PDF e devolve a Leitura (as páginas, quantas não têm texto e o aviso de qualidade, se houver)."""
    paginas = ler_pdf(caminho, aviso)
    sem_texto = sum(p.sem_texto for p in paginas)
    avisos = [_aviso_paginas_sem_texto(paginas, sem_texto)] if sem_texto else []
    return Leitura(paginas=paginas, paginas_sem_texto=sem_texto, avisos=avisos)


def normalizar_espacos(texto: str) -> str:
    """Troca quebras de linha e espaços repetidos por um único espaço."""
    return re.sub(r"\s+", " ", texto).strip()


def listar_pdfs(pasta) -> list:
    """PDFs de uma pasta (não recursivo), em ordem alfabética."""
    return sorted(p for p in Path(pasta).iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
