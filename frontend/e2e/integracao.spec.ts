import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  API_URL, EMAIL, PDF_CORROMPIDO, PDF_PAGO, SENHA, entrar, enviarPelaApi, esperarStatus, gerarPdf, limparProcessos, pdfPesado, tokenDaApi,
} from "./apoio";

let token: string;

test.beforeAll(async ({ request }) => {
  token = await tokenDaApi(request);
});
test.beforeEach(async ({ page, request }) => {
  await limparProcessos(request, token);
  await entrar(page, token);
});

const entrada = (page: Page) => page.locator('input[type="file"]');
const pdf = (nome: string, buffer: Buffer) => ({ name: nome, mimeType: "application/pdf", buffer });
// uma linha do histórico é o item com o botão "Apagar <processo>" (a lista de arquivos do envio e o resumo do envio também são <li>)
const linhaDo = (page: Page, texto: string | RegExp) =>
  page.locator("main ul > li").filter({ has: page.getByRole("button", { name: /^Apagar / }) }).filter({ hasText: texto });

test("login pela tela leva ao painel; o primeiro Tab é o atalho para o conteúdo", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.removeItem("ribeiro.token")); // roda depois do que entrou: fica deslogado
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("E-mail").fill(EMAIL);
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Leitor de processos" })).toBeVisible();

  await page.goto("/"); // página nova: o ponto de partida do foco é o topo (depois da navegação do login seria o botão que sumiu)
  await page.keyboard.press("Tab");
  const atalho = page.getByRole("link", { name: "Pular para o conteúdo" });
  await expect(atalho).toBeFocused();
  await expect(atalho).toBeVisible(); // só aparece quando recebe foco
  await page.keyboard.press("Enter");
  await expect(page.locator("#conteudo")).toBeFocused();
});

test("o logo do escritório (logo.jpeg) aparece, carregado, no cabeçalho e na tela de login", async ({ page }) => {
  const carregado = (img: Locator) => img.evaluate((el) => (el as HTMLImageElement).complete && (el as HTMLImageElement).naturalWidth > 0);
  await page.goto("/");
  const noCabecalho = page.getByRole("banner").locator("img");
  await expect(noCabecalho).toHaveCount(1);
  await expect(noCabecalho).toHaveAttribute("src", /logo\.jpeg/);
  await expect.poll(() => carregado(noCabecalho)).toBe(true);
  await expect(page.getByRole("banner").locator("svg.lucide-scale")).toHaveCount(0); // o ícone antigo saiu

  await page.addInitScript(() => window.localStorage.removeItem("ribeiro.token"));
  await page.goto("/login");
  const logos = page.locator("img[src*='logo.jpeg']");
  await expect(logos).toHaveCount(2); // cabeçalho + formulário
  for (const i of [0, 1]) await expect.poll(() => carregado(logos.nth(i))).toBe(true);
  await page.screenshot({ path: "test-results/telas/logo-login.png" });
});

test("painel: envio compacto, histórico principal e estado vazio", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Histórico de processos" })).toBeVisible();
  await expect(page.getByText("Nenhum processo analisado ainda")).toBeVisible();
  const faixa = page.getByText("Arraste os PDFs aqui").locator("xpath=ancestor::label");
  expect((await faixa.boundingBox())!.height).toBeLessThan(100); // faixa horizontal, não o cartão grande de antes
});

test("envia um PDF, a análise termina e a página do processo abre sozinha, com o PDF na página da evidência", async ({ page }) => {
  await page.goto("/");
  await entrada(page).setInputFiles(pdf("autos-quitados.pdf", PDF_PAGO()));
  await expect(page.getByText("1 arquivo selecionado")).toBeVisible();
  await page.getByRole("button", { name: "Analisar PDF" }).click();

  await expect(page).toHaveURL(/\/processos\/[0-9a-f]{32}$/, { timeout: 20_000 }); // sem clicar em nada
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("1234567-89.2025.4.01.3500");
  await expect(page.getByText("A dívida já foi paga?")).toBeVisible();
  await expect(page.getByText("Fase atual do crédito")).toBeVisible();
  await expect(page.getByText("Ação recomendada")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Andamento do crédito" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Confiabilidade da análise" })).toBeVisible();

  // a evidência principal aponta para a página 2 do PDF, via link assinado
  const conferir = page.getByRole("button", { name: /Conferir na pág\. 2/ });
  const pedido = page.waitForRequest((r) => /\/api\/processos\/[0-9a-f]{32}\/pdf-link$/.test(r.url()));
  const [popup] = await Promise.all([page.waitForEvent("popup"), conferir.click()]);
  await pedido;
  await popup.waitForURL(/\/api\/processos\/[0-9a-f]{32}\/pdf\?assinatura=.+#page=2$/);
  await popup.close();

  // a lista de evidências continua com o link para a página de cada achado
  await expect(page.getByRole("button", { name: "Todas as evidências", expanded: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /pág\. 2 .*abre o PDF/ }).first()).toBeVisible();
});

test("arquivo que não é PDF e excesso de arquivos são avisados, e a lista de arquivos recolhe", async ({ page }) => {
  await page.goto("/");
  await entrada(page).setInputFiles({ name: "notas.txt", mimeType: "text/plain", buffer: Buffer.from("oi") });
  await expect(page.getByText("1 arquivo ignorado: só PDFs são aceitos.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Analisar/ })).toHaveCount(0);

  const muitos = Array.from({ length: 22 }, (_, i) => pdf(`autos-${String(i).padStart(2, "0")}.pdf`, gerarPdf([[`pagina ${i}`]])));
  await entrada(page).setInputFiles(muitos);
  await expect(page.getByText("20 arquivos selecionados")).toBeVisible();
  await expect(page.getByText("2 arquivos ignorados: o limite é de 20 PDFs por envio.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Analisar 20 PDFs" })).toBeVisible();

  const alternar = page.getByRole("button", { name: /20 arquivos selecionados/ });
  await expect(alternar).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("button", { name: "Remover autos-00.pdf" })).toBeVisible();
  await alternar.click();
  await expect(alternar).toHaveAttribute("aria-expanded", "false");
  // recolhida: a região fica inert (fora do foco e da árvore de acessibilidade); o Tab pula direto para "Limpar"
  await expect(page.getByRole("button", { name: "Remover autos-00.pdf" }).locator("xpath=ancestor::div[@inert]")).toHaveCount(1);
  await alternar.focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Limpar" })).toBeFocused();
  await page.getByRole("button", { name: "Limpar" }).click();
  await expect(page.getByText(/arquivos selecionados/)).toHaveCount(0);
});

test("o progresso do ENVIO é real e separado do da análise", async ({ page }) => {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 20, downloadThroughput: -1, uploadThroughput: 600 * 1024 });
  await page.goto("/");
  await entrada(page).setInputFiles(pdf("grande.pdf", pdfPesado(150))); // ~1 MB: leva alguns segundos a 600 KB/s

  await page.getByRole("button", { name: "Analisar PDF" }).click();
  const envio = page.getByRole("progressbar", { name: "Envio dos arquivos" });
  await expect(envio).toBeVisible();
  const valores: number[] = [];
  await expect
    .poll(async () => {
      const v = await envio.getAttribute("aria-valuenow").catch(() => null);
      if (v !== null) valores.push(Number(v));
      return valores.some((n) => n > 0 && n < 100);
    })
    .toBe(true); // passou por um percentual intermediário medido pelo navegador
  // enquanto só o envio acontece, não existe acompanhamento de análise na tela
  await expect(page.getByRole("group", { name: "Andamento da análise" })).toHaveCount(0);

  await expect(page).toHaveURL(/\/processos\/[0-9a-f]{32}$/, { timeout: 40_000 }); // enviou, analisou e abriu o processo
  await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
});

test("falha na análise: erro no histórico, no detalhe e a etapa onde parou; reanálise funciona", async ({ page, request }) => {
  const id = await enviarPelaApi(request, token, "quebrado.pdf", PDF_CORROMPIDO());
  await esperarStatus(request, token, id, "FALHOU");

  await page.goto("/");
  const linha = linhaDo(page, "quebrado.pdf");
  await expect(linha).toContainText("Falhou");
  await expect(linha).toContainText("Não foi possível abrir o arquivo como PDF");
  await linha.getByRole("link").click();

  await expect(page.getByRole("alert").filter({ hasText: "A análise deste PDF falhou" })).toBeVisible();
  await expect(page.getByText("A análise parou em “Extraindo conteúdo”.")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Extraindo conteúdo" })).toContainText("falhou aqui");

  const reanalise = page.waitForResponse((r) => r.url().endsWith("/reanalisar") && r.status() === 202);
  await page.getByRole("button", { name: "Analisar de novo" }).click();
  await reanalise;
  await expect(page.getByRole("alert").filter({ hasText: "A análise deste PDF falhou" })).toBeVisible(); // o mesmo arquivo falha de novo
});

test("excluir pelo histórico pede confirmação; pelo detalhe volta ao histórico", async ({ page, request }) => {
  const id = await enviarPelaApi(request, token, "apagar-1.pdf", PDF_PAGO());
  await esperarStatus(request, token, id, "CONCLUIDO");
  await enviarPelaApi(request, token, "apagar-2.pdf", gerarPdf([["Processo Numero: 7654321-10.2024.8.09.0051"], ["Expeça-se ofício requisitório."]]));

  await page.goto("/");
  const linha = linhaDo(page, "1234567-89.2025.4.01.3500");
  await expect(linha).toBeVisible();

  page.once("dialog", (d) => d.dismiss()); // recusar a confirmação não apaga
  await linha.getByRole("button", { name: /Apagar 1234567-89/ }).click();
  await expect(linha).toBeVisible();

  page.once("dialog", (d) => d.accept());
  await linha.getByRole("button", { name: /Apagar 1234567-89/ }).click();
  await expect(linha).toHaveCount(0);

  const outra = linhaDo(page, "7654321-10.2024.8.09.0051");
  await expect(outra).toBeVisible({ timeout: 20_000 });
  await outra.getByRole("link").click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Apagar", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("Nenhum processo analisado ainda")).toBeVisible();
});

test("processo inexistente mostra 'não encontrado' com caminho de volta", async ({ page }) => {
  await page.goto(`/processos/${"0".repeat(32)}`);
  await expect(page.getByRole("alert").filter({ hasText: "Processo não encontrado" })).toBeVisible();
  await page.getByRole("link", { name: "Voltar ao histórico" }).click();
  await expect(page).toHaveURL(/\/$/);
});

test.describe("acompanhamento ao vivo (SSE real)", () => {
  test("etapas e páginas reais chegam ao vivo e a tela termina sozinha no resultado", async ({ page, request }) => {
    const id = await enviarPelaApi(request, token, "pesado.pdf", pdfPesado(900));
    const abriuFluxo = page.waitForRequest((r) => r.url().endsWith(`/api/processos/${id}/eventos`));
    await page.goto(`/processos/${id}`);
    await abriuFluxo;

    const grupo = page.getByRole("group", { name: "Andamento da análise" });
    await expect(grupo).toBeVisible();
    await expect(page.getByText("Acompanhando ao vivo")).toBeVisible();
    await expect(grupo.locator('[aria-current="step"]')).toHaveCount(1);

    // o contador de páginas anda (valores vindos do servidor, não de um relógio da tela)
    const barra = page.getByRole("progressbar", { name: /Páginas (lidas|analisadas)/ });
    await expect(barra).toBeVisible();
    const primeiro = Number(await barra.getAttribute("aria-valuenow"));
    await expect.poll(async () => Number((await barra.getAttribute("aria-valuenow").catch(() => "0")) ?? 0)).toBeGreaterThan(primeiro);

    // etapas anteriores à ativa aparecem como concluídas (o pipeline é sequencial)
    const ativa = grupo.locator('[aria-current="step"]');
    const rotulo = (await ativa.innerText()).split("\n")[0];
    if (rotulo.startsWith("Analisando as fases")) {
      await expect(grupo.getByRole("listitem").filter({ hasText: "Extraindo conteúdo" })).toContainText("concluída");
    }

    await expect(page.getByText("A dívida já foi paga?")).toBeVisible({ timeout: 60_000 }); // sem recarregar
    await expect(grupo).toHaveCount(0);
  });

  test("ao recarregar no meio da análise o estado real continua na tela", async ({ page, request }) => {
    const id = await enviarPelaApi(request, token, "pesado.pdf", pdfPesado(900));
    await page.goto(`/processos/${id}`);
    await expect(page.getByRole("progressbar", { name: /Páginas/ })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("group", { name: "Andamento da análise" })).toBeVisible();
    await expect(page.getByRole("progressbar", { name: /Páginas/ })).toBeVisible(); // continua no meio, não volta ao início
    const parcial = Number(await page.getByRole("progressbar", { name: /Páginas/ }).getAttribute("aria-valuenow"));
    expect(parcial).toBeGreaterThan(0);
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible({ timeout: 60_000 });
  });

  test("sem SSE (bloqueado), cai para o polling de 2 s e termina igual", async ({ page, request }) => {
    const id = await enviarPelaApi(request, token, "pesado.pdf", pdfPesado(900));
    await page.route(/\/api\/processos\/[0-9a-f]{32}\/eventos$/, (rota) => rota.abort("failed"));
    const consultas: number[] = [];
    page.on("request", (r) => {
      if (r.method() === "GET" && r.url().endsWith(`/api/processos/${id}`)) consultas.push(Date.now());
    });
    await page.goto(`/processos/${id}`);
    await expect(page.getByText(/consultando a API a cada 2 segundos/)).toBeVisible();
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible({ timeout: 60_000 });
    expect(consultas.length).toBeGreaterThanOrEqual(3);
    const intervalos = consultas.slice(1, 4).map((t, i) => t - consultas[i]);
    expect(Math.min(...intervalos)).toBeGreaterThan(1500); // ~2 s entre consultas, sem martelar a API
  });

  test("o servidor encerra a conexão de tempos em tempos e a tela reconecta sem cair para o polling", async ({ page, request }) => {
    // a API de teste fecha o fluxo a cada 4 s (RIBEIRO_SSE_DURACAO_MAXIMA=4); a análise dura bem mais que isso
    const id = await enviarPelaApi(request, token, "pesado.pdf", pdfPesado(1200));
    let aberturas = 0;
    page.on("request", (r) => {
      if (r.url().endsWith(`/api/processos/${id}/eventos`)) aberturas += 1;
    });
    await page.goto(`/processos/${id}`);
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible({ timeout: 90_000 });
    expect(aberturas).toBeGreaterThanOrEqual(2);
    await expect(page.getByText(/consultando a API/)).toHaveCount(0);
  });

  test("a reanálise reabre o acompanhamento e volta ao resultado", async ({ page, request }) => {
    const id = await enviarPelaApi(request, token, "autos.pdf", PDF_PAGO());
    await esperarStatus(request, token, id, "CONCLUIDO");
    await page.goto(`/processos/${id}`);
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible();
    await page.getByRole("button", { name: "Analisar de novo" }).click();
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible({ timeout: 20_000 }); // terminou de novo, sem recarregar
    await expect(page.getByRole("button", { name: "Analisar de novo" })).toBeEnabled();
  });

  test("o histórico mostra a etapa de cada análise e atualiza só as linhas, sem recarregar a página", async ({ page, request }) => {
    const id = await enviarPelaApi(request, token, "pesado.pdf", pdfPesado(900));
    await page.goto("/");
    await page.evaluate(() => ((window as unknown as { marca: number }).marca = 42)); // sumiria se a página recarregasse
    const linha = linhaDo(page, "pesado.pdf");
    await expect(linha).toContainText(/Extraindo conteúdo|Analisando as fases|Na fila/);
    await expect(page.getByText(/1 análise em andamento/)).toBeVisible();
    await esperarStatus(request, token, id, "CONCLUIDO", 60_000);
    await expect(linha).toContainText(/Sem informação|Ainda não paga|Paga/, { timeout: 15_000 });
    await expect(page.getByText(/análise em andamento/)).toHaveCount(0);
    expect(await page.evaluate(() => (window as unknown as { marca: number }).marca)).toBe(42);
    void API_URL;
  });
});

test.describe("a página do processo abre sozinha quando a análise iniciada termina", () => {
  const abriuProcesso = /\/processos\/[0-9a-f]{32}$/;

  test("fica no histórico enquanto analisa e abre o processo, com o resultado, ao terminar", async ({ page }) => {
    await page.goto("/");
    await entrada(page).setInputFiles(pdf("pesado.pdf", pdfPesado(500)));
    await page.getByRole("button", { name: "Analisar PDF" }).click();

    await expect(page.getByText(/a página do processo abre sozinha/)).toBeVisible();
    await expect(linhaDo(page, "pesado.pdf")).toContainText(/Na fila|Extraindo conteúdo|Analisando as fases/); // ainda analisando
    expect(new URL(page.url()).pathname, "enquanto analisa, não sai da tela inicial").toBe("/");

    await page.waitForURL(abriuProcesso, { timeout: 60_000 });
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible(); // o resultado já está lá
    await expect(page.getByRole("heading", { name: "Andamento do crédito" })).toBeVisible();
    await page.getByRole("link", { name: "Voltar ao histórico" }).click();
    await expect(linhaDo(page, "pesado.pdf")).toContainText(/Sem informação|Ainda não paga|Paga/); // e o histórico guardou o processo
  });

  test("se a análise falha, abre o processo mostrando o erro e a etapa onde parou", async ({ page }) => {
    await page.goto("/");
    await entrada(page).setInputFiles(pdf("quebrado.pdf", PDF_CORROMPIDO()));
    await page.getByRole("button", { name: "Analisar PDF" }).click();
    await page.waitForURL(abriuProcesso, { timeout: 30_000 });
    await expect(page.getByRole("alert").filter({ hasText: "A análise deste PDF falhou" })).toBeVisible();
    await expect(page.getByText("A análise parou em “Extraindo conteúdo”.")).toBeVisible();
  });

  test("com vários PDFs no mesmo envio não há uma única página para abrir: fica no histórico", async ({ page }) => {
    await page.goto("/");
    await entrada(page).setInputFiles([pdf("a.pdf", PDF_PAGO()), pdf("b.pdf", gerarPdf([["Processo Numero: 7654321-10.2024.8.09.0051"], ["Expeça-se ofício requisitório."]]))]);
    await page.getByRole("button", { name: "Analisar 2 PDFs" }).click();
    await expect(page.getByText("2 PDFs recebidos pelo servidor")).toBeVisible();
    await expect(page.getByText("acompanhe cada uma no histórico abaixo")).toBeVisible();
    await expect(linhaDo(page, "1234567-89.2025.4.01.3500")).toContainText("Paga", { timeout: 20_000 });
    await expect(linhaDo(page, "7654321-10.2024.8.09.0051")).toContainText("Ainda não paga", { timeout: 20_000 });
    await page.waitForTimeout(3000); // as duas terminaram: se fosse redirecionar, já teria
    expect(new URL(page.url()).pathname).toBe("/");
  });

  test("quem sai da tela inicial antes de terminar não é levado a lugar nenhum, nem ao voltar", async ({ page, request }) => {
    const outro = await enviarPelaApi(request, token, "outro.pdf", PDF_PAGO());
    await esperarStatus(request, token, outro, "CONCLUIDO");

    await page.goto("/");
    await entrada(page).setInputFiles(pdf("pesado.pdf", pdfPesado(500)));
    await page.getByRole("button", { name: "Analisar PDF" }).click();
    await expect(linhaDo(page, "pesado.pdf")).toContainText(/Na fila|Extraindo conteúdo|Analisando as fases/);

    // navegação de dentro do app (sem recarregar): vai olhar outro processo enquanto o enviado analisa
    await linhaDo(page, "1234567-89.2025.4.01.3500").getByRole("link").click();
    await expect(page).toHaveURL(new RegExp(`/processos/${outro}$`));

    const { processos } = await (await request.get(`${API_URL}/api/processos`, { headers: { Authorization: `Bearer ${token}` } })).json();
    const enviado = processos.find((p: { arquivo: string }) => p.arquivo === "pesado.pdf");
    await esperarStatus(request, token, enviado.id, "CONCLUIDO", 60_000);
    await page.waitForTimeout(3500);
    await expect(page).toHaveURL(new RegExp(`/processos/${outro}$`)); // a análise terminou e a pessoa continua onde estava

    await page.getByRole("link", { name: "Voltar ao histórico" }).click();
    await expect(linhaDo(page, "pesado.pdf")).toContainText(/Sem informação|Ainda não paga|Paga/);
    await page.waitForTimeout(3000);
    expect(new URL(page.url()).pathname, "voltar ao histórico não dispara um redirecionamento antigo").toBe("/");
  });
});
