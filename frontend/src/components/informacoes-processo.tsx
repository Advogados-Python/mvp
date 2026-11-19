"use client";

import { useId, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { formatarBytes, formatarDataHora, humanizar } from "@/lib/formatar";
import type { Parte, Processo } from "@/lib/tipos";
import { Recolhivel } from "./recolhivel";
import { Cartao } from "./ui";

function Campo({ rotulo, children, className = "" }: { rotulo: string; children: ReactNode; className?: string }) {
  return (
    <div className={`min-w-0 ${className}`}>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{rotulo}</dt>
      <dd className="mt-0.5 text-sm [overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

const ou = (valor: string | null | undefined) => valor || <span className="text-muted">Não identificado</span>;

/** As partes agrupadas pelo papel que o leitor extraiu (autor, réu, exequente...), na ordem em que aparecem. */
function partesPorPapel(partes: Parte[]): [string, string[]][] {
  const grupos = new Map<string, string[]>();
  for (const parte of partes) grupos.set(parte.papel, [...(grupos.get(parte.papel) ?? []), parte.nome]);
  return [...grupos];
}

/**
 * Os dados que identificam o processo, em duas camadas: um resumo sempre visível (partes, juiz(a), valor requisitado)
 * e, numa seção expansível, o complemento (órgão julgador, valor da causa, advogados, OAB, posição e arquivo).
 */
export function InformacoesProcesso({ processo }: { processo: Processo }) {
  const [aberto, setAberto] = useState(false);
  const idRegiao = useId();
  const grupos = partesPorPapel(processo.partes);

  return (
    <Cartao compacto titulo="Informações do processo" descricao="Dados extraídos dos autos.">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 lg:grid-cols-4">
        {grupos.length === 0 ? (
          <Campo rotulo="Partes" className="col-span-2 sm:col-span-1">
            {ou(null)}
          </Campo>
        ) : (
          grupos.map(([papel, nomes]) => (
            <Campo key={papel} rotulo={humanizar(papel)} className="col-span-2 sm:col-span-1">
              {nomes.length === 1 ? (
                nomes[0]
              ) : (
                <ul className="space-y-0.5">
                  {nomes.map((nome) => (
                    <li key={nome}>{nome}</li>
                  ))}
                </ul>
              )}
            </Campo>
          ))
        )}
        <Campo rotulo="Juiz(a)">{ou(processo.juiz)}</Campo>
        <Campo rotulo="Valor requisitado">{ou(processo.valor_requisitado)}</Campo>
      </dl>

      <button
        type="button"
        aria-expanded={aberto}
        aria-controls={idRegiao}
        onClick={() => setAberto((atual) => !atual)}
        className="mt-3 flex w-full items-center gap-2 rounded-md border-t border-border pt-3 text-left text-sm"
      >
        <ChevronDown aria-hidden className={`size-4 shrink-0 text-muted transition-transform duration-300 ${aberto ? "rotate-180" : ""}`} />
        <span className="shrink-0 whitespace-nowrap font-medium">Mais informações</span>
        <span className="min-w-0 truncate text-muted">Órgão julgador, valor da causa, advogados, OAB e arquivo</span>
      </button>
      <Recolhivel aberto={aberto} id={idRegiao}>
        <dl className="grid gap-x-6 gap-y-3 pt-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo rotulo="Órgão julgador">{ou(processo.orgao_julgador)}</Campo>
          <Campo rotulo="Valor da causa">{ou(processo.valor_causa)}</Campo>
          <Campo rotulo="Advogados">{processo.advogados.length === 0 ? ou(null) : processo.advogados.join("; ")}</Campo>
          <Campo rotulo="OAB (mais citadas)">{processo.oabs.length === 0 ? ou(null) : processo.oabs.join("; ")}</Campo>
          <Campo rotulo="Posição do processo">{processo.data_emissao_pdf ? `PDF gerado em ${processo.data_emissao_pdf}` : ou(null)}</Campo>
          <Campo rotulo="Arquivo" className="sm:col-span-2 lg:col-span-3">
            {processo.arquivo}{" "}
            <span className="text-muted">
              · {formatarBytes(processo.tamanho_bytes)} · Analisado em {formatarDataHora(processo.concluido_em ?? processo.criado_em)}
            </span>
          </Campo>
        </dl>
      </Recolhivel>
    </Cartao>
  );
}
