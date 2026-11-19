"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { emAndamento } from "@/lib/tipos";
import { useProcessoAoVivo } from "@/lib/use-processo-ao-vivo";
import { AreaUpload, processoParaAbrirAoTerminar } from "./area-upload";
import { ListaProcessos } from "./lista-processos";

/**
 * Acompanha UMA análise que acabou de ser enviada e, quando ela termina (resultado ou falha), abre a página do processo.
 * Usa o mesmo acompanhamento da página de detalhes (SSE, com polling e reconexão como reserva). Só existe enquanto o
 * Painel está na tela: se a pessoa sair, o acompanhamento para e nada a redireciona depois.
 */
function AbrirAoTerminar({ id }: { id: string }) {
  const router = useRouter();
  const { processo } = useProcessoAoVivo(id);
  const terminou = processo !== null && !emAndamento(processo.status);

  useEffect(() => {
    if (terminou) router.push(`/processos/${id}`);
  }, [terminou, id, router]);

  return terminou ? (
    <p role="status" className="sr-only">
      A análise terminou. Abrindo a página do processo.
    </p>
  ) : null;
}

/**
 * Tela inicial, em duas áreas: o envio de PDFs (uma faixa compacta no topo) e o histórico de processos, que é o que ocupa
 * a página. A lista busca de novo depois de cada envio (`versao`). Quando o envio gera um único processo, a análise
 * iniciada é acompanhada e a página dela abre sozinha ao terminar.
 */
export function Painel() {
  const [versao, setVersao] = useState(0);
  const [acompanhado, setAcompanhado] = useState<string | null>(null);

  // Ao sair da tela (ou esconder: o Next mantém a tela anterior em memória), esquece o que estava acompanhando. Sem isto,
  // quem voltasse ao painel dias depois seria levado para uma análise antiga.
  useEffect(() => () => setAcompanhado(null), []);

  return (
    <div className="space-y-4">
      <AreaUpload
        aoConcluir={(resposta) => {
          setVersao((atual) => atual + 1);
          setAcompanhado(processoParaAbrirAoTerminar(resposta)?.id ?? null);
        }}
      />
      <ListaProcessos versao={versao} />
      {acompanhado && <AbrirAoTerminar key={acompanhado} id={acompanhado} />}
    </div>
  );
}
