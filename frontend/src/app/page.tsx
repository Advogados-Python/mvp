import { Painel } from "@/components/painel";
import { Protegido } from "@/components/protegido";

export default function Home() {
  return (
    <Protegido>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Leitor de processos</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Envie os autos em PDF. O sistema informa em que fase está o crédito contra o Estado e se a dívida já foi paga,
          sempre com a página e o trecho que comprovam.
        </p>
      </div>
      <Painel />
    </Protegido>
  );
}
