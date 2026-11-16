"""Constantes do MVP: caminhos, parâmetros, DICIONÁRIO DE TERMOS e expressões regulares.

Toda a "regra de negócio" mora aqui. Para ensinar o sistema a reconhecer um termo novo,
basta acrescentar uma linha em DICIONARIO_TERMOS — não é preciso mexer em funcoes.py.

Convenção: os padrões são escritos como texto (r"...") e compilados no final do arquivo
com re.IGNORECASE. Os padrões de nomes próprios em MAIÚSCULAS são compilados sem
IGNORECASE de propósito (senão "de", "da" casariam com [A-Z]).
"""

import re
from pathlib import Path

# --------------------------------------------------------------------------------------
# Caminhos e parâmetros
# --------------------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
PASTA_INPUT = RAIZ / "input"
PASTA_OUTPUT = RAIZ / "output"

MIN_CARACTERES_PAGINA = 30            # página com menos texto que isso é tratada como "sem texto" (scan)
PERCENTUAL_SEM_TEXTO_PARA_ALERTA = 0.5  # se >= 50% das páginas estão sem texto, avisa que precisa de OCR
PAGINAS_DA_CAPA = 6                   # a capa do PJe (partes, advogados) fica nas primeiras páginas

TAMANHO_TRECHO = 240                  # caracteres de contexto guardados em cada evidência
JANELA_CONTEXTO = 110                 # quantos caracteres olhar para trás ao testar "contexto hipotético"
MAX_EVIDENCIAS_POR_TERMO = 3          # evita despejar 200 ocorrências iguais no relatório

# --------------------------------------------------------------------------------------
# Fases do crédito (escada). Quanto mais abaixo, mais perto de "dívida paga".
# A fase final do processo é a MAIS ALTA que tiver evidência confiável.
# --------------------------------------------------------------------------------------
FASES = (
    ("SEM_INFORMACAO", "Nenhuma informação de fase encontrada"),
    ("SENTENCA", "Sentença/condenação proferida"),
    ("TRANSITO_EM_JULGADO", "Transitou em julgado"),
    ("CUMPRIMENTO_DE_SENTENCA", "Em cumprimento de sentença / cálculos"),
    ("REQUISICAO", "Requisição (RPV/OPV/precatório) determinada ou expedida - aguardando pagamento"),
    ("PAGAMENTO_DISPONIBILIZADO", "Valor depositado/disponibilizado - aguardando levantamento"),
    ("QUITADO", "Dívida paga/liquidada (levantamento ou extinção por pagamento)"),
)
ORDEM_FASE = {codigo: posicao for posicao, (codigo, _) in enumerate(FASES)}
DESCRICAO_FASE = dict(FASES)

# Resposta objetiva à pergunta "a dívida já foi paga?" para cada fase final.
DIVIDA_PAGA_SIM = "SIM"
DIVIDA_PAGA_PROVAVEL = "PROVAVEL"
DIVIDA_PAGA_NAO = "NAO"
DIVIDA_PAGA_SEM_INFO = "SEM_INFORMACAO"

# --------------------------------------------------------------------------------------
# DICIONÁRIO DE TERMOS:  fase -> { nome_do_termo: regex }
# O nome do termo aparece no relatório, então escolha nomes que um advogado entenda.
# Evite termos soltos como "pagamento" ou "quitação": no INSS, por exemplo, "pagamento"
# aparece 40x só falando do benefício. Prefira frases específicas.
# A chave especial "ALERTA" não é fase: gera avisos no relatório.
# --------------------------------------------------------------------------------------
DICIONARIO_TERMOS = {
    "SENTENCA": {
        "julgo_procedente": r"julgo\s+(?:parcialmente\s+)?procedentes?",
        "condeno": r"\bcondeno\b",
        "condenar_ente_publico": r"condenar\s+(?:o|a)\s+(?:INSS|Instituto|Uni[ãa]o|Estado|Munic[íi]pio|r[ée]u)",
    },
    "TRANSITO_EM_JULGADO": {
        "certifico_transito": r"certifico\s+(?:o\s+)?tr[âa]nsito\s+em\s+julgado",
        "certidao_transito": r"certid[ãa]o\s+de\s+tr[âa]nsito\s+em\s+julgado",
        "transitou_em_julgado": r"transit(?:ou|ad[oa])\s+em\s+julgado",
    },
    "CUMPRIMENTO_DE_SENTENCA": {
        "cumprimento_de_sentenca": r"cumprimento\s+de\s+senten[çc]a",
        "homologa_calculos": r"homolog\w+\s+(?:os\s+|as\s+)?(?:c[áa]lculos|contas?)",
        "homologacao_calculos": r"homologa[çc][ãa]o\s+d[eo]s?\s+(?:c[áa]lculos|contas?)",
        "conta_de_liquidacao": r"conta\s+de\s+liquida[çc][ãa]o",
    },
    "REQUISICAO": {
        "oficio_requisitorio": r"of[íi]cio\s+requisit[óo]rio",
        "oficio_requisicao_pagamento": r"of[íi]cio\s+requisi[çc][ãa]o\s+de\s+pagamento",
        "expedicao_rpv_precatorio": r"(?:expedi[çc][ãa]o|juntada)\s+de\s+(?:RPV|OPV|precat[óo]rio)",
        "expedir_precatorio": r"expedi(?:r|do|da|u)\b[^.]{0,30}precat[óo]rio",
        # Número de requisição no padrão TRF1/PJe, ex.: 2026.0000.000.000001
        "requisicao_pagamento_numerada": r"requisi[çc][ãa]o\s+de\s+pagamento\s+\d{4}\.\d{4}\.\d{3}\.\d{6}",
    },
    "PAGAMENTO_DISPONIBILIZADO": {
        "valores_depositados": (
            r"(?:valor(?:es)?|quantia|import[âa]ncia|cr[ée]dito)\s+(?:j[áa]\s+)?"
            r"(?:foi\s+|foram\s+|est[áa]\s+|est[ãa]o\s+)?(?:devidamente\s+)?"
            r"(?:depositad\w+|disponibilizad\w+|liberad\w+)"
        ),
        "deposito_efetuado": r"dep[óo]sito\s+(?:judicial\s+)?(?:foi\s+)?(?:efetuad\w+|realizad\w+|confirmad\w+)",
        "pagamento_efetuado": (
            r"pagamento\s+(?:da\s+(?:RPV|OPV|requisi[çc][ãa]o|precat[óo]rio)\s+)?(?:foi\s+)?"
            r"(?:efetuad\w+|realizad\w+|disponibilizad\w+|liberad\w+|confirmad\w+)"
        ),
        "requisicao_paga": r"\b(?:RPV|OPV|precat[óo]rio|requisi[çc][ãa]o)\s+(?:j[áa]\s+)?(?:foi\s+)?(?:paga|pago|depositad\w+|liberad\w+)",
        "alvara_expedido": r"(?:expe[çc]a-se|expedi(?:r|do|u|[çc][ãa]o\s+de))\s+(?:o\s+|um\s+)?alvar[áa]",
        "intimado_para_levantamento": r"intimad[oa]s?\s+(?:para|a)\s+(?:efetuar\s+)?(?:o\s+)?levantamento",
    },
    "QUITADO": {
        "extincao_da_execucao": (
            r"(?:extin[çc][ãa]o|extint[ao]s?|extingo)\s+(?:d[ao]s?\s+|a\s+|o\s+)?"
            r"(?:execu[çc][ãa]o|cumprimento\s+de\s+senten[çc]a|obriga[çc][ãa]o)"
        ),
        "art_924_inciso_II": r"art(?:igo|\.)?\s*924,?\s*(?:inciso\s+)?II\b",
        "satisfacao_da_obrigacao": r"satisfa[çc][ãa]o\s+(?:integral\s+)?(?:d[ao]\s+)?(?:obriga[çc][ãa]o|cr[ée]dito|d[ée]bito|d[íi]vida)",
        "levantamento_realizado": r"levantamento\s+(?:dos\s+valores\s+)?(?:foi\s+)?(?:efetuad\w+|realizad\w+|conclu[íi]d\w+|comprovad\w+)",
        "valores_levantados": r"(?:valor(?:es)?|quantia|alvar[áa])\s+(?:j[áa]\s+)?(?:foi\s+|foram\s+)?levantad\w+",
        "alvara_cumprido": r"alvar[áa]\s+(?:j[áa]\s+)?(?:foi\s+)?(?:cumprid\w+|liquidad\w+|pago)",
        "quitacao_integral": r"quita[çc][ãa]o\s+(?:integral|total|plena)|d(?:ou|[áa])\s+(?:plena\s+|total\s+|integral\s+)?quita[çc][ãa]o",
        "divida_paga": r"d[íi]vida\s+(?:foi\s+)?(?:paga|quitada|liquidada)",
    },
    "ALERTA": {
        "sentenca_improcedente": r"julgo\s+improcedentes?",
    },
}

# Se a frase ANTES do termo contém uma destas palavras, a menção é hipotética/futura/negada
# ("Aguarde-se o pagamento", "Após a expedição da RPV...", "requer a expedição...").
# Esses achados aparecem no relatório (hipotetico=True), mas NÃO mudam a fase.
CONTEXTO_HIPOTETICO = (
    r"\b(?:ap[óo]s|ser[áa]o?|caso|sob\s+pena|quando|dever[áa]o?|poder[áa]o?|aguard\w+|"
    r"requer\w*|solicit\w*|pleite\w+|eventual\w*|at[ée]\s+que|"
    r"antes\s+d[aeo]s?|condicionad\w+|mediante|fins\s+de)\b"
)
# Negação só vale se estiver COLADA no termo (ex.: "ainda não foi efetuado o pagamento").
# Mais longe ela engana: "...no que não conflitar com a Lei X, certifico o trânsito em julgado".
NEGACAO_PROXIMA = r"\b(?:n[ãa]o|sem|nenhum\w*)\b"
JANELA_NEGACAO = 25
# Fronteira de frase usada para recortar a "janela" antes do termo.
FRONTEIRA_DE_FRASE = r"(?<=[.;:!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ(])"

# Só documentos que vieram do JUÍZO valem para decidir a fase. Peças das partes (petição,
# contestação, manifestação, documentos pessoais, CNIS...) costumam REQUERER ou ALEGAR, não provar.
# Páginas sem tipo identificado (capa do PJe, PDFs do e-SAJ) são aceitas.
TIPOS_DOCUMENTO_DO_JUIZO = (
    r"senten[çc]a|decis[ãa]o|despacho|certid[ãa]o|ato\s+ordinat[óo]rio|intima[çc][ãa]o|of[íi]cio|"
    r"alvar[áa]|ac[óo]rd[ãa]o|voto|ementa|termo|mandado|edital|requisi[çc][ãa]o|expedi[çc][ãa]o|quadro-resumo"
)

# --------------------------------------------------------------------------------------
# Regex de metadados
# --------------------------------------------------------------------------------------
# Número CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO  (J = ramo da justiça, TR = tribunal)
PADRAO_CNJ = r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b"

# Capa do PJe (Justiça Federal / TJGO etc.)
REGEX_CAPA_PJE = {
    "numero_processo": r"N[úu]mero:\s*(" + PADRAO_CNJ[2:-2] + r")",
    "classe": r"Classe:\s*([^\n]+)",
    "orgao_julgador": r"[ÓO]rg[ãa]o julgador:\s*([^\n]+)",
    "valor_causa": r"Valor da causa:\s*R\$\s*([\d.]+,\d{2})",
    "ultima_distribuicao": r"[ÚU]ltima distribui[çc][ãa]o\s*:\s*(\d{2}/\d{2}/\d{4})",
    "assuntos": r"Assuntos?:\s*([^\n]+)",
}
# Data impressa no topo da capa = "posição" do processo no momento em que o PDF foi gerado.
REGEX_DATA_EMISSAO_CAPA = r"^\s*(\d{2}/\d{2}/\d{4})\s*$"

# Rodapé/cabeçalho de cada página de documento no PJe.
REGEX_PJE_CABECALHO_DOC = r"Documento id (\d+) - ([^\n]+)"
REGEX_PJE_NUM_DOC = r"Num\.\s*(\d+)\s*-\s*P[áa]g\.\s*(\d+)"
REGEX_PJE_ASSINANTE = r"Assinado eletronicamente por:\s*(.+?)\s+-\s+\d{2}/\d{2}/\d{4}"

# Partes e advogados na capa: "NOME EM MAIÚSCULAS (AUTOR)". Compilado SEM IGNORECASE.
_MAIUSC = r"A-ZÁÀÂÃÉÊÍÓÔÕÚÇ"
REGEX_PARTE_COM_PAPEL = (
    r"([" + _MAIUSC + r"][" + _MAIUSC + r"0-9 .,'&/-]+?)\s*"
    r"\((AUTOR|R[EÉ]U|REQUERENTE|REQUERIDO|EXEQUENTE|EXECUTAD[OA]|IMPETRANTE|IMPETRADO|"
    r"APELANTE|APELADO|EMBARGANTE|EMBARGADO|ADVOGADO|ADVOGADA|PROCURADOR|PROCURADORA)\)"
)
PAPEIS_ADVOGADO = {"ADVOGADO", "ADVOGADA", "PROCURADOR", "PROCURADORA"}

# TJSP/e-SAJ não tem capa estruturada: busca "Exequente: NOME," no corpo da petição.
REGEX_PARTE_ROTULO = (
    r"(Exequente|Executad[ao]|Credor[a]?|Devedor[a]?)\s*:\s*"
    r"([" + _MAIUSC + r"][" + _MAIUSC + r" .'\-\n]+?)\s*,"
)

# Fallback para Diário da Justiça: "ADV: NOME (OAB/GO 12345)" (formato do DJe — AINDA NÃO VALIDADO
# com um PDF real de Diário, ver README).
REGEX_ADVOGADO_DIARIO = r"ADV(?:OGAD[OA]S?)?\.?\s*:\s*([^\n(]+?)\s*\(?\s*OAB"

# Juiz: e-SAJ (TJSP) traz "Juiz(a) de Direito: Dr(a). NOME". No PJe o juiz é quem ASSINA a sentença.
_NOME = r"[" + _MAIUSC + r"]+(?: [" + _MAIUSC + r"]+)*"
REGEX_JUIZ_ESAJ = r"Juiz(?:a|\(a\))?\s+de\s+Direito:\s*Dr(?:a|\(a\))?\.\s*(" + _NOME + r")"
TIPOS_DOCUMENTO_DO_JUIZ = r"senten[çc]a|decis[ãa]o|despacho"

# OAB. Cobre "OAB/GO nº 12.345", "OAB SP - 678901", "OAB: 678901/SP", "OAB 678901/SP".
# Compilados SEM IGNORECASE ("OAB" e UF em maiúsculas).
REGEX_OAB_UF_PRIMEIRO = r"OAB\s*[/:\-]?\s*([A-Z]{2})\s*(?:n[º°o.]*\s*)?[:\-]?\s*(\d{1,3}(?:\.\d{3})+|\d{3,7})"
REGEX_OAB_NUMERO_PRIMEIRO = r"OAB\s*[:\-]?\s*(?:n[º°o.]*\s*)?(\d{1,3}(?:\.\d{3})+|\d{3,7})\s*[/\-]\s*([A-Z]{2})"
TOP_OAB = 5

# Valor requisitado (RPV/OPV/precatório), em ordem de prioridade.
REGEX_VALOR_REQUISITADO = (
    r"Valor\s+Total\s+do\s+Benefici[áa]rio:\s*R\$\s*([\d.]+,\d{2})",
    r"Valor\s+global\s+da\s+(?:OPV|RPV|requisi[çc][ãa]o)\s*:\s*R\$\s*([\d.]+,\d{2})",
    r"Valor\s+total\s+(?:da\s+)?requisi[çc][ãa]o\s*:?\s*R\$\s*([\d.]+,\d{2})",
)

# --------------------------------------------------------------------------------------
# Tribunal a partir do número CNJ  (Resolução CNJ 65/2008)
# --------------------------------------------------------------------------------------
TRIBUNAIS_ESTADUAIS = {
    "01": "TJAC", "02": "TJAL", "03": "TJAP", "04": "TJAM", "05": "TJBA", "06": "TJCE",
    "07": "TJDFT", "08": "TJES", "09": "TJGO", "10": "TJMA", "11": "TJMT", "12": "TJMS",
    "13": "TJMG", "14": "TJPA", "15": "TJPB", "16": "TJPR", "17": "TJPE", "18": "TJPI",
    "19": "TJRJ", "20": "TJRN", "21": "TJRS", "22": "TJRO", "23": "TJRR", "24": "TJSC",
    "25": "TJSE", "26": "TJSP", "27": "TJTO",
}
TRIBUNAIS_FEDERAIS = {"01": "TRF1", "02": "TRF2", "03": "TRF3", "04": "TRF4", "05": "TRF5", "06": "TRF6"}
TRIBUNAIS_POR_RAMO = {"8": TRIBUNAIS_ESTADUAIS, "4": TRIBUNAIS_FEDERAIS}

# --------------------------------------------------------------------------------------
# Compilação (feita uma vez, na importação)
# --------------------------------------------------------------------------------------
_I = re.IGNORECASE


def _compilar_dicionario(dicionario):
    """Transforma {fase: {termo: regex}} em lista de tuplas (fase, termo, regex_compilado)."""
    return [(fase, termo, re.compile(padrao, _I)) for fase, termos in dicionario.items() for termo, padrao in termos.items()]


TERMOS_COMPILADOS = _compilar_dicionario(DICIONARIO_TERMOS)

RE_CNJ = re.compile(PADRAO_CNJ)
RE_CAPA_PJE = {chave: re.compile(padrao, _I) for chave, padrao in REGEX_CAPA_PJE.items()}
RE_DATA_EMISSAO_CAPA = re.compile(REGEX_DATA_EMISSAO_CAPA, re.MULTILINE)
RE_PJE_CABECALHO_DOC = re.compile(REGEX_PJE_CABECALHO_DOC)
RE_PJE_NUM_DOC = re.compile(REGEX_PJE_NUM_DOC, _I)
RE_PJE_ASSINANTE = re.compile(REGEX_PJE_ASSINANTE)
RE_PARTE_COM_PAPEL = re.compile(REGEX_PARTE_COM_PAPEL)           # sem IGNORECASE
RE_PARTE_ROTULO = re.compile(REGEX_PARTE_ROTULO, re.MULTILINE)   # sem IGNORECASE no nome
RE_ADVOGADO_DIARIO = re.compile(REGEX_ADVOGADO_DIARIO)
RE_JUIZ_ESAJ = re.compile(REGEX_JUIZ_ESAJ)                       # sem IGNORECASE no nome
RE_TIPO_DOC_DO_JUIZ = re.compile(TIPOS_DOCUMENTO_DO_JUIZ, _I)
RE_OAB_UF_PRIMEIRO = re.compile(REGEX_OAB_UF_PRIMEIRO)
RE_OAB_NUMERO_PRIMEIRO = re.compile(REGEX_OAB_NUMERO_PRIMEIRO)
RE_VALOR_REQUISITADO = [re.compile(p, _I) for p in REGEX_VALOR_REQUISITADO]
RE_CONTEXTO_HIPOTETICO = re.compile(CONTEXTO_HIPOTETICO, _I)
RE_NEGACAO_PROXIMA = re.compile(NEGACAO_PROXIMA, _I)
RE_FRONTEIRA_DE_FRASE = re.compile(FRONTEIRA_DE_FRASE)
RE_TIPO_DOC_DO_JUIZO = re.compile(TIPOS_DOCUMENTO_DO_JUIZO, _I)
