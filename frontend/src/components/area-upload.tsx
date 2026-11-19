"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { ChevronDown, CircleCheck, FileText, LoaderCircle, Upload, X } from "lucide-react";
import { enviarPdfs } from "@/lib/api";
import { formatarBytes } from "@/lib/formatar";
import type { RespostaEnvio, ResumoProcesso } from "@/lib/tipos";
import { Recolhivel } from "./recolhivel";
import { Aviso, Cartao } from "./ui";

const MAX_ARQUIVOS = 20; // o mesmo limite da API (RIBEIRO_MAX_ARQUIVOS_POR_ENVIO)

const ehPdf = (arquivo: File) => arquivo.type === "application/pdf" || arquivo.name.toLowerCase().endsWith(".pdf");
const chaveDe = (arquivo: File) => `${arquivo.name}|${arquivo.size}|${arquivo.lastModified}`;
const plural = (n: number, singular: string, plural: string) => `${n} ${n === 1 ? singular : plural}`;

/**
 * O processo cuja página deve abrir sozinha quando a análise terminar: só quando o envio gerou UM processo. Com vários
 * PDFs no mesmo envio não existe "a" página (qual deles?), então a pessoa fica no histórico, que mostra cada um ao vivo.
 */
export function processoParaAbrirAoTerminar(resposta: RespostaEnvio): ResumoProcesso | null {
  return resposta.processos.length === 1 ? resposta.processos[0] : null;
}

/**
 * Envio de PDFs, numa faixa horizontal. Aqui só existe o progresso do ENVIO (bytes que já subiram, medidos de verdade).
 * O andamento da ANÁLISE é outra coisa, vem do servidor e aparece no histórico e na página do processo.
 */
export function AreaUpload({ aoConcluir }: { aoConcluir: (resposta: RespostaEnvio) => void }) {
  const idLista = useId();
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [listaAberta, setListaAberta] = useState(true);
  const [arrastando, setArrastando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [progresso, setProgresso] = useState(0); // fração dos bytes já enviados
  const [resposta, setResposta] = useState<RespostaEnvio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [recusados, setRecusados] = useState(0); // não eram PDF
  const [excedentes, setExcedentes] = useState(0); // passaram do limite por envio

  const totalBytes = arquivos.reduce((soma, arquivo) => soma + arquivo.size, 0);
  const percentual = Math.round(progresso * 100);

  function adicionar(novos: FileList | File[]) {
    const lista = Array.from(novos);
    const pdfs = lista.filter(ehPdf);
    const vistos = new Set(arquivos.map(chaveDe));
    const unicos = pdfs.filter((arquivo) => {
      const chave = chaveDe(arquivo);
      if (vistos.has(chave)) return false;
      vistos.add(chave);
      return true;
    });
    const vagas = Math.max(0, MAX_ARQUIVOS - arquivos.length);
    setRecusados(lista.length - pdfs.length);
    setExcedentes(Math.max(0, unicos.length - vagas));
    setResposta(null);
    setErro(null);
    setArquivos([...arquivos, ...unicos.slice(0, vagas)]);
  }

  async function enviar() {
    setEnviando(true);
    setProgresso(0);
    setResposta(null);
    setErro(null);
    try {
      const recebida = await enviarPdfs(arquivos, setProgresso);
      setResposta(recebida);
      setArquivos([]);
      aoConcluir(recebida);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Falha ao enviar os arquivos.");
    } finally {
      setEnviando(false);
    }
  }

  const avisos = [
    recusados > 0 && `${plural(recusados, "arquivo ignorado", "arquivos ignorados")}: só PDFs são aceitos.`,
    excedentes > 0 && `${plural(excedentes, "arquivo ignorado", "arquivos ignorados")}: o limite é de ${MAX_ARQUIVOS} PDFs por envio.`,
  ].filter(Boolean);

  return (
    <Cartao compacto>
      <label
        onDragOver={(evento) => {
          evento.preventDefault();
          if (!enviando) setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(evento) => {
          evento.preventDefault();
          setArrastando(false);
          if (!enviando) adicionar(evento.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col gap-3 rounded-xl border-2 border-dashed px-4 py-3 transition-colors focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent sm:flex-row sm:items-center sm:justify-between ${
          arrastando ? "border-accent bg-accent-soft" : "border-border bg-surface-2 hover:border-accent"
        } ${enviando ? "pointer-events-none opacity-60" : ""}`}
      >
        <input
          type="file"
          accept="application/pdf,.pdf"
          multiple
          disabled={enviando}
          className="sr-only"
          onChange={(evento) => {
            if (evento.target.files) adicionar(evento.target.files);
            evento.target.value = ""; // permite escolher o mesmo arquivo de novo
          }}
        />
        <span className="flex min-w-0 items-center gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
            <Upload aria-hidden className="size-5" />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-medium sm:text-base">
              Arraste os PDFs aqui ou <span className="text-accent underline underline-offset-2">escolha os arquivos</span>
            </span>
            <span className="block text-xs text-muted">Autos completos (PJe, e-SAJ). Até {MAX_ARQUIVOS} PDFs por vez.</span>
          </span>
        </span>
        <span aria-hidden className="inline-flex shrink-0 items-center justify-center rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium">
          Escolher arquivos
        </span>
      </label>

      {avisos.length > 0 && (
        <p role="status" className="mt-2 text-sm text-warn">
          {avisos.join(" ")}
        </p>
      )}

      {arquivos.length > 0 && (
        <div className="mt-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              aria-expanded={listaAberta}
              aria-controls={idLista}
              onClick={() => setListaAberta((atual) => !atual)}
              className="inline-flex items-center gap-1.5 rounded-md py-1 text-sm font-medium"
            >
              <ChevronDown aria-hidden className={`size-4 text-muted transition-transform duration-300 ${listaAberta ? "rotate-180" : ""}`} />
              {plural(arquivos.length, "arquivo selecionado", "arquivos selecionados")}
              <span className="font-normal text-muted">· {formatarBytes(totalBytes)}</span>
            </button>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={enviando}
                onClick={() => {
                  setArquivos([]);
                  setRecusados(0);
                  setExcedentes(0);
                }}
                className="rounded-md px-2 py-1.5 text-sm text-muted hover:text-foreground disabled:opacity-40"
              >
                Limpar
              </button>
              <button
                type="button"
                onClick={enviar}
                disabled={enviando}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {enviando && <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />}
                {arquivos.length > 1 ? `Analisar ${arquivos.length} PDFs` : "Analisar PDF"}
              </button>
            </div>
          </div>

          <Recolhivel aberto={listaAberta} id={idLista}>
            <ul className="mt-2 max-h-52 divide-y divide-border overflow-y-auto rounded-xl border border-border">
              {arquivos.map((arquivo) => (
                <li key={chaveDe(arquivo)} className="flex items-center gap-3 px-3 py-1.5 text-sm">
                  <FileText aria-hidden className="size-4 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1 truncate" title={arquivo.name}>
                    {arquivo.name}
                  </span>
                  <span className="shrink-0 text-xs text-muted">{formatarBytes(arquivo.size)}</span>
                  <button
                    type="button"
                    disabled={enviando}
                    aria-label={`Remover ${arquivo.name}`}
                    onClick={() => setArquivos((atuais) => atuais.filter((outro) => outro !== arquivo))}
                    className="grid size-8 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-foreground disabled:opacity-40"
                  >
                    <X aria-hidden className="size-4" />
                  </button>
                </li>
              ))}
            </ul>
          </Recolhivel>
        </div>
      )}

      {enviando && (
        <div className="mt-3">
          {/* Progresso do ENVIO (bytes que já subiram, medidos pelo navegador). Não é o da análise. */}
          <div
            role="progressbar"
            aria-label="Envio dos arquivos"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percentual}
            className="h-2 overflow-hidden rounded-full bg-surface-2"
          >
            <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${percentual}%` }} />
          </div>
          <p role="status" className="mt-1.5 text-xs text-muted">
            {progresso < 1
              ? `Enviando os arquivos… ${percentual}%`
              : "Arquivos enviados. Aguardando o servidor confirmar o recebimento…"}{" "}
            A análise só começa depois, no servidor.
          </p>
        </div>
      )}

      {erro && (
        <div className="mt-3">
          <Aviso tom="danger" titulo="Não foi possível enviar">
            {erro}
          </Aviso>
        </div>
      )}

      {resposta && (
        <div className="mt-3 space-y-3">
          {resposta.processos.length > 0 && (
            <div role="status" className="rounded-xl border border-border bg-surface-2 p-3">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <CircleCheck aria-hidden className="size-4 text-ok" />
                {plural(resposta.processos.length, "PDF recebido", "PDFs recebidos")} pelo servidor
              </p>
              <p className="mt-0.5 text-xs text-muted">
                {processoParaAbrirAoTerminar(resposta)
                  ? "A análise roda em segundo plano. Se você continuar nesta tela, a página do processo abre sozinha quando ela terminar; a etapa aparece no histórico abaixo."
                  : "A análise roda em segundo plano: acompanhe cada uma no histórico abaixo ou abra o processo."}
              </p>
              <ul className="mt-2 flex flex-wrap gap-2">
                {resposta.processos.map((processo) => (
                  <li key={processo.id} className="flex max-w-full items-center rounded-lg border border-border bg-surface px-2 py-1 text-sm">
                    <Link href={`/processos/${processo.id}`} className="min-w-0 truncate text-accent underline underline-offset-2">
                      {processo.numero_processo ?? processo.arquivo}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {resposta.falhas.length > 0 && (
            <Aviso tom="danger" titulo={plural(resposta.falhas.length, "arquivo foi recusado", "arquivos foram recusados")}>
              <ul className="list-disc space-y-1 pl-4">
                {resposta.falhas.map((falha, indice) => (
                  <li key={`${falha.arquivo}-${indice}`}>
                    <span className="font-medium">{falha.arquivo}</span>: {falha.erro}
                  </li>
                ))}
              </ul>
            </Aviso>
          )}
        </div>
      )}

      <p className="mt-3 text-xs text-muted">
        Autos têm dados pessoais (LGPD). Os PDFs ficam só no servidor da API, visíveis apenas para a sua conta, e podem ser apagados no
        histórico.
      </p>
    </Cartao>
  );
}
