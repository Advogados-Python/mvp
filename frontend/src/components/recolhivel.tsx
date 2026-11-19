"use client";

import { useId, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

/**
 * Região que abre e fecha com transição de altura (grid 0fr → 1fr). Fechada, fica `inert`: sem foco por teclado e fora
 * da árvore de acessibilidade, mas continua montada (o estado do que está dentro, como filtros, não se perde).
 */
export function Recolhivel({ aberto, id, children }: { aberto: boolean; id?: string; children: ReactNode }) {
  return (
    <div
      id={id}
      inert={!aberto}
      className={`grid transition-[grid-template-rows,opacity] duration-300 ease-out ${
        aberto ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
      }`}
    >
      {/* -m-1 p-1: folga para o contorno de foco dos filhos não ser cortado pelo overflow-hidden */}
      <div className="-m-1 min-h-0 overflow-hidden p-1">{children}</div>
    </div>
  );
}

/** Cartão cujo cabeçalho inteiro é o botão de abrir/fechar. `resumo` aparece ao lado do título mesmo fechado. */
export function CartaoRecolhivel({
  titulo,
  descricao,
  resumo,
  abertoInicialmente = true,
  children,
  className = "",
  compacto = false,
}: {
  titulo: string;
  descricao?: string;
  resumo?: ReactNode;
  abertoInicialmente?: boolean;
  children: ReactNode;
  className?: string;
  /** Menos respiro interno (a mesma medida do `Cartao compacto`). */
  compacto?: boolean;
}) {
  const [aberto, setAberto] = useState(abertoInicialmente);
  const idRegiao = useId();

  return (
    <section className={`vidro rounded-2xl ${className}`}>
      <h2>
        <button
          type="button"
          aria-expanded={aberto}
          aria-controls={idRegiao}
          onClick={() => setAberto((atual) => !atual)}
          className={`flex w-full items-start gap-3 rounded-2xl text-left ${compacto ? "p-3 sm:p-4" : "p-5 sm:p-6"}`}
        >
          <span className="min-w-0 flex-1">
            <span className="block text-base font-semibold">{titulo}</span>
            {descricao && <span className="mt-0.5 block text-sm font-normal text-muted">{descricao}</span>}
          </span>
          {resumo && <span className="mt-0.5 hidden shrink-0 text-xs font-normal text-muted sm:block">{resumo}</span>}
          <ChevronDown
            aria-hidden
            className={`mt-0.5 size-5 shrink-0 text-muted transition-transform duration-300 ${aberto ? "rotate-180" : ""}`}
          />
        </button>
      </h2>
      <Recolhivel aberto={aberto} id={idRegiao}>
        <div className={compacto ? "px-3 pb-3 sm:px-4 sm:pb-4" : "px-5 pb-5 sm:px-6 sm:pb-6"}>{children}</div>
      </Recolhivel>
    </section>
  );
}
