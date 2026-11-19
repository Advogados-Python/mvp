"""Funções do pipeline:  ler PDF -> extrair metadados -> buscar termos -> classificar -> exportar.

Cada etapa é uma função pequena e independente, para poder ser testada com texto puro
(sem PDF) e trocada depois (ex.: ler_pdf com OCR, classificar com um LLM).
"""

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

import pymupdf

from ..fases import registro as _fases
from . import constantes as const
from .classes import Evidencia, Pagina, ResultadoProcesso
from .erros import ErroLeituraPdf, ErroPdfNaoEncontrado, ErroPdfProtegido

# Quem chama pode acompanhar o pipeline: aviso(etapa, atual, total). `atual`/`total` (páginas) só vêm nas etapas que
# trabalham página a página; nas demais ficam None. É só observação: não muda nenhum resultado.
AvisoDeEtapa = Callable[[str, Optional[int], Optional[int]], None]


# ======================================================================================
# Utilidades
# ======================================================================================
def normalizar_espacos(texto: str) -> str:
    """Troca quebras de linha e espaços repetidos por um único espaço."""
    return re.sub(r"\s+", " ", texto).strip()


def listar_pdfs(pasta) -> list:
    """PDFs de uma pasta (não recursivo), em ordem alfabética."""
    return sorted(p for p in Path(pasta).iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


# ======================================================================================
# 1) Leitura do PDF
# ======================================================================================
def ler_pdf(caminho, aviso: Optional[AvisoDeEtapa] = None) -> list:
    """Lê o PDF e devolve uma lista de Pagina (texto por página, na ordem natural de leitura).

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
            aviso(const.ETAPA_LENDO_PDF, 0, total)  # o total já é conhecido antes da primeira página
        for i, pagina in enumerate(documento.pages(), start=1):
            paginas.append(Pagina(numero=i, texto=_texto_da_pagina(pagina)))
            if aviso:
                aviso(const.ETAPA_LENDO_PDF, i, total)

    identificar_documentos(paginas)
    return paginas


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
        for doc_id, tipo in const.RE_PJE_CABECALHO_DOC.findall(pagina.texto):
            tipos.setdefault(doc_id, normalizar_espacos(tipo))

    for pagina in paginas:
        achou = const.RE_PJE_NUM_DOC.search(pagina.texto)
        if not achou:
            continue
        pagina.documento_id = achou.group(1)
        pagina.tipo_documento = tipos.get(pagina.documento_id)
        assinatura = const.RE_PJE_ASSINANTE.search(pagina.texto)
        if assinatura:
            pagina.assinante = normalizar_espacos(assinatura.group(1))


# ======================================================================================
# 2) Metadados (número, partes, advogados, juiz, valores) — só regex
# ======================================================================================
def identificar_tribunal(numero_cnj: str) -> str:
    """NNNNNNN-DD.AAAA.J.TR.OOOO -> 'TJSP', 'TRF1'... (J = ramo, TR = tribunal)."""
    achou = re.match(r"\d{7}-\d{2}\.\d{4}\.(\d)\.(\d{2})\.\d{4}$", numero_cnj or "")
    if not achou:
        return "desconhecido"
    ramo, tr = achou.groups()
    return const.TRIBUNAIS_POR_RAMO.get(ramo, {}).get(tr, f"J{ramo}.TR{tr}")


def _extrair_partes_e_advogados(capa: str, texto_total: str):
    partes, advogados = [], []
    vistos = set()
    for nome, papel in const.RE_PARTE_COM_PAPEL.findall(capa):
        nome, papel = normalizar_espacos(nome), ("RÉU" if papel == "REU" else papel)
        if (nome, papel) in vistos:
            continue
        vistos.add((nome, papel))
        if papel in const.PAPEIS_ADVOGADO:
            advogados.append(nome)
        else:
            partes.append({"nome": nome, "papel": papel})

    if not partes:  # e-SAJ/TJSP: "Exequente: NOME," no corpo da petição
        for papel, nome in const.RE_PARTE_ROTULO.findall(capa):
            nome = normalizar_espacos(nome)
            if (nome, papel.upper()) not in vistos:
                vistos.add((nome, papel.upper()))
                partes.append({"nome": nome, "papel": papel.upper()})

    if not advogados:  # formato de Diário da Justiça (não validado com PDF real ainda)
        for nome in const.RE_ADVOGADO_DIARIO.findall(texto_total):
            nome = normalizar_espacos(nome)
            if nome and nome not in advogados:
                advogados.append(nome)
    return partes, advogados[:10]


def _extrair_oabs(texto_total: str) -> list:
    """OABs mais mencionadas, normalizadas como 'OAB/GO 12345 (12x)'."""
    contagem = Counter()
    for uf, numero in const.RE_OAB_UF_PRIMEIRO.findall(texto_total):
        contagem[f"OAB/{uf} {numero.replace('.', '')}"] += 1
    for numero, uf in const.RE_OAB_NUMERO_PRIMEIRO.findall(texto_total):
        contagem[f"OAB/{uf} {numero.replace('.', '')}"] += 1
    return [f"{oab} ({n}x)" for oab, n in contagem.most_common(const.TOP_OAB)]


def _extrair_juiz(paginas: list, texto_total: str):
    """e-SAJ: 'Juiz(a) de Direito: Dr(a). NOME'. PJe: quem assina a sentença (ou decisão/despacho)."""
    nomes_esaj = const.RE_JUIZ_ESAJ.findall(texto_total)
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
    for regex in const.RE_VALOR_REQUISITADO:
        for pagina in paginas:
            achou = regex.search(pagina.texto)
            if achou:
                return f"R$ {achou.group(1)}"
    return None


def extrair_metadados(paginas: list) -> dict:
    """Extrai com regex os dados de identificação do processo. Campos não achados ficam fora do dict."""
    capa = "\n".join(p.texto for p in paginas[: const.PAGINAS_DA_CAPA])
    texto_total = "\n".join(p.texto for p in paginas)
    meta = {}

    for chave, regex in const.RE_CAPA_PJE.items():
        achou = regex.search(capa)
        if achou:
            meta[chave] = normalizar_espacos(achou.group(1))

    if "numero_processo" not in meta:  # sem capa estruturada: o número mais repetido é o do processo
        numeros = const.RE_CNJ.findall(texto_total)
        if numeros:
            meta["numero_processo"] = Counter(numeros).most_common(1)[0][0]

    if "classe" in meta:  # capa do PJe: a data no topo é a "posição" do processo
        achou = const.RE_DATA_EMISSAO_CAPA.search(paginas[0].texto)
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


# ======================================================================================
# 3) Busca de termos do dicionário
# ======================================================================================
def _origem_confiavel(tipo_documento) -> bool:
    """Sem tipo (capa/e-SAJ) é aceito; com tipo, só documentos do juízo."""
    return tipo_documento is None or bool(const.RE_TIPO_DOC_DO_JUIZO.search(tipo_documento))


def _eh_hipotetico(texto: str, inicio: int) -> bool:
    """True se, na frase que antecede o termo, há palavra de condição/futuro, ou uma negação colada nele."""
    janela = texto[max(0, inicio - const.JANELA_CONTEXTO): inicio]
    frase_atual = const.RE_FRONTEIRA_DE_FRASE.split(janela)[-1]
    return bool(
        const.RE_CONTEXTO_HIPOTETICO.search(frase_atual)
        or const.RE_NEGACAO_PROXIMA.search(frase_atual[-const.JANELA_NEGACAO:])
    )


def buscar_termos(paginas: list, aviso: Optional[AvisoDeEtapa] = None) -> list:
    """Procura todos os termos do DICIONARIO_TERMOS e devolve Evidencias (página + trecho).

    `aviso`, se dado, recebe (ETAPA_ANALISANDO_FASES, páginas analisadas, total de páginas) a cada página.
    """
    evidencias = []
    guardadas = Counter()
    metade = const.TAMANHO_TRECHO // 2

    for analisadas, pagina in enumerate(paginas):
        if aviso:
            aviso(const.ETAPA_ANALISANDO_FASES, analisadas, len(paginas))
        texto = normalizar_espacos(pagina.texto)
        confiavel = _origem_confiavel(pagina.tipo_documento)
        for fase, termo, regex in const.TERMOS_COMPILADOS:
            for achado in regex.finditer(texto):
                hipotetico = _eh_hipotetico(texto, achado.start())
                chave = (termo, hipotetico, confiavel)
                if guardadas[chave] >= const.MAX_EVIDENCIAS_POR_TERMO:
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
        aviso(const.ETAPA_ANALISANDO_FASES, len(paginas), len(paginas))
    return evidencias


# ======================================================================================
# 4) Classificação
# ======================================================================================
def classificar_fase(evidencias: list) -> str:
    """A fase é a mais avançada da escada que tenha ao menos uma evidência que 'conta'."""
    fase = "SEM_INFORMACAO"
    for ev in evidencias:
        if ev.conta and ev.fase in const.ORDEM_FASE and const.ORDEM_FASE[ev.fase] > const.ORDEM_FASE[fase]:
            fase = ev.fase
    return fase


def responder_divida_paga(fase: str) -> str:
    """Traduz a fase na resposta direta: SIM / PROVAVEL / NAO / SEM_INFORMACAO. Quem responde é a própria fase
    (backend/fases/<fase>/modelos.py: `divida_paga`). Um código que não é da escada responde NAO, como sempre."""
    degrau = _fases.fase_da_escada(fase)
    return degrau.divida_paga.value if degrau else const.DIVIDA_PAGA_NAO


# ======================================================================================
# 5) Pipeline completo de um PDF
# ======================================================================================
def processar_pdf(caminho, aviso: Optional[AvisoDeEtapa] = None) -> ResultadoProcesso:
    """Roda o pipeline completo em um PDF (ler, extrair, buscar, classificar) e devolve o ResultadoProcesso.

    `aviso`, se dado, é chamado ao entrar em cada etapa (const.ETAPA_*) e, nas etapas que andam página a página,
    a cada página. A etapa só é anunciada quando ela realmente começa: quem acompanha pode tratar as anteriores como feitas.
    """
    def informar(etapa, atual=None, total=None):
        if aviso:
            aviso(etapa, atual, total)

    caminho = Path(caminho)
    informar(const.ETAPA_LENDO_PDF)
    paginas = ler_pdf(caminho, aviso)
    sem_texto = sum(p.sem_texto for p in paginas)
    resultado = ResultadoProcesso(arquivo=caminho.name, total_paginas=len(paginas), paginas_sem_texto=sem_texto)

    if sem_texto:
        resultado.avisos.append(_aviso_paginas_sem_texto(paginas, sem_texto))

    informar(const.ETAPA_IDENTIFICANDO)
    meta = extrair_metadados(paginas)
    resultado.numero_processo = meta.get("numero_processo")
    resultado.tribunal = identificar_tribunal(resultado.numero_processo) if resultado.numero_processo else None
    resultado.classe = meta.get("classe")
    resultado.orgao_julgador = meta.get("orgao_julgador")
    resultado.valor_causa = meta.get("valor_causa")
    resultado.valor_requisitado = meta.get("valor_requisitado")
    resultado.data_emissao_pdf = meta.get("data_emissao_pdf")
    resultado.partes = meta["partes"]
    resultado.advogados = meta["advogados"]
    resultado.oabs = meta["oabs"]
    resultado.juiz = meta.get("juiz")

    if not resultado.numero_processo:
        resultado.avisos.append("Número do processo (CNJ) não encontrado.")

    informar(const.ETAPA_ANALISANDO_FASES, 0, len(paginas))
    resultado.evidencias = buscar_termos(paginas, aviso)
    informar(const.ETAPA_VALIDANDO)
    resultado.fase = classificar_fase(resultado.evidencias)
    resultado.fase_descricao = const.DESCRICAO_FASE[resultado.fase]
    resultado.divida_paga = responder_divida_paga(resultado.fase)

    if any(ev.fase == "ALERTA" and ev.conta for ev in resultado.evidencias):
        resultado.avisos.append(
            "Encontrado 'julgo improcedente' em peça do juízo: confirme se existe mesmo crédito a receber."
        )
    resultado.avisos.extend(_avisar_mencoes_ignoradas(resultado))
    return resultado


def _aviso_paginas_sem_texto(paginas: list, sem_texto: int) -> str:
    """Páginas que são só imagem (scan) NÃO foram lidas: o que estiver escrito nelas não entra no resultado."""
    numeros = [p.numero for p in paginas if p.sem_texto]
    lista = ", ".join(map(str, numeros[:12])) + ("..." if len(numeros) > 12 else "")
    aviso = f"{sem_texto}/{len(paginas)} páginas sem texto (imagem/scan) NÃO foram lidas: pág. {lista}. Rode OCR para lê-las (veja README)."
    if sem_texto / len(paginas) >= const.PERCENTUAL_SEM_TEXTO_PARA_ALERTA:
        aviso += " Mais da metade do PDF não foi lida: resultado pouco confiável."
    return aviso


def _avisar_mencoes_ignoradas(resultado: ResultadoProcesso) -> list:
    """Errar para 'não pago' é o erro caro (comprar crédito já quitado), então nada some em silêncio.

    Se há menção CONDICIONAL a pagamento/quitação acima da fase atual (texto-padrão tipo
    'após o pagamento, será intimada para o levantamento'), ela foi ignorada na classificação,
    mas fica sinalizada com as páginas para conferência humana.
    """
    atual = const.ORDEM_FASE[resultado.fase]
    paginas = sorted({
        ev.pagina for ev in resultado.evidencias
        if ev.hipotetico and ev.origem_confiavel
        and ev.fase in ("PAGAMENTO_DISPONIBILIZADO", "QUITADO")
        and const.ORDEM_FASE[ev.fase] > atual
    })
    if not paginas:
        return []
    return [
        "Menções condicionais/futuras a pagamento ou quitação foram ignoradas (pág. "
        + ", ".join(map(str, paginas[:10]))
        + "). Se alguma for pagamento real, a fase está subestimada."
    ]


# ======================================================================================
# 6) Saída
# ======================================================================================
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
