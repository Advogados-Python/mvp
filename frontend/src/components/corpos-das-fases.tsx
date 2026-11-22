import type { Fases, Parte, Processo } from "@/lib/tipos";
import { formatarBytes, formatarDataHora, humanizar } from "@/lib/formatar";
import { rotuloDaFase } from "@/lib/use-fases";
import { BotaoPdf } from "./botao-pdf";
import { EscadaFases } from "./escada-fases";
import { ListaEvidencias } from "./lista-evidencias";
import { SeloDivida } from "./selo-divida";
import { Aviso, Campo, Chip, ou } from "./ui";

/**
 * O que cada fase de leitura produziu para o processo, uma função por módulo do backend:
 * 1 receive · 2 extract · 3 identify · 4 search · 5 validate · 6 finalize.
 * Só apresenta o que o backend já entrega; nenhuma regra de classificação vive aqui.
 */

const PERCENTUAL_SEM_TEXTO_PARA_ALERTA = 0.5; // o mesmo corte do backend (backend/extract/models.py)

export function leituraDe(processo: Processo) {
  const total = processo.total_paginas ?? 0;
  const semTexto = processo.paginas_sem_texto ?? 0;
  const lidas = Math.max(0, total - semTexto);
  return { total, semTexto, lidas, percentualLido: total > 0 ? (lidas / total) * 100 : 0, pouquissimoLido: total > 0 && semTexto / total >= PERCENTUAL_SEM_TEXTO_PARA_ALERTA };
}

const partesPorPapel = (partes: Parte[]): [string, string[]][] => {
  const grupos = new Map<string, string[]>();
  for (const parte of partes) grupos.set(parte.papel, [...(grupos.get(parte.papel) ?? []), parte.nome]);
  return [...grupos];
};

/** Fase 1, documento recebido: o que foi guardado do PDF. */
export function CorpoRecebimento({ processo }: { processo: Processo }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
      <Campo rotulo="Arquivo">{processo.arquivo}</Campo>
      <Campo rotulo="Tamanho">{formatarBytes(processo.tamanho_bytes)}</Campo>
      <Campo rotulo="Recebido em">{formatarDataHora(processo.criado_em)}</Campo>
    </dl>
  );
}

/** Fase 2, extraindo conteúdo: quanto do PDF foi lido. */
export function CorpoExtracao({ processo }: { processo: Processo }) {
  const { total, semTexto, lidas, percentualLido, pouquissimoLido } = leituraDe(processo);
  return (
    <div>
      <p className={`text-sm ${pouquissimoLido ? "font-medium text-warn" : ""}`}>
        {lidas} de {total} {total === 1 ? "página lida" : "páginas lidas"}
        {semTexto > 0 && <span className="font-normal text-muted"> ({semTexto} sem texto)</span>}
      </p>
      <div role="img" aria-label={`${lidas} de ${total} páginas lidas`} className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-surface-2">
        <span className="h-full bg-accent" style={{ width: `${percentualLido}%` }} />
        {semTexto > 0 && <span className={`h-full ${pouquissimoLido ? "bg-danger" : "bg-warn"}`} style={{ width: `${100 - percentualLido}%` }} />}
      </div>
      {semTexto > 0 ? (
        <p className="mt-2 text-sm text-muted">
          Páginas só com imagem (escaneadas) não foram lidas: o que estiver escrito nelas não entra no resultado. O sistema ainda não faz OCR.
        </p>
      ) : (
        <p className="mt-2 text-sm text-muted">Todas as páginas tinham texto e foram lidas.</p>
      )}
    </div>
  );
}

/** Fase 3, identificando o processo: o que foi achado nos autos. */
export function CorpoIdentificacao({ processo }: { processo: Processo }) {
  const grupos = partesPorPapel(processo.partes);
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
      <Campo rotulo="Número do processo">{processo.numero_processo ? <span className="font-mono">{processo.numero_processo}</span> : ou(null)}</Campo>
      <Campo rotulo="Tribunal">{ou(processo.tribunal)}</Campo>
      <Campo rotulo="Classe">{ou(processo.classe)}</Campo>
      <Campo rotulo="Órgão julgador">{ou(processo.orgao_julgador)}</Campo>
      {grupos.length === 0 ? (
        <Campo rotulo="Partes">{ou(null)}</Campo>
      ) : (
        grupos.map(([papel, nomes]) => (
          <Campo key={papel} rotulo={humanizar(papel)}>
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
      <Campo rotulo="Valor da causa">{ou(processo.valor_causa)}</Campo>
      <Campo rotulo="Valor requisitado">{ou(processo.valor_requisitado)}</Campo>
      <Campo rotulo="Advogados">{processo.advogados.length === 0 ? ou(null) : processo.advogados.join("; ")}</Campo>
      <Campo rotulo="OAB (mais citadas)">{processo.oabs.length === 0 ? ou(null) : processo.oabs.join("; ")}</Campo>
      <Campo rotulo="Posição do processo">{processo.data_emissao_pdf ? `PDF gerado em ${processo.data_emissao_pdf}` : ou(null)}</Campo>
    </dl>
  );
}

/** Fase 4, buscando os termos: cada achado do dicionário, com a página e o trecho. */
export function CorpoBusca({ processo, fases }: { processo: Processo; fases: Fases | null }) {
  return (
    <div>
      <p className="mb-3 text-sm text-muted">Cada achado do dicionário de termos, com a página e o trecho de onde veio. Só as evidências que contam decidem a fase.</p>
      <ListaEvidencias evidencias={processo.evidencias} idProcesso={processo.id} fases={fases} />
    </div>
  );
}

/** Fase 5, validando evidências: a escada do crédito, a fase atual, o que ela significa e a evidência que a sustenta. */
export function CorpoValidacao({ processo, fases }: { processo: Processo; fases: Fases | null }) {
  const dividaPaga = processo.divida_paga ?? "SEM_INFORMACAO";
  const fase = processo.fase ?? "SEM_INFORMACAO";
  const significado = fases?.divida_paga.find((item) => item.valor === dividaPaga);
  const principal = processo.evidencia_principal;

  return (
    <div>
      <EscadaFases fases={fases?.fases ?? null} atual={fase} />
      <div className="mt-4 grid gap-4 border-t border-border pt-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Fase atual do crédito</p>
          <h3 className="mt-0.5 text-base font-semibold">{rotuloDaFase(fases, fase)}</h3>
          <p className="mt-0.5 text-sm">{processo.fase_descricao}</p>
          {significado && (
            <>
              <p className="mt-3 text-xs font-medium uppercase tracking-wide text-muted">Ação recomendada</p>
              <p className="mt-0.5 text-sm">
                <span className="text-muted">{significado.significado}</span> <span className="font-medium text-foreground">{significado.acao}</span>
              </p>
            </>
          )}
        </div>
        <div className="rounded-xl border border-border bg-surface-2 p-3">
          <p className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Evidência principal
            {principal?.tipo_documento && <Chip>{principal.tipo_documento}</Chip>}
          </p>
          {principal ? (
            <>
              <blockquote className="mt-2 text-sm leading-relaxed text-muted [overflow-wrap:anywhere]">…{principal.trecho}…</blockquote>
              <div className="mt-3">
                <BotaoPdf id={processo.id} pagina={principal.pagina}>
                  Conferir na pág. {principal.pagina}
                </BotaoPdf>
              </div>
            </>
          ) : (
            <p className="mt-2 text-sm text-muted">Nenhum trecho do PDF decidiu a fase deste processo.</p>
          )}
        </div>
      </div>
    </div>
  );
}

/** Fase 6, finalizando resultado: o que foi gravado no fim da análise. */
export function CorpoFinalizacao({ processo }: { processo: Processo }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
      <Campo rotulo="Situação">Análise concluída</Campo>
      <Campo rotulo="Gravado em">{formatarDataHora(processo.concluido_em ?? processo.criado_em)}</Campo>
      <Campo rotulo="Dívida paga gravada">
        <SeloDivida valor={processo.divida_paga ?? "SEM_INFORMACAO"} />
      </Campo>
    </dl>
  );
}

/** A resposta em destaque, no topo: o que a validação concluiu (a fase 5 mostra o detalhe). */
export function ResultadoEmDestaque({ processo, fases }: { processo: Processo; fases: Fases | null }) {
  const dividaPaga = processo.divida_paga ?? "SEM_INFORMACAO";
  const fase = processo.fase ?? "SEM_INFORMACAO";
  const significado = fases?.divida_paga.find((item) => item.valor === dividaPaga);
  const etapas = fases?.fases.filter((item) => item.ordem > 0) ?? [];
  const ordemAtual = fases?.fases.find((item) => item.codigo === fase)?.ordem ?? 0;
  const principal = processo.evidencia_principal;

  return (
    <section aria-label="Resultado da análise" className="vidro rounded-2xl p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div>
          <p className="text-xs text-muted">A dívida já foi paga?</p>
          <div className="mt-1">
            <SeloDivida valor={dividaPaga} grande />
          </div>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Fase atual do crédito</p>
          <p className="mt-0.5 font-semibold">{rotuloDaFase(fases, fase)}</p>
          {ordemAtual > 0 && etapas.length > 0 && (
            <p className="text-xs tabular-nums text-muted">
              Etapa {ordemAtual} de {etapas.length}
            </p>
          )}
        </div>
        {significado && (
          <p className="min-w-0 basis-full text-sm lg:flex-1 lg:basis-0 lg:min-w-64">
            <span className="text-muted">{significado.significado}</span> <span className="font-medium text-foreground">{significado.acao}</span>
          </p>
        )}
        {principal && (
          <BotaoPdf id={processo.id} pagina={principal.pagina} className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium hover:border-accent">
            Conferir no PDF · pág. {principal.pagina}
          </BotaoPdf>
        )}
      </div>
    </section>
  );
}

/** Os avisos da leitura, sempre à vista: alerta crítico não se esconde dentro de uma fase recolhida. */
export function AvisosDaAnalise({ processo }: { processo: Processo }) {
  const { pouquissimoLido } = leituraDe(processo);
  const avisos = processo.avisos;
  if (!pouquissimoLido && avisos.length === 0) return null;
  return (
    <div className="space-y-3 sm:space-y-4">
      {pouquissimoLido && (
        <Aviso tom="danger" titulo="Mais da metade do PDF não foi lida">
          Resultado pouco confiável: confira os autos antes de agir.
        </Aviso>
      )}
      {avisos.length > 0 && (
        <Aviso titulo={avisos.length === 1 ? "Leia este aviso antes de confiar no resultado" : "Leia estes avisos antes de confiar no resultado"}>
          <ul className="list-disc space-y-1 pl-4">
            {avisos.map((aviso) => (
              <li key={aviso} className="[overflow-wrap:anywhere]">
                {aviso}
              </li>
            ))}
          </ul>
        </Aviso>
      )}
    </div>
  );
}
