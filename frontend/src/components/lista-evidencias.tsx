"use client";

import { useMemo, useState } from "react";
import { humanizar } from "@/lib/formatar";
import type { Evidencia, Fases } from "@/lib/tipos";
import { rotuloDaFase } from "@/lib/use-fases";
import { BotaoPdf } from "./botao-pdf";
import { Chip } from "./ui";

type Visao = "contam" | "ignoradas" | "todas";

// Apresentação progressiva: autos grandes geram centenas de achados. Mostra os primeiros e o resto sob demanda.
const LIMITE_INICIAL = 10;
const PASSO_DE_EXPANSAO = 20;

/** Evidências agrupadas por fase, da mais avançada para a mais inicial ("ALERTA" fica no topo). */
export function ListaEvidencias({
  evidencias,
  idProcesso,
  fases,
}: {
  evidencias: Evidencia[];
  idProcesso: string;
  fases: Fases | null;
}) {
  const contam = evidencias.filter((ev) => ev.conta).length;
  const ignoradas = evidencias.length - contam;
  const [visao, setVisao] = useState<Visao>(contam > 0 ? "contam" : "todas");
  const [limite, setLimite] = useState(LIMITE_INICIAL);

  const grupos = useMemo(() => {
    const ordemDe = (codigo: string) =>
      codigo === "ALERTA" ? Number.MAX_SAFE_INTEGER : (fases?.fases.find((fase) => fase.codigo === codigo)?.ordem ?? -1);
    const filtradas = evidencias.filter((ev) => visao === "todas" || (visao === "contam" ? ev.conta : !ev.conta));
    const porFase = new Map<string, Evidencia[]>();
    for (const ev of filtradas) porFase.set(ev.fase, [...(porFase.get(ev.fase) ?? []), ev]);
    return [...porFase.entries()].sort(([a], [b]) => ordemDe(b) - ordemDe(a));
  }, [evidencias, fases, visao]);

  const totalNaVisao = grupos.reduce((soma, [, itens]) => soma + itens.length, 0);
  const gruposVisiveis = grupos.reduce<{ fase: string; total: number; mostrados: Evidencia[] }[]>((lista, [fase, itens]) => {
    const jaMostradas = lista.reduce((soma, grupo) => soma + grupo.mostrados.length, 0);
    const mostrados = itens.slice(0, Math.max(0, limite - jaMostradas));
    return mostrados.length > 0 ? [...lista, { fase, total: itens.length, mostrados }] : lista;
  }, []);
  const escondidas = totalNaVisao - Math.min(limite, totalNaVisao);

  const opcoes: { valor: Visao; rotulo: string; quantidade: number }[] = [
    { valor: "contam", rotulo: "Que decidem a fase", quantidade: contam },
    { valor: "ignoradas", rotulo: "Ignoradas", quantidade: ignoradas },
    { valor: "todas", rotulo: "Todas", quantidade: evidencias.length },
  ];

  return (
    <div>
      <div role="group" aria-label="Filtrar evidências" className="mb-4 flex flex-wrap gap-2">
        {opcoes.map((opcao) => (
          <button
            key={opcao.valor}
            type="button"
            aria-pressed={visao === opcao.valor}
            onClick={() => {
              setVisao(opcao.valor);
              setLimite(LIMITE_INICIAL);
            }}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              visao === opcao.valor
                ? "border-accent bg-accent text-accent-foreground"
                : "border-border bg-surface text-muted hover:border-accent hover:text-foreground"
            }`}
          >
            {opcao.rotulo} ({opcao.quantidade})
          </button>
        ))}
      </div>

      {visao === "ignoradas" && (
        <p className="mb-4 text-sm text-muted">
          Aparecem aqui os achados que <strong>não</strong> mudaram a fase: frases condicionais ou futuras (“após o pagamento, será
          intimada…”) e trechos de peças das partes. Confira se algum deles era um pagamento de verdade.
        </p>
      )}

      {grupos.length === 0 ? (
        <p className="rounded-xl bg-surface-2 px-4 py-6 text-center text-sm text-muted">Nenhuma evidência nesta visão.</p>
      ) : (
        <div className="space-y-6">
          {gruposVisiveis.map(({ fase, total, mostrados }) => (
            <section key={fase} aria-labelledby={`fase-${fase}`}>
              <h3 id={`fase-${fase}`} className="mb-2 text-sm font-semibold">
                {rotuloDaFase(fases, fase)} <span className="font-normal text-muted">({total})</span>
              </h3>
              <ul className="space-y-3">
                {mostrados.map((ev, indice) => (
                  <li key={`${ev.termo}-${ev.pagina}-${indice}`} className="rounded-xl border border-border bg-surface-2 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium" title={ev.termo}>
                        {humanizar(ev.termo)}
                      </span>
                      <BotaoPdf id={idProcesso} pagina={ev.pagina}>
                        pág. {ev.pagina}
                      </BotaoPdf>
                      {ev.tipo_documento && <Chip>{ev.tipo_documento}</Chip>}
                      {ev.hipotetico && <Chip tom="warn">Condicional ou futuro</Chip>}
                      {!ev.origem_confiavel && <Chip tom="warn">Peça da parte</Chip>}
                    </div>
                    <blockquote className="mt-2 border-l-2 border-border pl-3 text-sm leading-relaxed text-muted [overflow-wrap:anywhere]">
                      …{ev.trecho}…
                    </blockquote>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {escondidas > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setLimite((atual) => atual + PASSO_DE_EXPANSAO)}
                className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent"
              >
                Mostrar mais {Math.min(PASSO_DE_EXPANSAO, escondidas)}
              </button>
              {escondidas > PASSO_DE_EXPANSAO && (
                <button type="button" onClick={() => setLimite(totalNaVisao)} className="text-sm text-muted underline underline-offset-2 hover:text-foreground">
                  Mostrar todas ({escondidas} restantes)
                </button>
              )}
              <span className="text-xs text-muted">
                Mostrando {totalNaVisao - escondidas} de {totalNaVisao}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
