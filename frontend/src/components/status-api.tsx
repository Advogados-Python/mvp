"use client";

import { useEffect, useState } from "react";
import { API_URL, api } from "@/lib/api";

type Estado = "verificando" | "online" | "offline";

const VISUAL: Record<Estado, { texto: string; ponto: string }> = {
  verificando: { texto: "Verificando API…", ponto: "bg-neutral" },
  online: { texto: "API conectada", ponto: "bg-ok" },
  offline: { texto: "API offline", ponto: "bg-danger" },
};

/** Mostra no cabeçalho se o frontend está conseguindo falar com a API (confere a cada 20 s). */
export function StatusApi() {
  const [estado, setEstado] = useState<Estado>("verificando");

  useEffect(() => {
    let ativo = true;
    const verificar = () =>
      api
        .saude()
        .then(() => ativo && setEstado("online"))
        .catch(() => ativo && setEstado("offline"));
    verificar();
    const intervalo = setInterval(verificar, 20_000);
    return () => {
      ativo = false;
      clearInterval(intervalo);
    };
  }, []);

  const { texto, ponto } = VISUAL[estado];
  return (
    <span
      role="status"
      title={API_URL}
      className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-muted sm:px-3"
    >
      <span aria-hidden className={`size-2 rounded-full ${ponto}`} />
      {/* No celular fica só o ponto colorido (o texto segue disponível para leitores de tela). */}
      <span className="sr-only sm:not-sr-only">{texto}</span>
    </span>
  );
}
