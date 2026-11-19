import { Check } from "lucide-react";
import type { Fase } from "@/lib/tipos";
import { Esqueleto } from "./ui";

/**
 * A "escada" do crédito: sentença → ... → quitado. Mostra até onde o processo chegou.
 * Vertical no celular, horizontal a partir de md. `fases` vem da API (a mesma ordem do dicionário).
 */
export function EscadaFases({ fases, atual }: { fases: Fase[] | null; atual: string }) {
  if (!fases) return <Esqueleto className="h-24" />;

  const etapas = fases.filter((fase) => fase.ordem > 0); // ordem 0 = "sem informação"
  const ordemAtual = fases.find((fase) => fase.codigo === atual)?.ordem ?? 0;

  return (
    <div>
      <ol className="grid md:grid-cols-6">
        {etapas.map((etapa, indice) => {
          const estado = etapa.ordem < ordemAtual ? "feita" : etapa.ordem === ordemAtual ? "atual" : "pendente";
          const circulo =
            estado === "pendente"
              ? "border-2 border-border bg-surface text-muted"
              : estado === "atual"
                ? "bg-accent text-accent-foreground ring-4 ring-accent-soft"
                : "bg-accent text-accent-foreground";
          return (
            <li
              key={etapa.codigo}
              aria-current={estado === "atual" ? "step" : undefined}
              title={etapa.descricao}
              className="relative flex gap-3 pb-4 last:pb-0 md:flex-col md:items-center md:gap-2 md:pb-0 md:text-center"
            >
              {indice < etapas.length - 1 && (
                <span
                  aria-hidden
                  className={`absolute left-4 top-8 bottom-0 w-0.5 -translate-x-1/2 md:bottom-auto md:left-1/2 md:top-4 md:h-0.5 md:w-full md:translate-x-0 md:-translate-y-1/2 ${
                    estado === "feita" ? "bg-accent" : "bg-border"
                  }`}
                />
              )}
              <span className={`relative z-10 grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold ${circulo}`}>
                {estado === "feita" ? <Check aria-hidden className="size-4" /> : indice + 1}
              </span>
              <span className="min-w-0 pt-1 md:px-2 md:pt-0">
                <span className={`block text-sm ${estado === "atual" ? "font-semibold" : estado === "feita" ? "" : "text-muted"}`}>
                  {etapa.rotulo}
                </span>
                <span className="sr-only">
                  {estado === "atual" ? "(fase atual)" : estado === "feita" ? "(etapa já alcançada)" : "(ainda não alcançada)"}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
      {ordemAtual === 0 && (
        <p className="mt-4 text-sm text-muted">Nenhuma fase foi identificada neste PDF.</p>
      )}
    </div>
  );
}
