import type { ReactNode } from "react";
import { Info, TriangleAlert } from "lucide-react";

// Classes escritas por extenso para o Tailwind encontrá-las ao varrer o código.
export const TOM = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  info: "bg-info-soft text-info",
  neutral: "bg-neutral-soft text-neutral",
  danger: "bg-danger-soft text-danger",
} as const;
export type Tom = keyof typeof TOM;

const TOM_AVISO = {
  warn: "border-warn/30 bg-warn-soft [&_.titulo]:text-warn",
  danger: "border-danger/30 bg-danger-soft [&_.titulo]:text-danger",
  info: "border-info/30 bg-info-soft [&_.titulo]:text-info",
} as const;

export function Cartao({
  titulo,
  descricao,
  acao,
  children,
  className = "",
  compacto = false,
}: {
  titulo?: string;
  descricao?: string;
  acao?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Menos respiro (áreas de apoio, como o envio de PDFs). */
  compacto?: boolean;
}) {
  return (
    <section className={`vidro rounded-2xl ${compacto ? "p-3 sm:p-4" : "p-5 sm:p-6"} ${className}`}>
      {(titulo || acao) && (
        <header className={`${compacto ? "mb-3" : "mb-4"} flex flex-wrap items-start justify-between gap-3`}>
          <div>
            {titulo && <h2 className="text-base font-semibold">{titulo}</h2>}
            {descricao && <p className="mt-0.5 text-sm text-muted">{descricao}</p>}
          </div>
          {acao}
        </header>
      )}
      {children}
    </section>
  );
}

/** Faixa de destaque. `danger` usa role="alert" (leitor de tela anuncia na hora); os demais são notas. */
export function Aviso({
  tom = "warn",
  titulo,
  children,
}: {
  tom?: keyof typeof TOM_AVISO;
  titulo: string;
  children?: ReactNode;
}) {
  const Icone = tom === "info" ? Info : TriangleAlert;
  return (
    <div role={tom === "danger" ? "alert" : "note"} className={`flex gap-3 rounded-xl border p-4 ${TOM_AVISO[tom]}`}>
      <Icone aria-hidden className="titulo mt-0.5 size-5 shrink-0" />
      <div className="min-w-0 text-sm">
        <p className="titulo font-semibold">{titulo}</p>
        {children && <div className="mt-1 text-foreground">{children}</div>}
      </div>
    </div>
  );
}

export function Chip({ children, tom = "neutral" }: { children: ReactNode; tom?: Tom }) {
  return <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${TOM[tom]}`}>{children}</span>;
}

export function Esqueleto({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-lg bg-surface-2 ${className}`} />;
}

/** Um dado do processo: rótulo pequeno e o valor. Use dentro de um <dl>. */
export function Campo({ rotulo, children, className = "" }: { rotulo: string; children: ReactNode; className?: string }) {
  return (
    <div className={`min-w-0 ${className}`}>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{rotulo}</dt>
      <dd className="mt-0.5 text-sm [overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

/** O valor, ou "Não identificado" quando a leitura não achou. */
export const ou = (valor: string | null | undefined) => valor || <span className="text-muted">Não identificado</span>;
