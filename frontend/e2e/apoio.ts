import type { APIRequestContext, Page } from "@playwright/test";

export const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8101";
export const EMAIL = process.env.E2E_EMAIL ?? "";
export const SENHA = process.env.E2E_SENHA ?? "";

// ---------------------------------------------------------------- PDFs gerados na hora (sem arquivos no repositório)
/** Um PDF válido de texto simples (Helvetica/WinAnsi): cada item de `paginas` é uma página; cada string, uma linha. */
export function gerarPdf(paginas: string[][], fonte = 11): Buffer {
  const escapar = (texto: string) => texto.replace(/[\\()]/g, "\\$&");
  const partes: string[] = ["%PDF-1.4\n"];
  const offsets: number[] = [];
  let tamanho = partes[0].length;
  const objeto = (corpo: string) => {
    offsets.push(tamanho);
    const texto = `${offsets.length} 0 obj\n${corpo}\nendobj\n`;
    partes.push(texto);
    tamanho += texto.length;
  };
  objeto("<< /Type /Catalog /Pages 2 0 R >>");
  objeto(`<< /Type /Pages /Kids [${paginas.map((_, i) => `${4 + i * 2} 0 R`).join(" ")}] /Count ${paginas.length} >>`);
  objeto("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
  paginas.forEach((linhas, i) => {
    objeto(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${5 + i * 2} 0 R >>`);
    const fluxo = `BT /F1 ${fonte} Tf ${fonte + 2} TL 36 760 Td\n${linhas.map((linha) => `(${escapar(linha)}) '`).join("\n")}\nET`;
    objeto(`<< /Length ${fluxo.length} >>\nstream\n${fluxo}\nendstream`);
  });
  const inicioTabela = tamanho;
  const tabela = offsets.map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  partes.push(`xref\n0 ${offsets.length + 1}\n0000000000 65535 f \n${tabela}trailer\n<< /Size ${offsets.length + 1} /Root 1 0 R >>\nstartxref\n${inicioTabela}\n%%EOF\n`);
  return Buffer.from(partes.join(""), "latin1");
}

/** Pago: a página 2 diz "Julgo extinta a execução pelo pagamento." (o leitor classifica como QUITADO / dívida paga). */
export const PDF_PAGO = () => gerarPdf([["Processo Numero: 1234567-89.2025.4.01.3500"], ["Julgo extinta a execução pelo pagamento."]]);
export const PDF_REQUISICAO = () => gerarPdf([["Processo Numero: 7654321-10.2024.8.09.0051"], ["Expeça-se ofício requisitório."]]);
/** Começa com "%PDF-" (o upload aceita) mas não abre: a análise falha ao ler. */
export const PDF_CORROMPIDO = () => Buffer.from("%PDF-1.4\nisto nao e um pdf de verdade\n", "latin1");
/** Muitas páginas de texto denso: a análise leva vários segundos, dá tempo de ver as etapas e as contagens reais. */
export function pdfPesado(paginas: number): Buffer {
  const linha = "Execução contra a Fazenda Pública do Estado. Aguarde-se o pagamento após o trânsito em julgado, intime-se a parte.";
  const corpo = (i: number) => Array.from({ length: 70 }, (_, j) => `${linha.slice(0, 60 + (j % 50))} ${i}-${j}`);
  return gerarPdf(Array.from({ length: paginas }, (_, i) => (i === 0 ? ["Processo Numero: 4444444-44.2022.8.09.0051", ...corpo(i)] : corpo(i))), 7);
}

// ---------------------------------------------------------------- sessão e API
export async function tokenDaApi(request: APIRequestContext): Promise<string> {
  // Os testes APAGAM todos os processos da conta que usam: só rodam com uma conta de teste, nunca com a de verdade.
  if (!EMAIL || !SENHA) throw new Error("Defina E2E_EMAIL e E2E_SENHA (conta da stack de TESTE; veja playwright.config.ts).");
  if (!/^e2e/i.test(EMAIL)) throw new Error(`Por segurança, E2E_EMAIL deve começar com "e2e" (os testes apagam todos os processos da conta; recebido: ${EMAIL}).`);
  const resposta = await request.post(`${API_URL}/api/auth/login`, { form: { username: EMAIL, password: SENHA } });
  if (!resposta.ok()) throw new Error(`Login na API de teste falhou (${resposta.status()}). Confira E2E_EMAIL/E2E_SENHA/E2E_API_URL.`);
  return (await resposta.json()).access_token;
}

/** Entra sem passar pela tela de login: grava o token onde o app o procura (localStorage "ribeiro.token"). */
export async function entrar(page: Page, token: string): Promise<void> {
  await page.addInitScript((valor) => window.localStorage.setItem("ribeiro.token", valor), token);
}

export async function limparProcessos(request: APIRequestContext, token: string): Promise<void> {
  const cabecalhos = { Authorization: `Bearer ${token}` };
  const { processos } = await (await request.get(`${API_URL}/api/processos`, { headers: cabecalhos })).json();
  for (const processo of processos) await request.delete(`${API_URL}/api/processos/${processo.id}`, { headers: cabecalhos });
}

export async function enviarPelaApi(request: APIRequestContext, token: string, nome: string, conteudo: Buffer): Promise<string> {
  const resposta = await request.post(`${API_URL}/api/processos`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: { arquivos: { name: nome, mimeType: "application/pdf", buffer: conteudo } },
  });
  const corpo = await resposta.json();
  if (!resposta.ok() || corpo.processos.length === 0) throw new Error(`Envio falhou: ${JSON.stringify(corpo)}`);
  return corpo.processos[0].id;
}

export async function esperarStatus(request: APIRequestContext, token: string, id: string, status: string, limiteMs = 60_000) {
  const fim = Date.now() + limiteMs;
  for (;;) {
    const dados = await (await request.get(`${API_URL}/api/processos/${id}`, { headers: { Authorization: `Bearer ${token}` } })).json();
    if (dados.status === status) return dados;
    if (Date.now() > fim) throw new Error(`processo ${id} não chegou a ${status} (último: ${dados.status})`);
    await new Promise((resolver) => setTimeout(resolver, 200));
  }
}

// ---------------------------------------------------------------- respostas fabricadas (UI determinística)
const ID_FALSO = "a".repeat(32);

export function resumoFalso(sobrescritas: Record<string, unknown> = {}) {
  return {
    id: ID_FALSO,
    arquivo: "autos.pdf",
    tamanho_bytes: 2_400_000,
    criado_em: "2026-11-18T14:00:00Z",
    concluido_em: "2026-11-18T14:02:00Z",
    status: "CONCLUIDO",
    erro: null,
    progresso: null,
    total_paginas: 120,
    paginas_sem_texto: 0,
    numero_processo: "0001234-56.2024.8.09.0051",
    tribunal: "TJGO",
    classe: "Cumprimento de Sentença contra a Fazenda Pública",
    orgao_julgador: "1ª Vara da Fazenda Pública Estadual",
    valor_causa: "R$ 120.000,00",
    valor_requisitado: "R$ 118.500,00",
    data_emissao_pdf: "10/11/2026",
    partes: [
      { nome: "MARIA APARECIDA DA SILVA SANTOS", papel: "EXEQUENTE" },
      { nome: "ESTADO DE GOIÁS", papel: "EXECUTADO" },
    ],
    advogados: ["JOÃO CARLOS PEREIRA"],
    oabs: ["OAB/GO 12345 (30x)"],
    juiz: "Dr. Carlos Eduardo Lima",
    fase: "REQUISICAO",
    fase_descricao: "Foi expedido o ofício requisitório.",
    divida_paga: "NAO",
    avisos: [],
    evidencia_principal: { fase: "REQUISICAO", termo: "oficio_requisitorio", pagina: 42, trecho: "determino a expedição de ofício requisitório", tipo_documento: "Decisão", hipotetico: false, origem_confiavel: true, conta: true },
    total_evidencias: 3,
    evidencias_que_contam: 2,
    ...sobrescritas,
  };
}

export function evidenciasFalsas(quantidade: number) {
  return Array.from({ length: quantidade }, (_, i) => ({
    fase: i % 3 === 0 ? "REQUISICAO" : i % 3 === 1 ? "SENTENCA" : "TRANSITO_EM_JULGADO",
    termo: `termo_${i}`,
    pagina: i + 1,
    trecho: `trecho da evidência número ${i} com texto suficiente para quebrar linha em telas pequenas e conferir o layout`,
    tipo_documento: "Decisão",
    hipotetico: i % 5 === 0,
    origem_confiavel: i % 7 !== 0,
    conta: i % 5 !== 0 && i % 7 !== 0,
  }));
}

export function detalheFalso(sobrescritas: Record<string, unknown> = {}, evidencias = 3) {
  const lista = evidenciasFalsas(evidencias);
  return { ...resumoFalso({ total_evidencias: lista.length, evidencias_que_contam: lista.filter((e) => e.conta).length, ...sobrescritas }), evidencias: lista };
}

const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "authorization,content-type" };

/**
 * Responde a lista e o detalhe com dados fabricados (o login, as fases e o resto continuam reais).
 * `detalhe` pode ser uma função para devolver uma resposta diferente a cada consulta (simula o andamento no servidor).
 */
/** Uma resposta fabricada; "ABORTAR" = a rede cai nesta consulta. */
type Resposta = object | "ABORTAR";

export async function simularApi(
  page: Page,
  { lista, detalhe, eventos = "abortar" }: { lista?: object[]; detalhe?: Resposta | ((chamada: number) => Resposta); eventos?: "abortar" | { corpo: string } },
) {
  let chamadas = 0;
  await page.route(/\/api\/processos$/, (rota) =>
    rota.request().method() === "GET" && lista ? rota.fulfill({ headers: CORS, json: { processos: lista, total: lista.length } }) : rota.fallback(),
  );
  await page.route(/\/api\/processos\/[0-9a-f]{32}$/, (rota) => {
    if (rota.request().method() !== "GET" || detalhe === undefined) return rota.fallback();
    chamadas += 1;
    const resposta = typeof detalhe === "function" ? detalhe(chamadas) : detalhe;
    return resposta === "ABORTAR" ? rota.abort("failed") : rota.fulfill({ headers: CORS, json: resposta });
  });
  await page.route(/\/api\/processos\/[0-9a-f]{32}\/eventos$/, (rota) =>
    eventos === "abortar"
      ? rota.abort("failed")
      : rota.fulfill({ headers: { ...CORS, "content-type": "text/event-stream", "cache-control": "no-store" }, body: eventos.corpo }),
  );
}

/** Um processo na fila/analisando/falhou, como a API entrega: sem os campos do resultado, só status e progresso. */
export function processoEmAndamentoFalso(status: "PENDENTE" | "ANALISANDO" | "FALHOU", progresso: unknown = null, sobrescritas: Record<string, unknown> = {}) {
  return {
    ...detalheFalso({
      status,
      progresso,
      concluido_em: null,
      erro: status === "FALHOU" ? "Não foi possível abrir o arquivo como PDF (corrompido ou formato inválido)." : null,
      numero_processo: null,
      tribunal: null,
      classe: null,
      orgao_julgador: null,
      valor_causa: null,
      valor_requisitado: null,
      data_emissao_pdf: null,
      total_paginas: null,
      paginas_sem_texto: null,
      partes: [],
      advogados: [],
      oabs: [],
      juiz: null,
      fase: null,
      fase_descricao: null,
      divida_paga: null,
      avisos: [],
      evidencia_principal: null,
      total_evidencias: 0,
      evidencias_que_contam: 0,
      ...sobrescritas,
    }, 0),
  };
}
