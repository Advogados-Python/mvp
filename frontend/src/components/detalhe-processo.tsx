"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, RefreshCw, Trash2 } from "lucide-react";
import { ErroApi, api } from "@/lib/api";
import { emAndamento } from "@/lib/tipos";
import { useFases } from "@/lib/use-fases";
import { useProcessoAoVivo } from "@/lib/use-processo-ao-vivo";
import { AndamentoCredito } from "./andamento-credito";
import { BotaoPdf } from "./botao-pdf";
import { ConfiabilidadeAnalise } from "./confiabilidade-analise";
import { InformacoesProcesso } from "./informacoes-processo";
import { ListaEvidencias } from "./lista-evidencias";
import { ProgressoAnalise } from "./progresso-analise";
import { CartaoRecolhivel } from "./recolhivel";
import { Aviso, Cartao, Chip, Esqueleto } from "./ui";

const EVIDENCIAS_ABERTAS_ATE = 12; // acima disso a seção de evidências começa recolhida (o resumo no título diz quantas são)

const ESTILO_BOTAO =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium hover:border-accent disabled:opacity-40";

// Largura de leitura da página e o respiro entre as seções (12 px no celular, 16 px a partir do tablet).
const MOLDURA = "mx-auto w-full max-w-6xl space-y-3 sm:space-y-4";

export function EsqueletoDetalhe() {
  return (
    <div aria-busy="true" aria-label="Carregando processo" className={MOLDURA}>
      <Esqueleto className="h-5 w-40" />
      <Esqueleto className="h-9 w-2/3" />
      <Esqueleto className="h-32" />
      <Esqueleto className="h-80" />
      <Esqueleto className="h-24" />
    </div>
  );
}

export function DetalheProcesso({ id }: { id: string }) {
  const router = useRouter();
  const fases = useFases();
  const { processo, erro, estado, conexao, recarregar, definirErro } = useProcessoAoVivo(id);
  const [ocupado, setOcupado] = useState(false);

  async function apagar() {
    if (!processo || !window.confirm("Apagar o PDF e o resultado deste processo? Isso não pode ser desfeito.")) return;
    setOcupado(true);
    try {
      await api.excluir(processo.id);
      router.push("/");
    } catch (falha) {
      definirErro(falha as ErroApi);
      setOcupado(false);
    }
  }

  async function reanalisar() {
    setOcupado(true);
    try {
      await api.reanalisar(id);
      recarregar(); // reabre o acompanhamento: o processo volta para a fila e a tela mostra o andamento
    } catch (falha) {
      definirErro(falha as ErroApi);
    } finally {
      setOcupado(false);
    }
  }

  const voltar = (
    <Link href="/" className="inline-flex items-center gap-1.5 rounded-md py-1 text-sm text-muted hover:text-foreground">
      <ArrowLeft aria-hidden className="size-4" />
      Voltar ao histórico
    </Link>
  );

  if (erro && !processo) {
    return (
      <div className={MOLDURA}>
        {voltar}
        {erro.status === undefined ? (
          <Aviso tom="danger" titulo="Sem conexão com a API">
            {erro.message} A página tenta de novo sozinha.
          </Aviso>
        ) : (
          <Aviso tom="danger" titulo={erro.status === 404 ? "Processo não encontrado" : "Não foi possível carregar o processo"}>
            {erro.status === 404 ? "Ele pode ter sido apagado. Volte ao histórico e envie o PDF de novo." : erro.message}
          </Aviso>
        )}
      </div>
    );
  }
  if (!processo) return <EsqueletoDetalhe />;

  const concluido = processo.status === "CONCLUIDO";
  const andamento = emAndamento(processo.status);

  const cabecalho = (
    <header className="space-y-3">
      {voltar}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h1 className="font-mono text-xl font-semibold tracking-tight [overflow-wrap:anywhere] sm:text-2xl">
            {processo.numero_processo ?? (concluido ? "Número não identificado" : processo.arquivo)}
          </h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
            {processo.tribunal && <Chip tom="info">{processo.tribunal}</Chip>}
            <span className="[overflow-wrap:anywhere]">{processo.classe ?? (concluido ? processo.arquivo : "")}</span>
          </p>
        </div>
        {/* No celular os botões dividem a largura; a partir do tablet ficam com o tamanho do texto. */}
        <div className="flex flex-wrap gap-2 [&>*]:flex-1 sm:[&>*]:flex-none">
          <BotaoPdf id={processo.id} className={ESTILO_BOTAO}>
            Abrir PDF
          </BotaoPdf>
          {!andamento && (
            <button type="button" onClick={reanalisar} disabled={ocupado} className={ESTILO_BOTAO}>
              <RefreshCw aria-hidden className="size-4" />
              Analisar de novo
            </button>
          )}
          <button type="button" onClick={apagar} disabled={ocupado} className={`${ESTILO_BOTAO} text-muted hover:border-danger hover:text-danger`}>
            <Trash2 aria-hidden className="size-4" />
            Apagar
          </button>
        </div>
      </div>
    </header>
  );

  // Falha de rede/API depois de o processo já estar na tela: avisa, mantém o que já se sabe e segue tentando.
  const alertaDeErro = erro && (
    <Aviso tom={erro.status === undefined ? "warn" : "danger"} titulo={erro.status === undefined ? "Sem conexão com a API" : "Algo deu errado"}>
      {erro.message}
      {erro.status === undefined && " Mostrando o último estado carregado; continuamos tentando."}
    </Aviso>
  );

  // ---- análise ainda não terminou
  if (andamento) {
    const vivo = estado ?? { status: processo.status, progresso: processo.progresso };
    return (
      <div className={MOLDURA}>
        {cabecalho}
        {alertaDeErro}
        <Cartao titulo="Análise em andamento" descricao="O resultado aparece aqui assim que o servidor terminar.">
          <ProgressoAnalise status={vivo.status} progresso={vivo.progresso} conexao={conexao} />
        </Cartao>
      </div>
    );
  }

  // ---- a análise falhou
  if (processo.status === "FALHOU") {
    return (
      <div className={MOLDURA}>
        {cabecalho}
        {alertaDeErro}
        <Aviso tom="danger" titulo="A análise deste PDF falhou">
          {processo.erro ?? "Erro desconhecido."} Confira o arquivo e tente de novo, ou apague e envie outro PDF.
        </Aviso>
        {processo.progresso?.falhou && (
          <Cartao titulo="Onde a análise parou">
            <ProgressoAnalise status="FALHOU" progresso={processo.progresso} />
          </Cartao>
        )}
      </div>
    );
  }

  // ---- análise concluída: do que identifica o processo, ao andamento do crédito (o centro da página), à confiabilidade e às provas
  return (
    <div className={MOLDURA}>
      {cabecalho}
      {alertaDeErro}
      <InformacoesProcesso processo={processo} />
      <AndamentoCredito processo={processo} fases={fases} />
      <ConfiabilidadeAnalise processo={processo} />
      <CartaoRecolhivel
        compacto
        titulo="Todas as evidências"
        descricao="Cada achado do dicionário de termos, com a página e o trecho de onde veio."
        resumo={`${processo.total_evidencias} ${processo.total_evidencias === 1 ? "achado" : "achados"} · ${processo.evidencias_que_contam} decidem a fase`}
        abertoInicialmente={processo.evidencias.length <= EVIDENCIAS_ABERTAS_ATE}
      >
        <ListaEvidencias evidencias={processo.evidencias} idProcesso={processo.id} fases={fases} />
      </CartaoRecolhivel>
    </div>
  );
}
