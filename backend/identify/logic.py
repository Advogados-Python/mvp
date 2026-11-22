"""Fase 3 da leitura, IDENTIFICANDO O PROCESSO: descobre de que peça é cada página (PJe) e extrai os dados do processo
(número, tribunal, partes, advogados, OAB, juiz, valores). Só regex, nada de IA."""

import re
from collections import Counter

from ..extract.logic import normalizar_espacos
from . import rules
from .models import Identificacao, Parte


def identificar_documentos(paginas: list) -> None:
    """PJe: descobre a qual documento (id, tipo, assinante) cada página pertence.

    Os autos do PJe juntam dezenas de documentos num só PDF. Cada página traz no rodapé
    "Assinado eletronicamente por: NOME - data ... Num. <id> - Pág. N" e o cabeçalho
    "Documento id <id> - <tipo>". Saber o TIPO permite (a) achar o juiz (quem assina a
    sentença) e (b) ignorar peças das partes na hora de decidir a fase.
    Em PDFs sem esse padrão (e-SAJ/TJSP) nada é preenchido, e tudo bem.
    """
    tipos = {}
    for pagina in paginas:
        for doc_id, tipo in rules.RE_PJE_CABECALHO_DOC.findall(pagina.texto):
            tipos.setdefault(doc_id, normalizar_espacos(tipo))

    for pagina in paginas:
        achou = rules.RE_PJE_NUM_DOC.search(pagina.texto)
        if not achou:
            continue
        pagina.documento_id = achou.group(1)
        pagina.tipo_documento = tipos.get(pagina.documento_id)
        assinatura = rules.RE_PJE_ASSINANTE.search(pagina.texto)
        if assinatura:
            pagina.assinante = normalizar_espacos(assinatura.group(1))


def identificar_tribunal(numero_cnj: str) -> str:
    """NNNNNNN-DD.AAAA.J.TR.OOOO -> 'TJSP', 'TRF1'... (J = ramo, TR = tribunal)."""
    achou = re.match(r"\d{7}-\d{2}\.\d{4}\.(\d)\.(\d{2})\.\d{4}$", numero_cnj or "")
    if not achou:
        return "desconhecido"
    ramo, tr = achou.groups()
    return rules.TRIBUNAIS_POR_RAMO.get(ramo, {}).get(tr, f"J{ramo}.TR{tr}")


def _extrair_partes_e_advogados(capa: str, texto_total: str):
    partes, advogados = [], []
    vistos = set()
    for nome, papel in rules.RE_PARTE_COM_PAPEL.findall(capa):
        nome, papel = normalizar_espacos(nome), ("RÉU" if papel == "REU" else papel)
        if (nome, papel) in vistos:
            continue
        vistos.add((nome, papel))
        if papel in rules.PAPEIS_ADVOGADO:
            advogados.append(nome)
        else:
            partes.append({"nome": nome, "papel": papel})

    if not partes:  # e-SAJ/TJSP: "Exequente: NOME," no corpo da petição
        for papel, nome in rules.RE_PARTE_ROTULO.findall(capa):
            nome = normalizar_espacos(nome)
            if (nome, papel.upper()) not in vistos:
                vistos.add((nome, papel.upper()))
                partes.append({"nome": nome, "papel": papel.upper()})

    if not advogados:  # formato de Diário da Justiça (não validado com PDF real ainda)
        for nome in rules.RE_ADVOGADO_DIARIO.findall(texto_total):
            nome = normalizar_espacos(nome)
            if nome and nome not in advogados:
                advogados.append(nome)
    return partes, advogados[:10]


def _extrair_oabs(texto_total: str) -> list:
    """OABs mais mencionadas, normalizadas como 'OAB/GO 12345 (12x)'."""
    contagem = Counter()
    for uf, numero in rules.RE_OAB_UF_PRIMEIRO.findall(texto_total):
        contagem[f"OAB/{uf} {numero.replace('.', '')}"] += 1
    for numero, uf in rules.RE_OAB_NUMERO_PRIMEIRO.findall(texto_total):
        contagem[f"OAB/{uf} {numero.replace('.', '')}"] += 1
    return [f"{oab} ({n}x)" for oab, n in contagem.most_common(rules.TOP_OAB)]


def _extrair_juiz(paginas: list, texto_total: str):
    """e-SAJ: 'Juiz(a) de Direito: Dr(a). NOME'. PJe: quem assina a sentença (ou decisão/despacho)."""
    nomes_esaj = rules.RE_JUIZ_ESAJ.findall(texto_total)
    if nomes_esaj:
        return Counter(nomes_esaj).most_common(1)[0][0]

    for tipo_procurado in (r"senten[çc]a", r"decis[ãa]o|despacho"):
        assinantes = [
            p.assinante for p in paginas
            if p.assinante and p.tipo_documento and re.search(tipo_procurado, p.tipo_documento, re.IGNORECASE)
        ]
        if assinantes:
            return Counter(assinantes).most_common(1)[0][0]
    return None


def _extrair_valor_requisitado(paginas: list):
    for regex in rules.RE_VALOR_REQUISITADO:
        for pagina in paginas:
            achou = regex.search(pagina.texto)
            if achou:
                return f"R$ {achou.group(1)}"
    return None


def extrair_metadados(paginas: list) -> dict:
    """Extrai com regex os dados de identificação do processo. Campos não achados ficam fora do dict."""
    capa = "\n".join(p.texto for p in paginas[: rules.PAGINAS_DA_CAPA])
    texto_total = "\n".join(p.texto for p in paginas)
    meta = {}

    for chave, regex in rules.RE_CAPA_PJE.items():
        achou = regex.search(capa)
        if achou:
            meta[chave] = normalizar_espacos(achou.group(1))

    if "numero_processo" not in meta:  # sem capa estruturada: o número mais repetido é o do processo
        numeros = rules.RE_CNJ.findall(texto_total)
        if numeros:
            meta["numero_processo"] = Counter(numeros).most_common(1)[0][0]

    if "classe" in meta:  # capa do PJe: a data no topo é a "posição" do processo
        achou = rules.RE_DATA_EMISSAO_CAPA.search(paginas[0].texto)
        if achou:
            meta["data_emissao_pdf"] = achou.group(1)

    meta["partes"], meta["advogados"] = _extrair_partes_e_advogados(capa, texto_total)
    meta["oabs"] = _extrair_oabs(texto_total)

    juiz = _extrair_juiz(paginas, texto_total)
    if juiz:
        meta["juiz"] = juiz
    valor = _extrair_valor_requisitado(paginas)
    if valor:
        meta["valor_requisitado"] = valor
    if "valor_causa" in meta:
        meta["valor_causa"] = f"R$ {meta['valor_causa']}"
    return meta


def identificar_processo(paginas: list) -> Identificacao:
    """A fase inteira: identifica os documentos (muda as páginas no lugar) e devolve a Identificacao do processo."""
    identificar_documentos(paginas)
    meta = extrair_metadados(paginas)
    numero = meta.get("numero_processo")
    return Identificacao(
        numero_processo=numero,
        tribunal=identificar_tribunal(numero) if numero else None,
        classe=meta.get("classe"),
        orgao_julgador=meta.get("orgao_julgador"),
        valor_causa=meta.get("valor_causa"),
        valor_requisitado=meta.get("valor_requisitado"),
        data_emissao_pdf=meta.get("data_emissao_pdf"),
        partes=[Parte(**parte) for parte in meta["partes"]],
        advogados=meta["advogados"],
        oabs=meta["oabs"],
        juiz=meta.get("juiz"),
        avisos=[] if numero else ["Número do processo (CNJ) não encontrado."],
    )
