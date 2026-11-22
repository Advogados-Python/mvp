"use client";

import Link from "next/link";
import { memo, useCallback, useMemo, useState } from "react";
import { Inbox, RefreshCw, Search, SearchX, Trash2, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { formatarDataHora } from "@/lib/formatar";
import { emAndamento, type DividaPaga, type Fases, type ResumoProcesso } from "@/lib/tipos";
import { useListaProcessos } from "@/lib/use-lista-processos";
import { rotuloDaFase, useFases } from "@/lib/use-fases";
import { ProgressoAnalise } from "./progresso-analise";
import { DIVIDA, ORDEM_DIVIDA } from "./selo-divida";
import { SeloProcesso } from "./selo-status";
import { Aviso, Cartao, Esqueleto } from "./ui";

type Filtro = DividaPaga | "TODOS";

const semAcento = (texto: string) => texto.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

function textoDeBusca(processo: ResumoProcesso): string {
  return semAcento(
    [
      processo.numero_processo,
      processo.arquivo,
      processo.tribunal,
      processo.juiz,
      ...processo.partes.map((parte) => parte.nome),
      ...processo.advogados,
    ]
      .filter(Boolean)
      .join(" "),
  );
}

/**
 * Uma linha do histórico. A mesma marcação vira cartão no celular (número e partes, fase, e um rodapé com situação e data),
 * duas linhas no tablet (md) e uma linha de quatro colunas no desktop (lg): A número+partes · B fase · C situação · D data+avisos.
 * No desktop C e D têm largura fixa: cada linha é uma grade própria e, com trilhas `auto`, as colunas não alinhariam entre linhas. `memo`: só renderiza de novo se o próprio
 * processo mudou, então as atualizações a cada 2 s tocam apenas nas linhas em andamento.
 */
const LinhaProcesso = memo(function LinhaProcesso({
  processo,
  fases,
  apagando,
  aoApagar,
}: {
  processo: ResumoProcesso;
  fases: Fases | null;
  apagando: boolean;
  aoApagar: (processo: ResumoProcesso) => void;
}) {
  const concluido = processo.status === "CONCLUIDO";
  const nome = processo.numero_processo ?? processo.arquivo;
  return (
    <li className="flex items-stretch bg-surface">
      <Link
        href={`/processos/${processo.id}`}
        className="grid min-w-0 flex-1 grid-cols-1 items-center gap-x-4 gap-y-2 p-3 transition-colors hover:bg-surface-2 sm:p-4 md:grid-cols-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(15rem,1.4fr)_minmax(0,1.2fr)_10.5rem_11rem]"
      >
        {/* A: número (inteiro, sem cortar) e partes */}
        <div data-area="A" className="row-start-1 min-w-0 md:col-start-1">
          <p className="font-mono text-sm font-medium [overflow-wrap:anywhere]">
            {processo.numero_processo ?? (concluido ? "Número não identificado" : processo.arquivo)}
          </p>
          <p className="truncate text-xs text-muted" title={processo.arquivo}>
            {processo.partes.map((parte) => parte.nome).join(" × ") || processo.arquivo}
          </p>
        </div>

        {/* B: fase atual e tribunal (ou o andamento / o erro) */}
        <div data-area="B" className="row-start-2 min-w-0 md:col-start-1 lg:col-start-2 lg:row-start-1">
          {concluido ? (
            <>
              <p className="text-sm">{rotuloDaFase(fases, processo.fase ?? "SEM_INFORMACAO")}</p>
              {(processo.tribunal || processo.classe) && (
                <p className="truncate text-xs text-muted" title={[processo.tribunal, processo.classe].filter(Boolean).join(" · ")}>
                  {processo.tribunal && <span className="font-medium text-foreground/80">{processo.tribunal}</span>}
                  {processo.tribunal && processo.classe && " · "}
                  {processo.classe}
                </p>
              )}
            </>
          ) : processo.status === "FALHOU" ? (
            <p className="line-clamp-2 text-sm text-danger">{processo.erro}</p>
          ) : (
            <ProgressoAnalise status={processo.status} progresso={processo.progresso} />
          )}
        </div>

        {/* Rodapé do cartão no celular e no tablet (situação à esquerda, data à direita, quebrando linha se faltar espaço).
            A partir de md o bloco some (`contents`) e C e D viram colunas da grade. */}
        <div className="row-start-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 md:contents">
          {/* C: situação da dívida (ou o estado da análise) */}
          <div data-area="C" className="flex md:col-start-2 md:row-start-1 md:justify-end lg:col-start-3 lg:justify-start">
            <SeloProcesso processo={processo} />
          </div>

          {/* D: data e avisos */}
          <div
            data-area="D"
            className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted md:col-start-2 md:row-start-2 md:justify-end lg:col-start-4 lg:row-start-1"
          >
            <time dateTime={processo.concluido_em ?? processo.criado_em} className="whitespace-nowrap">
              {formatarDataHora(processo.concluido_em ?? processo.criado_em)}
            </time>
            {processo.avisos.length > 0 && (
              <span
                className="inline-flex items-center gap-1 whitespace-nowrap font-medium text-warn"
                title={`${processo.avisos.length} aviso(s): leia antes de confiar no resultado`}
              >
                <TriangleAlert aria-hidden className="size-3.5" />
                <span className="sr-only">Avisos:</span>
                {processo.avisos.length} {processo.avisos.length === 1 ? "aviso" : "avisos"}
              </span>
            )}
          </div>
        </div>
      </Link>
      <button
        type="button"
        disabled={apagando}
        aria-label={`Apagar ${nome}`}
        onClick={() => aoApagar(processo)}
        className="grid w-11 shrink-0 place-items-center border-l border-border text-muted transition-colors hover:bg-danger-soft hover:text-danger disabled:opacity-40 sm:w-12"
      >
        <Trash2 aria-hidden className="size-4" />
      </button>
    </li>
  );
});

/** O histórico: a seção principal da página inicial. `versao` muda quando um envio termina: é o sinal para buscar já. */
export function ListaProcessos({ versao }: { versao: number }) {
  const fases = useFases();
  const { processos, erro, recarregar, remover } = useListaProcessos(versao);
  const [filtro, setFiltro] = useState<Filtro>("TODOS");
  const [busca, setBusca] = useState("");
  const [apagando, setApagando] = useState<string | null>(null);
  const [erroAoApagar, setErroAoApagar] = useState<string | null>(null);

  const contagem = useMemo(() => {
    const total: Record<string, number> = { TODOS: processos?.length ?? 0 };
    for (const processo of processos ?? []) {
      if (processo.divida_paga) total[processo.divida_paga] = (total[processo.divida_paga] ?? 0) + 1;
    }
    return total;
  }, [processos]);

  const visiveis = useMemo(() => {
    const termo = semAcento(busca.trim());
    return (processos ?? []).filter(
      (processo) =>
        (filtro === "TODOS" || processo.divida_paga === filtro) && (!termo || textoDeBusca(processo).includes(termo)),
    );
  }, [processos, filtro, busca]);

  const emAnalise = (processos ?? []).filter((processo) => emAndamento(processo.status)).length;

  // useCallback: as linhas são `memo`; uma função nova a cada render as faria renderizar de novo sem necessidade
  const apagar = useCallback(
    async (processo: ResumoProcesso) => {
      const nome = processo.numero_processo ?? processo.arquivo;
      if (!window.confirm(`Apagar o PDF e o resultado de ${nome}? Isso não pode ser desfeito.`)) return;
      setApagando(processo.id);
      setErroAoApagar(null);
      try {
        await api.excluir(processo.id);
        remover(processo.id);
      } catch (falha) {
        setErroAoApagar(falha instanceof Error ? falha.message : "Não foi possível apagar.");
      } finally {
        setApagando(null);
      }
    },
    [remover],
  );

  const filtrando = filtro !== "TODOS" || busca.trim() !== "";

  return (
    <Cartao
      titulo="Histórico de processos"
      descricao="Clique em um processo para ver as evidências e abrir o PDF na página certa."
      acao={
        emAnalise > 0 ? (
          <span role="status" className="rounded-full bg-info-soft px-2.5 py-1 text-xs font-medium text-info">
            {emAnalise === 1 ? "1 análise em andamento" : `${emAnalise} análises em andamento`}
          </span>
        ) : undefined
      }
    >
      {erro && processos === null && (
        <Aviso tom="danger" titulo="Não foi possível carregar o histórico">
          <p>{erro}</p>
          <button
            type="button"
            onClick={recarregar}
            className="mt-2 inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent"
          >
            <RefreshCw aria-hidden className="size-4" />
            Tentar de novo
          </button>
        </Aviso>
      )}

      {erro && processos !== null && (
        <div className="mb-4">
          <Aviso titulo="Sem conexão com a API">
            Mostrando a última lista que foi carregada. Continuamos tentando e ela se atualiza sozinha quando a conexão voltar.
          </Aviso>
        </div>
      )}

      {erroAoApagar && (
        <div className="mb-4">
          <Aviso tom="danger" titulo="Não foi possível apagar">
            {erroAoApagar}
          </Aviso>
        </div>
      )}

      {processos === null && !erro && (
        <div className="space-y-3" aria-busy="true" aria-label="Carregando processos">
          <Esqueleto className="h-20" />
          <Esqueleto className="h-20" />
          <Esqueleto className="h-20" />
        </div>
      )}

      {processos !== null && processos.length === 0 && (
        <div className="flex flex-col items-center gap-2 rounded-xl bg-surface-2 px-4 py-12 text-center">
          <Inbox aria-hidden className="size-8 text-muted" />
          <p className="font-medium">Nenhum processo analisado ainda</p>
          <p className="max-w-sm text-sm text-muted">Envie os PDFs dos autos na faixa acima. Cada processo aparece aqui assim que chega.</p>
        </div>
      )}

      {processos !== null && processos.length > 0 && (
        <>
          <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            {/* No celular os filtros rolam na horizontal (uma linha só); a partir do tablet quebram linha. */}
            <div
              role="group"
              aria-label="Filtrar por situação da dívida"
              className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 md:flex-wrap md:overflow-visible md:pb-0"
            >
              {(["TODOS", ...ORDEM_DIVIDA] as Filtro[]).map((opcao) => {
                const ativo = filtro === opcao;
                const quantidade = contagem[opcao] ?? 0;
                return (
                  <button
                    key={opcao}
                    type="button"
                    aria-pressed={ativo}
                    disabled={quantidade === 0 && !ativo}
                    onClick={() => setFiltro(opcao)}
                    className={`shrink-0 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40 ${
                      ativo
                        ? "border-accent bg-accent text-accent-foreground"
                        : "border-border bg-surface text-muted hover:border-accent hover:text-foreground"
                    }`}
                  >
                    {opcao === "TODOS" ? "Todos" : DIVIDA[opcao].rotulo} ({quantidade})
                  </button>
                );
              })}
            </div>
            <label className="relative block w-full lg:w-80">
              <span className="sr-only">Buscar por número, parte, juiz, advogado, tribunal ou arquivo</span>
              <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <input
                type="search"
                value={busca}
                onChange={(evento) => setBusca(evento.target.value)}
                placeholder="Buscar número, parte, juiz, tribunal…"
                className="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm placeholder:text-muted"
              />
            </label>
          </div>

          <p role="status" className="mb-2 text-xs text-muted">
            {filtrando ? `Mostrando ${visiveis.length} de ${processos.length}` : `${processos.length} ${processos.length === 1 ? "processo" : "processos"}`}
          </p>

          {visiveis.length === 0 ? (
            <div className="flex flex-col items-center gap-2 rounded-xl bg-surface-2 px-4 py-10 text-center">
              <SearchX aria-hidden className="size-7 text-muted" />
              <p className="font-medium">Nenhum processo corresponde ao filtro</p>
              <button
                type="button"
                onClick={() => {
                  setFiltro("TODOS");
                  setBusca("");
                }}
                className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent"
              >
                Limpar filtros
              </button>
            </div>
          ) : (
            <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
              {visiveis.map((processo) => (
                <LinhaProcesso
                  key={processo.id}
                  processo={processo}
                  fases={fases}
                  apagando={apagando === processo.id}
                  aoApagar={apagar}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </Cartao>
  );
}
