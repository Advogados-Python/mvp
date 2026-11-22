"use client";

import { useId, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { formatarBytes, formatarDataHora } from "@/lib/formatar";
import type { EstadoAnalise, Fases, Processo } from "@/lib/tipos";
import { rotuloDaFase } from "@/lib/use-fases";
import type { Conexao } from "@/lib/use-processo-ao-vivo";
import { CorpoBusca, CorpoExtracao, CorpoFinalizacao, CorpoIdentificacao, CorpoRecebimento, CorpoValidacao, leituraDe } from "./corpos-das-fases";
import { BarraIndeterminada, CIRCULO, IconePasso, PASSOS, TEXTO_SITUACAO, interpretar, paginas, type Passo, type Situacao } from "./progresso-analise";
import { Recolhivel } from "./recolhivel";
import { SeloDivida } from "./selo-divida";

/**
 * O processo, fase a fase: as seis fases de leitura do documento (uma por módulo do backend), cada uma com o que produziu.
 * Enquanto o PDF é analisado mostra o andamento real de cada fase; ao terminar, o resultado de cada uma.
 * A situação de cada fase vem do que a API informou (`status` + `progresso`), nunca de um relógio da tela.
 */

const EVIDENCIAS_ABERTAS_ATE = 12;

interface ItemProps {
  numero: number;
  passo: Passo;
  situacao: Situacao;
  resumo: ReactNode;
  corpo: ReactNode | null;
  abertaInicialmente: boolean;
  ultima: boolean;
}

function ItemDaFase({ numero, passo, situacao, resumo, corpo, abertaInicialmente, ultima }: ItemProps) {
  const [aberta, setAberta] = useState(abertaInicialmente);
  const idRegiao = useId();
  const expansivel = corpo !== null;

  const cabecalho = (
    <>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5 sm:flex-row sm:items-center sm:gap-3">
        <span className={`shrink-0 font-semibold ${situacao === "pendente" ? "text-muted" : ""} ${situacao === "falhou" ? "text-danger" : ""}`}>
          {numero}. {passo.rotulo}
          <span className="sr-only"> ({TEXTO_SITUACAO[situacao]})</span>
        </span>
        <span className="min-w-0 text-sm font-normal text-muted">{resumo}</span>
      </span>
      {expansivel && (
        <ChevronDown aria-hidden className={`mt-0.5 size-5 shrink-0 text-muted transition-transform duration-300 ${aberta ? "rotate-180" : ""}`} />
      )}
    </>
  );

  return (
    <li aria-current={situacao === "ativa" ? "step" : undefined} className="relative flex gap-3 sm:gap-4">
      <div className="flex w-9 shrink-0 flex-col items-center">
        <span className={`relative z-10 grid size-9 shrink-0 place-items-center rounded-full transition-colors duration-500 ${CIRCULO[situacao]}`}>
          {situacao === "ativa" && (
            <span
              aria-hidden
              className="absolute -inset-1.5 rounded-full border-2 border-transparent border-t-accent motion-safe:animate-spin motion-reduce:border-accent/30"
            />
          )}
          <IconePasso passo={passo} situacao={situacao} />
        </span>
        {!ultima && (
          <span aria-hidden className="mt-1 w-0.5 flex-1 overflow-hidden bg-border">
            <span className={`block size-full origin-top bg-accent transition-transform duration-700 ease-out ${situacao === "concluida" ? "scale-y-100" : "scale-y-0"}`} />
          </span>
        )}
      </div>

      <section className="vidro mb-3 min-w-0 flex-1 self-start rounded-2xl sm:mb-4">
        <h2 className="text-base">
          {expansivel ? (
            <button
              type="button"
              aria-expanded={aberta}
              aria-controls={idRegiao}
              onClick={() => setAberta((atual) => !atual)}
              className="flex w-full items-start gap-3 rounded-2xl p-3 text-left sm:p-4"
            >
              {cabecalho}
            </button>
          ) : (
            <div className="flex items-start gap-3 p-3 sm:p-4">{cabecalho}</div>
          )}
        </h2>
        {expansivel && (
          <Recolhivel aberto={aberta} id={idRegiao}>
            <div className="px-3 pb-3 sm:px-4 sm:pb-4">{corpo}</div>
          </Recolhivel>
        )}
      </section>
    </li>
  );
}

/** O corpo de uma fase que está rodando: o que ela faz agora e, se o backend informa, quantas páginas já foram. */
function CorpoEmAndamento({ passo, atual, total, unidade }: { passo: Passo; atual: number | null; total: number | null; unidade?: string }) {
  const contagem = unidade && atual !== null && total ? { atual, total } : null;
  return (
    <div>
      <p className="animate-aparecer text-sm text-muted">{passo.mensagem}</p>
      {contagem ? (
        <div className="mt-3">
          <div
            role="progressbar"
            aria-label={`Páginas ${unidade}`}
            aria-valuemin={0}
            aria-valuemax={contagem.total}
            aria-valuenow={contagem.atual}
            aria-valuetext={`${contagem.atual} de ${contagem.total} páginas ${unidade}`}
            className="h-2 overflow-hidden rounded-full bg-surface-2"
          >
            <div className="h-full rounded-full bg-accent transition-[width] duration-300 ease-out" style={{ width: `${Math.round((contagem.atual / contagem.total) * 100)}%` }} />
          </div>
          <p className="mt-1.5 text-xs tabular-nums text-muted">
            {contagem.atual} de {contagem.total} páginas {unidade}
          </p>
        </div>
      ) : (
        passo.codigo !== "RECEBIDO" && (
          <div className="mt-3">
            <BarraIndeterminada rotulo={`${passo.rotulo}: em andamento`} />
          </div>
        )
      )}
    </div>
  );
}

export function FasesDoProcesso({
  processo,
  fases,
  estado,
  conexao,
}: {
  processo: Processo;
  fases: Fases | null;
  estado: EstadoAnalise | null;
  conexao: Conexao;
}) {
  const vivo = estado ?? { status: processo.status, progresso: processo.progresso };
  const leitura = interpretar(vivo.status, vivo.progresso);
  // Falha sem fase conhecida (o servidor reiniciou): só o recebimento está confirmado, e a tela não inventa onde parou.
  const situacoes: Situacao[] = leitura?.situacoes ?? PASSOS.map((_, i) => (i === 0 ? "concluida" : "pendente"));
  const temResultado = processo.status === "CONCLUIDO"; // os dados das fases 2 a 6 só existem com a análise concluída
  const { total, lidas } = leituraDe(processo);
  const contam = processo.evidencias_que_contam;
  const andamento = processo.status === "PENDENTE" || processo.status === "ANALISANDO";
  const semFaseConhecida = vivo.status === "ANALISANDO" && leitura?.indice === null; // o servidor ainda não disse em qual fase está
  const ativa = leitura?.indice != null && situacoes[leitura.indice] === "ativa" ? leitura.indice : null;

  function conteudoDe(indice: number): { resumo: ReactNode; corpo: ReactNode | null; aberta: boolean } {
    const passo = PASSOS[indice];
    const situacao = situacoes[indice];
    const contagemViva = situacao === "ativa" ? paginas(vivo.progresso) : null;

    if (situacao === "ativa") {
      const resumo =
        indice === 0
          ? "Na fila: aguardando a vez de ser lido"
          : contagemViva && passo.contagem
            ? `${contagemViva.atual}/${contagemViva.total} pág.` // a contagem por extenso fica no corpo da fase
            : "Em andamento…";
      return {
        resumo,
        corpo: <CorpoEmAndamento passo={passo} atual={contagemViva?.atual ?? null} total={contagemViva?.total ?? null} unidade={passo.contagem} />,
        aberta: true,
      };
    }
    if (situacao === "falhou") {
      return {
        resumo: "A análise parou aqui",
        corpo: <p className="text-sm text-danger">{processo.erro ?? "Erro desconhecido."}</p>,
        aberta: true,
      };
    }
    if (situacao === "pendente") return { resumo: "Aguardando", corpo: null, aberta: false };

    // concluída
    switch (indice) {
      case 0:
        return {
          resumo: `${formatarBytes(processo.tamanho_bytes)} · recebido em ${formatarDataHora(processo.criado_em)}`,
          corpo: <CorpoRecebimento processo={processo} />,
          aberta: false,
        };
      case 1:
        return { resumo: temResultado ? `${lidas} de ${total} páginas lidas` : "Concluída", corpo: temResultado ? <CorpoExtracao processo={processo} /> : null, aberta: false };
      case 2:
        return {
          resumo: temResultado ? [processo.numero_processo ?? "Número não identificado", processo.tribunal].filter(Boolean).join(" · ") : "Concluída",
          corpo: temResultado ? <CorpoIdentificacao processo={processo} /> : null,
          aberta: true,
        };
      case 3:
        return {
          resumo: temResultado ? `${processo.total_evidencias} ${processo.total_evidencias === 1 ? "achado" : "achados"} · ${contam} decidem a fase` : "Concluída",
          corpo: temResultado ? <CorpoBusca processo={processo} fases={fases} /> : null,
          aberta: temResultado && processo.evidencias.length <= EVIDENCIAS_ABERTAS_ATE, // muitas evidências: começa recolhida (o resumo diz quantas são)
        };
      case 4:
        return {
          resumo: temResultado ? (
            <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
              {rotuloDaFase(fases, processo.fase ?? "SEM_INFORMACAO")}
              <SeloDivida valor={processo.divida_paga ?? "SEM_INFORMACAO"} />
            </span>
          ) : (
            "Concluída"
          ),
          corpo: temResultado ? <CorpoValidacao processo={processo} fases={fases} /> : null,
          aberta: true,
        };
      default:
        return {
          resumo: temResultado ? `Gravado em ${formatarDataHora(processo.concluido_em ?? processo.criado_em)}` : "Concluída",
          corpo: temResultado ? <CorpoFinalizacao processo={processo} /> : null,
          aberta: false,
        };
    }
  }

  return (
    <div>
      <ol aria-label="Fases do processo">
        {PASSOS.map((passo, indice) => {
          const { resumo, corpo, aberta } = conteudoDe(indice);
          return (
            <ItemDaFase
              key={`${passo.codigo}-${situacoes[indice]}-${temResultado}`} // ao mudar de situação, o item recomeça com o seu padrão (aberto/fechado)
              numero={indice + 1}
              passo={passo}
              situacao={situacoes[indice]}
              resumo={resumo}
              corpo={corpo}
              abertaInicialmente={aberta}
              ultima={indice === PASSOS.length - 1}
            />
          );
        })}
      </ol>
      {/* Anuncia só a MUDANÇA de fase para leitores de tela (a contagem de páginas fica fora: mudaria a cada página). */}
      {ativa !== null && (
        <p role="status" className="sr-only">
          Fase {ativa + 1} de {PASSOS.length}: {PASSOS[ativa].rotulo}.
        </p>
      )}
      {semFaseConhecida && (
        <div className="mb-3 space-y-2">
          <p className="text-sm text-muted">O servidor ainda não informou em que fase está.</p>
          <BarraIndeterminada rotulo="Análise em andamento" />
        </div>
      )}
      {andamento && (
        <p className="text-xs text-muted">
          {conexao === "ao-vivo"
            ? "Acompanhando ao vivo."
            : conexao === "polling"
              ? "Sem conexão em tempo real: consultando a API a cada 2 segundos."
              : "Conectando ao servidor…"}{" "}
          Você pode sair desta página: a análise continua no servidor.
        </p>
      )}
    </div>
  );
}
