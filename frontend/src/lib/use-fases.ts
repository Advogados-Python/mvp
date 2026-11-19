"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import { humanizar } from "./formatar";
import type { Fases } from "./tipos";

// A escada de fases é a mesma para todas as telas: busca uma vez e reaproveita.
let emCache: Promise<Fases> | null = null;

function carregar(): Promise<Fases> {
  emCache ??= api.fases().catch((erro) => {
    emCache = null; // não guarda a falha: a próxima tela tenta de novo
    throw erro;
  });
  return emCache;
}

/** Devolve a escada de fases da API, ou null enquanto carrega (ou se a API falhar). */
export function useFases(): Fases | null {
  const [fases, setFases] = useState<Fases | null>(null);

  useEffect(() => {
    let ativo = true;
    carregar()
      .then((dados) => ativo && setFases(dados))
      .catch(() => {}); // sem fases a tela usa o código da fase como rótulo
    return () => {
      ativo = false;
    };
  }, []);

  return fases;
}

export function rotuloDaFase(fases: Fases | null, codigo: string): string {
  const achada = fases?.fases.find((fase) => fase.codigo === codigo);
  if (achada) return achada.rotulo;
  return codigo === "ALERTA" ? "Alerta" : humanizar(codigo);
}
