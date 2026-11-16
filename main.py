"""Ponto de entrada do MVP.

Uso:
    python main.py                       # processa todos os PDFs de input/
    python main.py input/processo.pdf    # processa um PDF (ou vários)
    python main.py --saida resultados    # grava em outra pasta (padrão: output/)
"""

import argparse
import sys
import time
from pathlib import Path

from app import (
    PASTA_INPUT, PASTA_OUTPUT, ErroRibeiro,
    exportar_csv, exportar_json, formatar_resumo, listar_pdfs, processar_pdf,
)


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Extrai dados de PDFs de processos e diz se a dívida foi paga.")
    parser.add_argument("pdfs", nargs="*", type=Path, help=f"PDFs a processar (padrão: todos de {PASTA_INPUT.name}/)")
    parser.add_argument("--saida", type=Path, default=PASTA_OUTPUT, help=f"pasta de saída (padrão: {PASTA_OUTPUT.name}/)")
    return parser.parse_args()


def main() -> int:
    args = ler_argumentos()
    pdfs = args.pdfs or listar_pdfs(PASTA_INPUT)
    if not pdfs:
        print(f"Nenhum PDF encontrado em {PASTA_INPUT}/. Coloque os arquivos lá ou passe o caminho.")
        return 1

    resultados, falhas = [], 0
    for pdf in pdfs:
        inicio = time.time()
        try:
            resultado = processar_pdf(pdf)
        except ErroRibeiro as erro:  # um PDF ruim não derruba o lote
            print(f"[ERRO] {pdf.name}: {erro}\n")
            falhas += 1
            continue
        exportar_json(resultado, args.saida)
        resultados.append(resultado)
        print(formatar_resumo(resultado))
        print(f"  ({time.time() - inicio:.1f}s)\n")

    if resultados:
        csv_gerado = exportar_csv(resultados, args.saida)
        print(f"{len(resultados)} processo(s) analisado(s), {falhas} falha(s). Resumo: {csv_gerado}")
    return 1 if falhas and not resultados else 0


if __name__ == "__main__":
    sys.exit(main())
