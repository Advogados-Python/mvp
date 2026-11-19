"""Os termos que identificam a QUITAÇÃO (dívida paga: levantamento ou extinção por pagamento): {nome do termo: expressão regular}."""

TERMOS = {
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
}
