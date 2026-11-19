import type { Metadata } from "next";
import { Suspense } from "react";
import { DetalheProcesso, EsqueletoDetalhe } from "@/components/detalhe-processo";
import { Protegido } from "@/components/protegido";

export const metadata: Metadata = { title: "Processo" };

export default function PaginaProcesso({ params }: PageProps<"/processos/[id]">) {
  // `params` é dado de runtime: com Cache Components ele só pode ser lido dentro de um <Suspense>.
  // O esqueleto faz parte do shell estático; o restante é buscado no navegador, direto na API.
  return (
    <Suspense fallback={<EsqueletoDetalhe />}>
      <ConteudoProcesso params={params} />
    </Suspense>
  );
}

async function ConteudoProcesso({ params }: { params: PageProps<"/processos/[id]">["params"] }) {
  const { id } = await params;
  return (
    <Protegido>
      <DetalheProcesso id={id} />
    </Protegido>
  );
}
