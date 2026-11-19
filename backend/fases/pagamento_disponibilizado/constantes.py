"""Os termos que identificam o PAGAMENTO DISPONIBILIZADO (valor depositado, aguardando levantamento): {nome do termo: expressão regular}."""

TERMOS = {
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
}
