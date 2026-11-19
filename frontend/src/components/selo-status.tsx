import { CircleX, Clock, LoaderCircle } from "lucide-react";
import type { ResumoProcesso } from "@/lib/tipos";
import { SeloDivida } from "./selo-divida";
import { TOM } from "./ui";

/** Estado da análise enquanto ela não terminou (ou se falhou). */
export function SeloStatus({ status }: { status: ResumoProcesso["status"] }) {
  const base = "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold";
  if (status === "PENDENTE") {
    return (
      <span className={`${base} ${TOM.neutral}`}>
        <Clock aria-hidden className="size-3.5" />
        Na fila
      </span>
    );
  }
  if (status === "ANALISANDO") {
    return (
      <span className={`${base} ${TOM.info}`}>
        <LoaderCircle aria-hidden className="size-3.5 animate-spin" />
        Analisando…
      </span>
    );
  }
  if (status === "FALHOU") {
    return (
      <span className={`${base} ${TOM.danger}`}>
        <CircleX aria-hidden className="size-3.5" />
        Falhou
      </span>
    );
  }
  return null;
}

/** O que mostrar como "resultado" de um processo: a resposta de dívida paga, ou o estado da análise. */
export function SeloProcesso({ processo }: { processo: Pick<ResumoProcesso, "status" | "divida_paga"> }) {
  if (processo.status === "CONCLUIDO") return <SeloDivida valor={processo.divida_paga ?? "SEM_INFORMACAO"} />;
  return <SeloStatus status={processo.status} />;
}
