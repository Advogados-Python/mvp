"""Constantes do MVP: caminhos, parâmetros, DICIONÁRIO DE TERMOS e expressões regulares.

Toda a "regra de negócio" mora aqui. Para ensinar o sistema a reconhecer um termo novo,
basta acrescentar uma linha em DICIONARIO_TERMOS — não é preciso mexer em funcoes.py.

Convenção: os padrões são escritos como texto (r"...") e compilados no final do arquivo
com re.IGNORECASE. Os padrões de nomes próprios em MAIÚSCULAS são compilados sem
IGNORECASE de propósito (senão "de", "da" casariam com [A-Z]).
"""

import re
from pathlib import Path

from ..fases import registro as _fases
from ..fases.modelos import RespostaDividaPaga

# --------------------------------------------------------------------------------------
# Caminhos e parâmetros
# --------------------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent.parent  # backend/leitor/constantes.py -> raiz do projeto
PASTA_INPUT = RAIZ / "input"
PASTA_OUTPUT = RAIZ / "output"

MIN_CARACTERES_PAGINA = 30            # página com menos texto que isso é tratada como "sem texto" (scan)
PERCENTUAL_SEM_TEXTO_PARA_ALERTA = 0.5  # se >= 50% das páginas estão sem texto, avisa que precisa de OCR
PAGINAS_DA_CAPA = 6                   # a capa do PJe (partes, advogados) fica nas primeiras páginas

# Etapas que o pipeline informa a quem o chama (parâmetro `aviso` de processar_pdf). São a ordem real de execução.
ETAPA_LENDO_PDF = "LENDO_PDF"                  # ler_pdf: texto de cada página (informa página a página)
ETAPA_IDENTIFICANDO = "IDENTIFICANDO"          # extrair_metadados: número, tribunal, partes, juiz...
ETAPA_ANALISANDO_FASES = "ANALISANDO_FASES"    # buscar_termos: dicionário de termos (informa página a página)
ETAPA_VALIDANDO = "VALIDANDO"                  # classificar_fase + dívida paga + avisos (só evidências que "contam" decidem)

TAMANHO_TRECHO = 240                  # caracteres de contexto guardados em cada evidência
JANELA_CONTEXTO = 110                 # quantos caracteres olhar para trás ao testar "contexto hipotético"
MAX_EVIDENCIAS_POR_TERMO = 3          # evita despejar 200 ocorrências iguais no relatório

# --------------------------------------------------------------------------------------
# Fases do crédito (escada) e DICIONÁRIO DE TERMOS.
# Cada fase mora no seu próprio módulo, em backend/fases/<fase>/ (a classe em modelos.py, os termos em constantes.py, a API em
# rotas.py). Aqui o leitor só LÊ o que o registro das fases montou, com os mesmos nomes de sempre.
# A fase final do processo é a MAIS ALTA da escada que tiver evidência confiável.
# Para ensinar um termo novo, acrescente uma linha em backend/fases/<fase>/constantes.py.
# --------------------------------------------------------------------------------------
FASES = tuple((fase.codigo, fase.descricao) for fase in _fases.ESCADA)   # (código, descrição), do ponto de partida até "quitado"
ORDEM_FASE = {fase.codigo: fase.ordem for fase in _fases.ESCADA}
DESCRICAO_FASE = dict(FASES)

# Resposta objetiva à pergunta "a dívida já foi paga?" para cada fase final (cada fase declara a sua em modelos.py).
DIVIDA_PAGA_SIM = RespostaDividaPaga.SIM.value
DIVIDA_PAGA_PROVAVEL = RespostaDividaPaga.PROVAVEL.value
DIVIDA_PAGA_NAO = RespostaDividaPaga.NAO.value
DIVIDA_PAGA_SEM_INFO = RespostaDividaPaga.SEM_INFORMACAO.value

# {fase: {nome_do_termo: regex}}. O nome do termo aparece no relatório, então os nomes são pensados para um advogado entender.
# Evite termos soltos como "pagamento" ou "quitação": no INSS, por exemplo, "pagamento" aparece 40x só falando do benefício.
# A chave especial "ALERTA" não é fase: gera avisos no relatório.
DICIONARIO_TERMOS = _fases.dicionario_de_termos()

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
