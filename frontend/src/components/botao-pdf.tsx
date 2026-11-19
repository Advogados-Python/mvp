"use client";

import { ExternalLink } from "lucide-react";
import { useState, type ReactNode } from "react";
import { abrirPdf } from "@/lib/api";

/** Abre o PDF numa nova aba (opcionalmente numa página) usando um link assinado de vida curta. */
export function BotaoPdf({
  id,
  pagina,
  className = "inline-flex items-center gap-1 rounded-md bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent hover:underline",
  children,
}: {
  id: string;
  pagina?: number;
  className?: string;
  children: ReactNode;
}) {
  const [erro, setErro] = useState<string | null>(null);

  return (
    <>
      <button
        type="button"
        className={className}
        onClick={() => {
          setErro(null);
          abrirPdf(id, pagina).catch((falha: Error) => setErro(falha.message));
        }}
      >
        {children}
        <ExternalLink aria-hidden className="size-3" />
        <span className="sr-only">(abre o PDF em nova aba)</span>
      </button>
      {erro && (
        <span role="alert" className="text-xs text-danger">
          {erro}
        </span>
      )}
    </>
  );
}
