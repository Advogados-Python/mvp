"""A barreira de privacidade da camada de IA: o que NÃO pode sair do servidor rumo ao modelo de linguagem.

Duas proteções, aplicadas pela própria API a TODO pedido (não dependem de o chamador ter feito a sua parte):

    remover_cabecalho   tira a capa dos autos (PJe): número, classe, partes, advogados e o índice de documentos.
                        É idempotente: se o chamador já tirou a capa, não há o que tirar e nada muda.
    anonimizar          mascara número do processo, CPF, CNPJ, e-mail e telefone que apareçam no corpo (e-SAJ não tem capa: o
                        timbre da petição traz endereço e telefone do escritório).

O que NÃO é coberto: NOMES. As partes e os advogados continuam sendo citados ao longo das peças (nos PDFs de exemplo, todos os
nomes da capa ainda aparecem no corpo depois de tirá-la), e o nome de quem assina cada peça fica no rodapé. Mascarar nomes por busca
exata daria falsa segurança (maiúsculas, abreviações, nomes parciais). A garantia é "sem capa e sem documentos/contatos", não
"texto anônimo".

Falha fechada: se o texto começa com a capa mas não dá para saber onde ela termina, a API recusa o pedido em vez de arriscar.
"""

import re

from ..identify import rules


class ErroCabecalho(Exception):
    """A capa dos autos está no texto e não foi possível separá-la do resto."""


def _parece_capa(texto: str) -> bool:
    """A capa do PJe traz "Número: <CNJ>" e "Classe: ..." juntos. É o mesmo critério que a fase 3 usa para ler a capa."""
    return bool(rules.RE_CAPA_PJE["numero_processo"].search(texto) and rules.RE_CAPA_PJE["classe"].search(texto))


def paginas_da_capa(paginas: list) -> int:
    """Quantas páginas, desde a primeira, são a capa (0 se o texto não começa por uma).

    No PJe a capa e o índice de documentos ocupam as primeiras páginas, e a primeira peça começa na página seguinte: é a primeira
    com o rodapé "Num. <id> - Pág. N" (e que não é, ela mesma, a capa). O índice pode passar de uma página, por isso não vale um
    número fixo. `paginas` precisa estar em ordem de página; cada item tem `.texto`.
    """
    if not paginas or not _parece_capa(paginas[0].texto):
        return 0
    for posicao, pagina in enumerate(paginas):
        if rules.RE_PJE_NUM_DOC.search(pagina.texto) and not _parece_capa(pagina.texto):
            return posicao
    raise ErroCabecalho("O texto começa pela capa dos autos, mas nenhuma peça vem depois dela: não dá para separar o cabeçalho.")


def remover_cabecalho(paginas: list) -> tuple:
    """(páginas sem a capa, quantas páginas de capa foram retiradas). Levanta ErroCabecalho se não puder separar."""
    quantas = paginas_da_capa(paginas)
    return paginas[quantas:], quantas


# (padrão, o que fica no lugar). Só formatos inconfundíveis: um padrão frouxo apagaria número de processo, valor ou data.
_MASCARAS = (
    (rules.RE_CNJ, "[Nº DO PROCESSO]"),  # o número se repete no topo de cada página e identifica o caso (e as partes) em qualquer site de tribunal
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF]"),
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "[CNPJ]"),
    (re.compile(r"(\bCPF\b[^0-9\n]{0,20})\d{11}\b", re.IGNORECASE), r"\1[CPF]"),  # "CPF nº 12345678901", sem pontuação
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[E-MAIL]"),
    (re.compile(r"(?:\+55\s?)?\(\d{2}\)\s?9?\d{4}-?\d{4}"), "[TELEFONE]"),         # só com DDD entre parênteses
)


def anonimizar(texto: str) -> str:
    for padrao, no_lugar in _MASCARAS:
        texto = padrao.sub(no_lugar, texto)
    return texto
