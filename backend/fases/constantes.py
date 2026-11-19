from .modelos import RespostaDividaPaga

# Mesma tabela do README ("Como ler divida_paga"): resposta -> (significado, ação sugerida).
SIGNIFICADO_DIVIDA_PAGA = {
    RespostaDividaPaga.SIM: ("Há evidência de levantamento ou extinção por pagamento.", "Conferir a página indicada."),
    RespostaDividaPaga.PROVAVEL: (
        "Valor depositado ou disponibilizado; falta confirmar o levantamento.",
        "Conferir a página indicada.",
    ),
    RespostaDividaPaga.NAO: ("O crédito ainda não foi pago; a fase diz em que ponto está.", "Acompanhar a fase."),
    RespostaDividaPaga.SEM_INFORMACAO: ("Nenhum termo de fase foi encontrado no PDF.", "Ler o PDF e verificar os avisos."),
}
