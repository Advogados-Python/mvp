import type { Fases, Processo } from "@/lib/tipos";
import { rotuloDaFase } from "@/lib/use-fases";
import { BotaoPdf } from "./botao-pdf";
import { EscadaFases } from "./escada-fases";
import { SeloDivida } from "./selo-divida";
import { Cartao, Chip } from "./ui";

/**
 * O centro da página: onde o crédito está e o que prova isso, num só componente.
 * A escada das fases (reaproveita EscadaFases), a fase atual em destaque, a situação da dívida, o que a fase significa,
 * a ação recomendada e a evidência principal, com o link para a página exata do PDF.
 * Só apresenta o que o leitor e a API já informam: nenhuma regra de classificação vive aqui.
 */
export function AndamentoCredito({ processo, fases }: { processo: Processo; fases: Fases | null }) {
  const dividaPaga = processo.divida_paga ?? "SEM_INFORMACAO";
  const fase = processo.fase ?? "SEM_INFORMACAO";
  const significado = fases?.divida_paga.find((item) => item.valor === dividaPaga);
  const principal = processo.evidencia_principal;

  const etapas = fases?.fases.filter((item) => item.ordem > 0) ?? []; // ordem 0 = "sem informação"
  const ordemAtual = fases?.fases.find((item) => item.codigo === fase)?.ordem ?? 0;

  return (
    <Cartao
      compacto
      titulo="Andamento do crédito"
      descricao="Fase processual identificada nos autos: vale a mais avançada que tenha evidência confiável."
      acao={
        ordemAtual > 0 && etapas.length > 0 ? (
          <span className="text-xs font-medium tabular-nums text-muted">
            Etapa {ordemAtual} de {etapas.length}
          </span>
        ) : undefined
      }
    >
      <EscadaFases fases={fases?.fases ?? null} atual={fase} />

      <div className="mt-4 grid gap-4 border-t border-border pt-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div>
          <p className="text-sm text-muted">A dívida já foi paga?</p>
          <div className="mt-1.5">
            <SeloDivida valor={dividaPaga} grande />
          </div>
          <p className="mt-4 text-xs font-medium uppercase tracking-wide text-muted">Fase atual do crédito</p>
          <h3 className="mt-0.5 text-base font-semibold">{rotuloDaFase(fases, fase)}</h3>
          <p className="mt-0.5 text-sm">{processo.fase_descricao}</p>
          {significado && (
            <>
              <p className="mt-3 text-xs font-medium uppercase tracking-wide text-muted">Ação recomendada</p>
              <p className="mt-0.5 text-sm">
                <span className="text-muted">{significado.significado}</span>{" "}
                <span className="font-medium text-foreground">{significado.acao}</span>
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
    </Cartao>
  );
}
