import { avisarNaoAutorizado, lerToken } from "./sessao";
import type { EstadoAnalise, EventoAnalise, Fases, Processo, RespostaEnvio, ResumoProcesso, Token, Usuario } from "./tipos";

// Endereço da API (backend/main.py). NEXT_PUBLIC_* é gravado no bundle durante o `next build`:
// mudou o endereço, rode o build de novo.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export class ErroApi extends Error {
  constructor(
    mensagem: string,
    readonly status?: number,
  ) {
    super(mensagem);
    this.name = "ErroApi";
  }
}

const MENSAGEM_SEM_CONEXAO = `Não foi possível conectar à API (${API_URL}). Ela está rodando? Na raiz do projeto: uvicorn backend.main:app --reload`;

function mensagemDoCorpo(corpo: unknown, status: number): string {
  const detalhe = (corpo as { detail?: unknown } | null)?.detail;
  return typeof detalhe === "string" ? detalhe : `A API respondeu com erro ${status}.`;
}

interface OpcoesPedido extends RequestInit {
  /** false no login: um 401 ali significa "senha errada", não "sessão expirada". */
  tratar401?: boolean;
}

async function pedir<T>(caminho: string, { tratar401 = true, ...init }: OpcoesPedido = {}): Promise<T> {
  const token = lerToken();
  const cabecalhos = new Headers(init.headers);
  if (token) cabecalhos.set("Authorization", `Bearer ${token}`);

  let resposta: Response;
  try {
    resposta = await fetch(`${API_URL}${caminho}`, { ...init, headers: cabecalhos, cache: "no-store" });
  } catch {
    throw new ErroApi(MENSAGEM_SEM_CONEXAO);
  }
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    if (resposta.status === 401 && token && tratar401) avisarNaoAutorizado();
    throw new ErroApi(mensagemDoCorpo(corpo, resposta.status), resposta.status);
  }
  return resposta.status === 204 ? (undefined as T) : ((await resposta.json()) as T);
}

export const api = {
  saude: () => pedir<{ status: string }>("/api/saude"),
  fases: () => pedir<Fases>("/api/fases"),

  // O login é um formulário OAuth2: o campo `username` leva o e-mail.
  login: (email: string, senha: string) =>
    pedir<Token>("/api/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password: senha }),
      tratar401: false,
    }),
  eu: () => pedir<Usuario>("/api/auth/eu"),

  listar: async () => (await pedir<{ processos: ResumoProcesso[] }>("/api/processos")).processos,
  obter: (id: string) => pedir<Processo>(`/api/processos/${encodeURIComponent(id)}`),
  excluir: (id: string) => pedir<void>(`/api/processos/${encodeURIComponent(id)}`, { method: "DELETE" }),
  reanalisar: (id: string) =>
    pedir<ResumoProcesso>(`/api/processos/${encodeURIComponent(id)}/reanalisar`, { method: "POST" }),
};

function lerEvento(bloco: string): EventoAnalise | null {
  let nome = "";
  const dados: string[] = [];
  for (const linha of bloco.split("\n")) {
    if (linha.startsWith("event:")) nome = linha.slice(6).trim();
    else if (linha.startsWith("data:")) dados.push(linha.slice(5).replace(/^ /, ""));
  }
  if (nome === "removido" || nome === "reconectar") return { tipo: nome };
  if (nome !== "estado" && nome !== "fim") return null; // comentário (": ping") ou evento que este front não conhece
  try {
    return { tipo: nome, estado: JSON.parse(dados.join("\n")) as EstadoAnalise };
  } catch {
    return null;
  }
}

/**
 * Acompanha uma análise ao vivo por Server-Sent Events (GET /api/processos/{id}/eventos).
 *
 * Usa fetch e não `EventSource` porque o EventSource não envia o cabeçalho Authorization, e o token não deve ir na URL
 * (ficaria em logs e no histórico). Resolve quando o servidor encerra o fluxo; rejeita com ErroApi se não conseguiu
 * conectar, se a API recusou ou se a conexão caiu no meio. Abortar o `sinal` encerra sem erro.
 * Quem chama decide o que fazer ao terminar (reabrir, ou cair para o polling).
 */
export async function acompanharAnalise(id: string, aoEvento: (evento: EventoAnalise) => void, sinal: AbortSignal): Promise<void> {
  const token = lerToken();
  const cabecalhos = new Headers({ Accept: "text/event-stream" });
  if (token) cabecalhos.set("Authorization", `Bearer ${token}`);

  let resposta: Response;
  try {
    resposta = await fetch(`${API_URL}/api/processos/${encodeURIComponent(id)}/eventos`, { headers: cabecalhos, cache: "no-store", signal: sinal });
  } catch {
    if (sinal.aborted) return;
    throw new ErroApi(MENSAGEM_SEM_CONEXAO);
  }
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    if (resposta.status === 401 && token) avisarNaoAutorizado();
    throw new ErroApi(mensagemDoCorpo(corpo, resposta.status), resposta.status);
  }
  if (!resposta.body || !resposta.headers.get("content-type")?.includes("text/event-stream")) {
    throw new ErroApi("A API não respondeu com um fluxo de eventos.");
  }

  const leitor = resposta.body.pipeThrough(new TextDecoderStream()).getReader();
  let pendente = "";
  try {
    for (;;) {
      const { done, value } = await leitor.read();
      if (done) return;
      pendente += value.replaceAll("\r\n", "\n");
      for (let corte = pendente.indexOf("\n\n"); corte >= 0; corte = pendente.indexOf("\n\n")) {
        const evento = lerEvento(pendente.slice(0, corte));
        pendente = pendente.slice(corte + 2);
        if (evento) aoEvento(evento);
      }
    }
  } catch {
    if (sinal.aborted) return;
    throw new ErroApi(MENSAGEM_SEM_CONEXAO);
  } finally {
    leitor.cancel().catch(() => {});
  }
}

/**
 * Abre o PDF numa nova aba, na página pedida (#page=N).
 *
 * Uma nova aba não envia o cabeçalho Authorization, então pedimos à API um link assinado que vale
 * poucos minutos e só para este PDF. A aba é aberta já no clique (senão o navegador bloqueia o
 * pop-up, pois a resposta da API chega depois) e só então recebe o endereço.
 */
export async function abrirPdf(id: string, pagina?: number): Promise<void> {
  const janela = window.open("about:blank", "_blank");
  try {
    const { url } = await pedir<{ url: string }>(`/api/processos/${encodeURIComponent(id)}/pdf-link`, { method: "POST" });
    const destino = `${API_URL}${url}${pagina ? `#page=${pagina}` : ""}`;
    if (janela) {
      janela.opener = null; // a aba do PDF não precisa (nem deve) enxergar esta
      janela.location.href = destino;
    } else {
      // pop-up bloqueado: abre nesta mesma aba. `destino` é uma URL absoluta da API (outra origem), não uma página do Next.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign(destino);
    }
  } catch (falha) {
    janela?.close();
    throw falha;
  }
}

/**
 * Envia os PDFs. Usa XMLHttpRequest (e não fetch) porque só ele informa o progresso do upload,
 * útil para autos de dezenas de MB. Depois de 100% a API responde na hora: a análise segue em segundo plano.
 */
export function enviarPdfs(arquivos: File[], aoProgredir?: (fracao: number) => void): Promise<RespostaEnvio> {
  return new Promise((resolver, rejeitar) => {
    const formulario = new FormData();
    for (const arquivo of arquivos) formulario.append("arquivos", arquivo, arquivo.name);

    const requisicao = new XMLHttpRequest();
    requisicao.open("POST", `${API_URL}/api/processos`);
    requisicao.responseType = "json";
    const token = lerToken();
    if (token) requisicao.setRequestHeader("Authorization", `Bearer ${token}`);
    requisicao.upload.onprogress = (evento) => {
      if (evento.lengthComputable) aoProgredir?.(evento.loaded / evento.total);
    };
    requisicao.onerror = () => rejeitar(new ErroApi(MENSAGEM_SEM_CONEXAO));
    requisicao.onload = () => {
      if (requisicao.status >= 200 && requisicao.status < 300) {
        resolver(requisicao.response as RespostaEnvio);
        return;
      }
      if (requisicao.status === 401 && token) avisarNaoAutorizado();
      rejeitar(new ErroApi(mensagemDoCorpo(requisicao.response, requisicao.status), requisicao.status));
    };
    requisicao.send(formulario);
  });
}
