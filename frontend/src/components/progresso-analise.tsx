import { Check, CircleX, Clock, FileCheck2, Fingerprint, Layers, LoaderCircle, Save, ScanText, ShieldCheck, type LucideIcon } from "lucide-react";
import { ETAPAS, type Progresso, type StatusAnalise } from "@/lib/tipos";

/**
 * Acompanhamento da análise: as etapas reais do pipeline do backend e em qual delas o PDF está.
 *
 * Tudo vem da API (`status` + `progresso`); nada é estimado:
 *  - não há percentual geral (não existe como saber quanto cada etapa pesa);
 *  - a contagem de páginas só aparece nas etapas em que o backend a informa (ler e analisar página a página);
 *  - o pipeline é sequencial e o backend só anuncia uma etapa quando ela começa, então "etapa X em andamento" é a
 *    confirmação de que as anteriores terminaram;
 *  - sem informação de etapa (status ANALISANDO sem `progresso`), a barra é indeterminada, sem fingir andamento.
 */

interface Passo {
  /** "RECEBIDO" não vem da API: é o status PENDENTE (o PDF chegou e espera a vez). As demais são as ETAPAS do backend. */
  codigo: "RECEBIDO" | (typeof ETAPAS)[number];
  rotulo: string;
  Icone: LucideIcon;
  mensagem: string;
  /** Só nas etapas que andam página a página: o que a contagem significa ("páginas lidas"). */
  contagem?: string;
}

const PASSOS: Passo[] = [
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
    codigo: "ANALISANDO_FASES",
    rotulo: "Analisando as fases",
    Icone: Layers,
    mensagem: "Buscando, página a página, os termos que indicam a fase do crédito.",
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

type Situacao = "concluida" | "ativa" | "pendente" | "falhou";

interface Leitura {
  situacoes: Situacao[];
  /** Índice do passo ativo (ou o que falhou). null = andamento sem etapa conhecida. */
  indice: number | null;
}

/** O que cada passo é, a partir do que a API informou. null = não há o que mostrar (nada a afirmar). */
function interpretar(status: StatusAnalise, progresso: Progresso | null): Leitura | null {
  const todos = (situacao: Situacao) => PASSOS.map(() => situacao);
  if (status === "CONCLUIDO") return { situacoes: todos("concluida"), indice: null };
  if (status === "PENDENTE") return { situacoes: PASSOS.map((_, i) => (i === 0 ? "ativa" : "pendente")), indice: 0 };

  const indice = PASSOS.findIndex((passo) => passo.codigo === progresso?.etapa);
  if (status === "FALHOU") {
    if (!progresso?.falhou || indice < 1) return null; // servidor reiniciou ou etapa desconhecida: não afirma onde parou
    return { situacoes: PASSOS.map((_, i) => (i < indice ? "concluida" : i === indice ? "falhou" : "pendente")), indice };
  }
  // ANALISANDO. Sem etapa conhecida: só o recebimento está confirmado.
  if (indice < 1 || progresso?.falhou) {
    return { situacoes: PASSOS.map((_, i) => (i === 0 ? "concluida" : "pendente")), indice: null };
  }
  return { situacoes: PASSOS.map((_, i) => (i < indice ? "concluida" : i === indice ? "ativa" : "pendente")), indice };
}

const TEXTO_SITUACAO: Record<Situacao, string> = {
  concluida: "concluída",
  ativa: "em andamento",
  pendente: "aguardando",
  falhou: "falhou aqui",
};

/** "12 de 300", só se o backend informou os dois números (e o total faz sentido). */
function paginas(progresso: Progresso | null) {
  if (!progresso || progresso.atual == null || !progresso.total || progresso.total <= 0) return null;
  const atual = Math.min(progresso.atual, progresso.total);
  return { atual, total: progresso.total, fracao: atual / progresso.total };
}

/** Ícone da etapa. Só o da etapa ativa se mexe (e só para quem não pediu menos movimento). */
function IconePasso({ passo, situacao }: { passo: Passo; situacao: Situacao }) {
  if (situacao === "concluida") return <Check aria-hidden className="size-4 animate-aparecer" />;
  if (situacao === "falhou") return <CircleX aria-hidden className="size-[18px] animate-aparecer" />;
  if (situacao === "ativa") {
    const Icone = passo.codigo === "RECEBIDO" ? Clock : passo.Icone; // aguardando a vez: relógio, não "recebido"
    return <Icone aria-hidden className="size-[18px] motion-safe:animate-pulso-icone" />;
  }
  return <passo.Icone aria-hidden className="size-4 opacity-60" />;
}

const CIRCULO: Record<Situacao, string> = {
  concluida: "bg-accent text-accent-foreground",
  ativa: "bg-accent-soft text-accent ring-2 ring-accent",
  pendente: "border-2 border-border bg-surface text-muted",
  falhou: "bg-danger-soft text-danger ring-2 ring-danger",
};

function BarraIndeterminada({ rotulo }: { rotulo: string }) {
  // Sem número a mostrar: um trecho que desliza. Para quem pede menos movimento a barra some e o texto basta.
  return (
    <div
      role="progressbar"
      aria-label={rotulo}
      className="h-1.5 overflow-hidden rounded-full bg-surface-2 motion-reduce:hidden"
    >
      <div className="h-full w-1/4 rounded-full bg-accent motion-safe:animate-indeterminado" />
    </div>
  );
}

interface Props {
  status: StatusAnalise;
  progresso: Progresso | null;
  variante?: "completa" | "compacta";
  /** Só na completa: como a página está recebendo as atualizações (ao vivo, ou consultando a API a cada 2 s). */
  conexao?: "conectando" | "ao-vivo" | "polling";
}

export function ProgressoAnalise({ status, progresso, variante = "completa", conexao }: Props) {
  const leitura = interpretar(status, progresso);
  if (!leitura) return null;
  if (variante === "compacta" && (status === "CONCLUIDO" || status === "FALHOU")) return null;

  const { situacoes, indice } = leitura;
  const ativo = indice === null ? null : PASSOS[indice];
  const contagem = ativo?.contagem && status === "ANALISANDO" ? paginas(progresso) : null;
  const falhou = status === "FALHOU";

  // ---- compacta: uma linha + um traço de 6 segmentos (linhas do histórico, cartões do mobile)
  if (variante === "compacta") {
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
            : `Etapa ${indice + 1} de ${PASSOS.length}: ${PASSOS[indice].rotulo}${contagem ? `, ${contagem.atual} de ${contagem.total} páginas` : ""}.`}
        </span>
      </div>
    );
  }

  // ---- completa
  return (
    <div role="group" aria-label="Andamento da análise" className="space-y-4">
      <ol className="grid md:grid-cols-6">
        {PASSOS.map((passo, i) => {
          const situacao = situacoes[i];
          const proximaConcluida = situacao === "concluida";
          return (
            <li
              key={passo.codigo}
              aria-current={situacao === "ativa" ? "step" : undefined}
              className="relative flex gap-3 pb-6 last:pb-0 md:flex-col md:items-center md:gap-2 md:pb-0 md:text-center"
            >
              {i < PASSOS.length - 1 && (
                <span
                  aria-hidden
                  className="absolute bottom-0 left-[18px] top-9 w-0.5 -translate-x-1/2 overflow-hidden bg-border md:bottom-auto md:left-1/2 md:top-[18px] md:h-0.5 md:w-full md:translate-x-0 md:-translate-y-1/2"
                >
                  {/* a linha "enche" quando a etapa termina; começa no meio do círculo e vai até o próximo */}
                  <span
                    className={`block size-full origin-top bg-accent transition-transform duration-700 ease-out md:origin-left ${
                      proximaConcluida ? "scale-100" : "scale-0"
                    }`}
                  />
                </span>
              )}
              <span
                className={`relative z-10 grid size-9 shrink-0 place-items-center rounded-full transition-colors duration-500 ${CIRCULO[situacao]}`}
              >
                {situacao === "ativa" && (
                  <span
                    aria-hidden
                    className="absolute -inset-1.5 rounded-full border-2 border-transparent border-t-accent motion-safe:animate-spin motion-reduce:border-accent/30"
                  />
                )}
                <IconePasso passo={passo} situacao={situacao} />
              </span>
              <span className="min-w-0 pt-1.5 md:px-1 md:pt-0">
                <span
                  className={`block text-sm transition-colors duration-500 ${
                    situacao === "ativa" || situacao === "falhou" ? "font-semibold" : situacao === "pendente" ? "text-muted" : ""
                  } ${situacao === "falhou" ? "text-danger" : ""}`}
                >
                  {passo.rotulo}
                </span>
                <span className="sr-only">({TEXTO_SITUACAO[situacao]})</span>
              </span>
            </li>
          );
        })}
      </ol>

      <div className="rounded-xl border border-border bg-surface-2 p-4">
        {/* A mensagem é a única parte "viva" para leitores de tela: muda a cada etapa, não a cada página. */}
        <div role="status" className="min-h-10">
          {falhou && ativo ? (
            <p className="animate-aparecer text-sm">
              <span className="font-semibold text-danger">A análise parou em “{ativo.rotulo}”.</span>
            </p>
          ) : ativo ? (
            <p key={ativo.codigo} className="animate-aparecer text-sm">
              <span className="font-semibold">{ativo.rotulo}.</span> <span className="text-muted">{ativo.mensagem}</span>
            </p>
          ) : (
            <p className="text-sm">
              <span className="font-semibold">Análise em andamento.</span>{" "}
              <span className="text-muted">O servidor ainda não informou em que etapa está.</span>
            </p>
          )}
        </div>

        {contagem && (
          <div className="mt-3">
            <div
              role="progressbar"
              aria-label={`Páginas ${ativo?.contagem}`}
              aria-valuemin={0}
              aria-valuemax={contagem.total}
              aria-valuenow={contagem.atual}
              aria-valuetext={`${contagem.atual} de ${contagem.total} páginas ${ativo?.contagem}`}
              className="h-2 overflow-hidden rounded-full bg-surface"
            >
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-300 ease-out"
                style={{ width: `${Math.round(contagem.fracao * 100)}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs tabular-nums text-muted">
              {contagem.atual} de {contagem.total} páginas {ativo?.contagem}
            </p>
          </div>
        )}
        {!contagem && status === "ANALISANDO" && (
          <div className="mt-3">
            <BarraIndeterminada rotulo="Análise em andamento" />
          </div>
        )}

        {conexao && status !== "FALHOU" && (
          <p className="mt-3 text-xs text-muted">
            {conexao === "ao-vivo"
              ? "Acompanhando ao vivo."
              : conexao === "polling"
                ? "Sem conexão em tempo real: consultando a API a cada 2 segundos."
                : "Conectando ao servidor…"}{" "}
            Você pode sair desta página: a análise continua no servidor.
          </p>
        )}
      </div>
    </div>
  );
}
