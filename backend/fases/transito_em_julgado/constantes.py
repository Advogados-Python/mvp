"""Os termos que identificam o TRÂNSITO EM JULGADO nos autos: {nome do termo: expressão regular}."""

TERMOS = {
    "certifico_transito": r"certifico\s+(?:o\s+)?tr[âa]nsito\s+em\s+julgado",
    "certidao_transito": r"certid[ãa]o\s+de\s+tr[âa]nsito\s+em\s+julgado",
    "transitou_em_julgado": r"transit(?:ou|ad[oa])\s+em\s+julgado",
}
