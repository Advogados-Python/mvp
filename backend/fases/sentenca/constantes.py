"""Os termos que identificam a SENTENÇA nos autos: {nome do termo: expressão regular}. Para ensinar um termo novo, acrescente uma linha."""

TERMOS = {
    "julgo_procedente": r"julgo\s+(?:parcialmente\s+)?procedentes?",
    "condeno": r"\bcondeno\b",
    "condenar_ente_publico": r"condenar\s+(?:o|a)\s+(?:INSS|Instituto|Uni[ãa]o|Estado|Munic[íi]pio|r[ée]u)",
}
