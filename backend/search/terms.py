"""O que a fase 4 procura e como julga cada achado.

Para ensinar um termo novo, acrescente uma linha no DICIONARIO_TERMOS, na fase do crédito certa. O nome do termo aparece no
relatório, então escolha nomes que um advogado entenda. Evite termos soltos como "pagamento" ou "quitação": no INSS, por
exemplo, "pagamento" aparece 40x só falando do benefício. Prefira frases específicas.
A chave especial "ALERTA" não é fase: gera avisos no relatório.
"""

import re

TAMANHO_TRECHO = 240                  # caracteres de contexto guardados em cada evidência
JANELA_CONTEXTO = 110                 # quantos caracteres olhar para trás ao testar "contexto hipotético"
MAX_EVIDENCIAS_POR_TERMO = 3          # evita despejar 200 ocorrências iguais no relatório

# {código da fase do crédito: {nome_do_termo: regex}}. As fases estão em backend/validate/ladder.py, na ordem da escada.
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
# Compilação (feita uma vez, na importação)
# --------------------------------------------------------------------------------------
_I = re.IGNORECASE

# Todos os termos compilados, como (fase, termo, regex), na ordem do dicionário.
TERMOS_COMPILADOS = [(fase, termo, re.compile(padrao, _I)) for fase, termos in DICIONARIO_TERMOS.items() for termo, padrao in termos.items()]

RE_CONTEXTO_HIPOTETICO = re.compile(CONTEXTO_HIPOTETICO, _I)
RE_NEGACAO_PROXIMA = re.compile(NEGACAO_PROXIMA, _I)
RE_FRONTEIRA_DE_FRASE = re.compile(FRONTEIRA_DE_FRASE)
RE_TIPO_DOC_DO_JUIZO = re.compile(TIPOS_DOCUMENTO_DO_JUIZO, _I)
