"""As regex e as tabelas da fase 3 (identificar o processo). Toda a regra desta fase mora aqui."""

import re

PAGINAS_DA_CAPA = 6                   # a capa do PJe (partes, advogados) fica nas primeiras páginas

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
