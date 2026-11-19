import type { Processo } from "@/lib/tipos";
import { Aviso, Cartao, Chip } from "./ui";

const PERCENTUAL_SEM_TEXTO_PARA_ALERTA = 0.5; // o mesmo corte do leitor (backend/leitor/constantes.py)

/**
 * O que pode alterar a confiança na conclusão: páginas que não foram lidas e os avisos que o leitor gerou.
 * Compacta, mas nunca recolhida: alerta crítico não se esconde. Só mostra o que o leitor informou (contagens e avisos);
 * a única afirmação fixa é a limitação do OCR, que o README documenta como não implementado.
 */
export function ConfiabilidadeAnalise({ processo }: { processo: Processo }) {
  const total = processo.total_paginas ?? 0;
  const semTexto = processo.paginas_sem_texto ?? 0;
  const lidas = Math.max(0, total - semTexto);
  const pouquissimoLido = total > 0 && semTexto / total >= PERCENTUAL_SEM_TEXTO_PARA_ALERTA;
  const avisos = processo.avisos;
  const percentualLido = total > 0 ? (lidas / total) * 100 : 0;

  const situacao =
    semTexto > 0 ? (
      <Chip tom={pouquissimoLido ? "danger" : "warn"}>{semTexto === 1 ? "1 página não lida" : `${semTexto} páginas não lidas`}</Chip>
    ) : avisos.length > 0 ? (
      <Chip tom="warn">{avisos.length === 1 ? "1 aviso" : `${avisos.length} avisos`}</Chip>
    ) : (
      <Chip>Todas as páginas lidas</Chip>
    );

  return (
    <Cartao compacto titulo="Confiabilidade da análise" acao={situacao}>
      <div className="space-y-3">
        {pouquissimoLido && (
          <Aviso tom="danger" titulo="Mais da metade do PDF não foi lida">
            Resultado pouco confiável: confira os autos antes de agir.
          </Aviso>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted">Leitura do documento</h3>
            <p className={`mt-0.5 text-sm ${pouquissimoLido ? "font-medium text-warn" : ""}`}>
              {lidas} de {total} {total === 1 ? "página" : "páginas"}
              {semTexto > 0 && <span className="font-normal text-muted"> ({semTexto} sem texto)</span>}
            </p>
            <div role="img" aria-label={`${lidas} de ${total} páginas lidas`} className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-surface-2">
              <span className="h-full bg-accent" style={{ width: `${percentualLido}%` }} />
              {semTexto > 0 && <span className={`h-full ${pouquissimoLido ? "bg-danger" : "bg-warn"}`} style={{ width: `${100 - percentualLido}%` }} />}
            </div>
            {semTexto > 0 && (
              <p className="mt-2 text-sm text-muted">
                Páginas só com imagem (escaneadas) não foram lidas: o que estiver escrito nelas não entra no resultado. O sistema ainda
                não faz OCR.
              </p>
            )}
          </div>

          <div>
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted">Avisos da análise</h3>
            {avisos.length === 0 ? (
              <p className="mt-0.5 text-sm text-muted">Nenhum aviso foi gerado para este PDF.</p>
            ) : (
              <div className="mt-1">
                <Aviso titulo={avisos.length === 1 ? "Leia este aviso antes de confiar no resultado" : "Leia estes avisos antes de confiar no resultado"}>
                  <ul className="list-disc space-y-1 pl-4">
                    {avisos.map((aviso) => (
                      <li key={aviso} className="[overflow-wrap:anywhere]">
                        {aviso}
                      </li>
                    ))}
                  </ul>
                </Aviso>
              </div>
            )}
          </div>
        </div>
      </div>
    </Cartao>
  );
}
