import { Check, CircleX, Clock, FileCheck2, Fingerprint, Layers, LoaderCircle, Save, ScanText, ShieldCheck, type LucideIcon } from "lucide-react";
import { ETAPAS, type Progresso, type StatusAnalise } from "@/lib/tipos";

/**
 * As seis fases de leitura do documento, uma por módulo do backend (receive, extract, identify, search, validate, finalize),
 * e em qual delas o PDF está. Tudo vem da API (`status` + `progresso`); nada é estimado:
 *  - não há percentual geral (não existe como saber quanto cada fase pesa);
 *  - a contagem de páginas só aparece nas fases em que o backend a informa (extração e busca de termos);
 *  - o pipeline é sequencial e o backend só anuncia uma fase quando ela começa, então "fase X em andamento" é a confirmação
 *    de que as anteriores terminaram;
 *  - sem informação de fase (status ANALISANDO sem `progresso`), a barra é indeterminada, sem fingir andamento.
 */

export interface Passo {
  /** "RECEBIDO" não vem da API de andamento: é o status PENDENTE (o PDF chegou e espera a vez). As demais são as ETAPAS do backend. */
  codigo: "RECEBIDO" | (typeof ETAPAS)[number];
  rotulo: string;
  Icone: LucideIcon;
  mensagem: string;
  /** Só nas fases que andam página a página: o que a contagem significa ("páginas lidas"). */
  contagem?: string;
}

export const PASSOS: Passo[] = [
  {
    codigo: "RECEBIDO",
    rotulo: "Documento recebido",
    Icone: FileCheck2,
    mensagem: "O PDF foi recebido e está na fila. A leitura começa assim que houver uma vaga.",
  },
  { codigo: "LENDO_PDF", rotulo: "Extraindo conteúdo", Icone: ScanText, mensagem: "Lendo o texto de cada página do PDF.", contagem: "lidas" },
  {
    codigo: "IDENTIFICANDO",
    rotulo: "Identificando o processo",
    Icone: Fingerprint,
    mensagem: "Procurando o número do processo, o tribunal, as partes, os advogados e o juiz.",
  },
  {
    codigo: "BUSCANDO_TERMOS",
    rotulo: "Buscando os termos",
    Icone: Layers,
    mensagem: "Procurando, página a página, os termos de cada fase do crédito e guardando cada achado como evidência.",
    contagem: "analisadas",
  },
  {
    codigo: "VALIDANDO",
    rotulo: "Validando evidências",
    Icone: ShieldCheck,
    mensagem: "Separando as evidências que decidem a fase das condicionais e das peças das partes.",
  },
  { codigo: "FINALIZANDO", rotulo: "Finalizando resultado", Icone: Save, mensagem: "Gravando o resultado." },
];

export type Situacao = "concluida" | "ativa" | "pendente" | "falhou";

export interface Leitura {
  situacoes: Situacao[];
  /** Índice do passo ativo (ou o que falhou). null = andamento sem fase conhecida. */
  indice: number | null;
}

/** O que cada fase é, a partir do que a API informou. null = não há o que afirmar (falha sem fase conhecida). */
export function interpretar(status: StatusAnalise, progresso: Progresso | null): Leitura | null {
  const todos = (situacao: Situacao) => PASSOS.map(() => situacao);
  if (status === "CONCLUIDO") return { situacoes: todos("concluida"), indice: null };
  if (status === "PENDENTE") return { situacoes: PASSOS.map((_, i) => (i === 0 ? "ativa" : "pendente")), indice: 0 };

  const indice = PASSOS.findIndex((passo) => passo.codigo === progresso?.etapa);
  if (status === "FALHOU") {
    if (!progresso?.falhou || indice < 1) return null; // servidor reiniciou ou fase desconhecida: não afirma onde parou
    return { situacoes: PASSOS.map((_, i) => (i < indice ? "concluida" : i === indice ? "falhou" : "pendente")), indice };
  }
  // ANALISANDO. Sem fase conhecida: só o recebimento está confirmado.
  if (indice < 1 || progresso?.falhou) {
    return { situacoes: PASSOS.map((_, i) => (i === 0 ? "concluida" : "pendente")), indice: null };
  }
  return { situacoes: PASSOS.map((_, i) => (i < indice ? "concluida" : i === indice ? "ativa" : "pendente")), indice };
}

export const TEXTO_SITUACAO: Record<Situacao, string> = {
  concluida: "concluída",
  ativa: "em andamento",
  pendente: "aguardando",
  falhou: "falhou aqui",
};

/** "12 de 300", só se o backend informou os dois números (e o total faz sentido). */
export function paginas(progresso: Progresso | null) {
  if (!progresso || progresso.atual == null || !progresso.total || progresso.total <= 0) return null;
  const atual = Math.min(progresso.atual, progresso.total);
  return { atual, total: progresso.total, fracao: atual / progresso.total };
}

/** Ícone da fase. Só o da fase ativa se mexe (e só para quem não pediu menos movimento). */
export function IconePasso({ passo, situacao }: { passo: Passo; situacao: Situacao }) {
  if (situacao === "concluida") return <Check aria-hidden className="size-4 animate-aparecer" />;
  if (situacao === "falhou") return <CircleX aria-hidden className="size-[18px] animate-aparecer" />;
  if (situacao === "ativa") {
    const Icone = passo.codigo === "RECEBIDO" ? Clock : passo.Icone; // aguardando a vez: relógio, não "recebido"
    return <Icone aria-hidden className="size-[18px] motion-safe:animate-pulso-icone" />;
  }
  return <passo.Icone aria-hidden className="size-4 opacity-60" />;
}

export const CIRCULO: Record<Situacao, string> = {
  concluida: "bg-accent text-accent-foreground",
  ativa: "bg-accent-soft text-accent ring-2 ring-accent",
  pendente: "border-2 border-border bg-surface text-muted",
  falhou: "bg-danger-soft text-danger ring-2 ring-danger",
};

export function BarraIndeterminada({ rotulo }: { rotulo: string }) {
  // Sem número a mostrar: um trecho que desliza. Para quem pede menos movimento a barra some e o texto basta.
  return (
    <div role="progressbar" aria-label={rotulo} className="h-1.5 overflow-hidden rounded-full bg-surface-2 motion-reduce:hidden">
      <div className="h-full w-1/4 rounded-full bg-accent motion-safe:animate-indeterminado" />
    </div>
  );
}

/** A versão de uma linha, para o histórico: a fase atual, a contagem de páginas (se houver) e um traço de seis segmentos. */
export function ProgressoAnalise({ status, progresso }: { status: StatusAnalise; progresso: Progresso | null }) {
  const leitura = interpretar(status, progresso);
  if (!leitura || status === "CONCLUIDO" || status === "FALHOU") return null;

  const { situacoes, indice } = leitura;
  const ativo = indice === null ? null : PASSOS[indice];
  const contagem = ativo?.contagem && status === "ANALISANDO" ? paginas(progresso) : null;
  const rotulo = status === "PENDENTE" ? "Na fila" : (ativo?.rotulo ?? "Iniciando a leitura");

  return (
    <div className="min-w-0">
      <p className="flex min-w-0 flex-wrap items-center gap-x-1.5 text-sm">
        <span className="flex min-w-0 items-center gap-1.5">
          {status === "PENDENTE" ? (
            <Clock aria-hidden className="size-3.5 shrink-0 text-accent motion-safe:animate-pulso-icone" /> // esperando a vez: não está processando
          ) : (
            <LoaderCircle aria-hidden className="size-3.5 shrink-0 text-accent motion-safe:animate-spin" />
          )}
          <span>{rotulo}…</span>
        </span>
        {contagem && (
          <span className="whitespace-nowrap text-xs tabular-nums text-muted">
            {contagem.atual}/{contagem.total} pág.
          </span>
        )}
      </p>
      <div aria-hidden className="mt-1.5 flex gap-1">
        {situacoes.map((situacao, i) => (
          <span
            key={PASSOS[i].codigo}
            className={`h-1 flex-1 rounded-full transition-colors duration-500 ${
              situacao === "concluida" ? "bg-accent" : situacao === "ativa" ? "bg-accent/60 motion-safe:animate-pulse" : "bg-border"
            }`}
          />
        ))}
      </div>
      <span className="sr-only">
        {indice === null
          ? "Análise em andamento."
          : `Fase ${indice + 1} de ${PASSOS.length}: ${PASSOS[indice].rotulo}${contagem ? `, ${contagem.atual} de ${contagem.total} páginas` : ""}.`}
      </span>
    </div>
  );
}
