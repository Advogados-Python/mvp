"""Os termos que identificam o CUMPRIMENTO DE SENTENÇA (e a fase de cálculos) nos autos: {nome do termo: expressão regular}."""

TERMOS = {
    "cumprimento_de_sentenca": r"cumprimento\s+de\s+senten[çc]a",
    "homologa_calculos": r"homolog\w+\s+(?:os\s+|as\s+)?(?:c[áa]lculos|contas?)",
    "homologacao_calculos": r"homologa[çc][ãa]o\s+d[eo]s?\s+(?:c[áa]lculos|contas?)",
    "conta_de_liquidacao": r"conta\s+de\s+liquida[çc][ãa]o",
}
