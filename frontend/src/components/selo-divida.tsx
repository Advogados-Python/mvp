import { CircleCheck, CircleDashed, CircleHelp, Clock, type LucideIcon } from "lucide-react";
import type { DividaPaga } from "@/lib/tipos";
import { TOM, type Tom } from "./ui";

// Cor + ícone + texto: o significado nunca depende só da cor.
// Atenção ao ler: "Ainda não paga" é a situação neutra (crédito em aberto), não um erro.
export const DIVIDA: Record<DividaPaga, { rotulo: string; tom: Tom; Icone: LucideIcon }> = {
  SIM: { rotulo: "Paga", tom: "ok", Icone: CircleCheck },
  PROVAVEL: { rotulo: "Provavelmente paga", tom: "warn", Icone: CircleDashed },
  NAO: { rotulo: "Ainda não paga", tom: "info", Icone: Clock },
  SEM_INFORMACAO: { rotulo: "Sem informação", tom: "neutral", Icone: CircleHelp },
};

export const ORDEM_DIVIDA: DividaPaga[] = ["SIM", "PROVAVEL", "NAO", "SEM_INFORMACAO"];

export function SeloDivida({ valor, grande = false }: { valor: DividaPaga; grande?: boolean }) {
  const { rotulo, tom, Icone } = DIVIDA[valor] ?? DIVIDA.SEM_INFORMACAO;
  const tamanho = grande ? "gap-2 px-4 py-2 text-lg" : "gap-1.5 px-2.5 py-1 text-xs";
  return (
    <span className={`inline-flex items-center rounded-full font-semibold ${TOM[tom]} ${tamanho}`}>
      <Icone aria-hidden className={grande ? "size-6" : "size-3.5"} />
      {rotulo}
    </span>
  );
}
