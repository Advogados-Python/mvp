import { expect, test, type Page } from "@playwright/test";
import { detalheFalso, entrar, processoEmAndamentoFalso, simularApi, tokenDaApi } from "./apoio";

const ID = "a".repeat(32);
let token: string;

test.beforeAll(async ({ request }) => {
  token = await tokenDaApi(request);
});
test.beforeEach(async ({ page }) => {
  await entrar(page, token);
});

const grupo = (page: Page) => page.getByRole("group", { name: "Andamento da análise" });
const passo = (page: Page, rotulo: string) => grupo(page).getByRole("listitem").filter({ hasText: rotulo });
const progresso = (etapa: string, atual: number | null = null, total: number | null = null, falhou = false) => ({ etapa, atual, total, falhou });

test.describe("cada estado vem do que a API informou", () => {
  test("na fila: só o recebimento está ativo e nenhuma etapa de leitura é afirmada", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("PENDENTE") });
    await page.goto(`/processos/${ID}`);
    await expect(passo(page, "Documento recebido")).toHaveAttribute("aria-current", "step");
    for (const outro of ["Extraindo conteúdo", "Identificando o processo", "Analisando as fases", "Validando evidências", "Finalizando resultado"]) {
      await expect(passo(page, outro)).toContainText("aguardando");
    }
    await expect(page.getByText("O PDF foi recebido e está na fila")).toBeVisible();
    await expect(page.getByRole("progressbar")).toHaveCount(0); // sem barra: não há o que medir
  });

  for (const [etapa, rotulo, anteriores, posteriores] of [
    ["LENDO_PDF", "Extraindo conteúdo", ["Documento recebido"], ["Identificando o processo", "Analisando as fases", "Validando evidências", "Finalizando resultado"]],
    ["IDENTIFICANDO", "Identificando o processo", ["Documento recebido", "Extraindo conteúdo"], ["Analisando as fases", "Validando evidências", "Finalizando resultado"]],
    ["ANALISANDO_FASES", "Analisando as fases", ["Documento recebido", "Extraindo conteúdo", "Identificando o processo"], ["Validando evidências", "Finalizando resultado"]],
    ["VALIDANDO", "Validando evidências", ["Documento recebido", "Extraindo conteúdo", "Identificando o processo", "Analisando as fases"], ["Finalizando resultado"]],
    ["FINALIZANDO", "Finalizando resultado", ["Documento recebido", "Extraindo conteúdo", "Identificando o processo", "Analisando as fases", "Validando evidências"], []],
  ] as const) {
    test(`etapa ${etapa}: ativa só ${rotulo}; as anteriores concluídas, as seguintes aguardando`, async ({ page }) => {
      await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso(etapa)) });
      await page.goto(`/processos/${ID}`);
      await expect(grupo(page).locator('[aria-current="step"]')).toHaveCount(1);
      await expect(passo(page, rotulo)).toHaveAttribute("aria-current", "step");
      await expect(passo(page, rotulo)).toContainText("em andamento");
      for (const outro of anteriores) await expect(passo(page, outro)).toContainText("concluída");
      for (const outro of posteriores) await expect(passo(page, outro)).toContainText("aguardando");
    });
  }

  test("a contagem de páginas só aparece com os dois números informados pelo servidor", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso("ANALISANDO_FASES", 120, 300)) });
    await page.goto(`/processos/${ID}`);
    const barra = page.getByRole("progressbar", { name: "Páginas analisadas" });
    await expect(barra).toHaveAttribute("aria-valuenow", "120");
    await expect(barra).toHaveAttribute("aria-valuemax", "300");
    await expect(barra).toHaveAttribute("aria-valuetext", "120 de 300 páginas analisadas");
    await expect(page.getByText("120 de 300 páginas analisadas")).toBeVisible();
    expect(await page.locator("body").innerText()).not.toMatch(/\d+\s?%/); // não existe percentual geral inventado
  });

  test("etapa sem contagem (ex.: validando) mostra barra indeterminada, sem valor", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso("VALIDANDO")) });
    await page.goto(`/processos/${ID}`);
    const barra = page.getByRole("progressbar", { name: "Análise em andamento" });
    await expect(barra).toBeVisible();
    await expect(barra).not.toHaveAttribute("aria-valuenow", /.*/);
  });

  for (const [descricao, valor] of [["sem etapa", null], ["com etapa desconhecida (backend mais novo que o front)", progresso("ETAPA_DO_FUTURO", 1, 2)]] as const) {
    test(`análise ${descricao}: indeterminada, sem marcar nenhuma etapa como atual`, async ({ page }) => {
      await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", valor) });
      await page.goto(`/processos/${ID}`);
      await expect(page.getByText("O servidor ainda não informou em que etapa está.")).toBeVisible();
      await expect(grupo(page).locator('[aria-current="step"]')).toHaveCount(0);
      await expect(passo(page, "Documento recebido")).toContainText("concluída"); // só o recebimento está confirmado
      await expect(passo(page, "Extraindo conteúdo")).toContainText("aguardando");
      await expect(page.getByRole("progressbar", { name: "Análise em andamento" })).toBeVisible();
    });
  }

  test("falha: marca a etapa onde parou, mantém as anteriores concluídas e oferece nova tentativa", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("FALHOU", progresso("IDENTIFICANDO", null, null, true)) });
    await page.goto(`/processos/${ID}`);
    await expect(page.getByRole("alert").filter({ hasText: "A análise deste PDF falhou" })).toContainText("corrompido ou formato inválido");
    await expect(page.getByText("A análise parou em “Identificando o processo”.")).toBeVisible();
    await expect(passo(page, "Identificando o processo")).toContainText("falhou aqui");
    await expect(passo(page, "Extraindo conteúdo")).toContainText("concluída");
    await expect(passo(page, "Analisando as fases")).toContainText("aguardando");
    await expect(page.getByRole("button", { name: "Analisar de novo" })).toBeEnabled();
    await expect(grupo(page).locator('[aria-current="step"]')).toHaveCount(0); // nada em andamento
  });

  test("falha sem etapa conhecida (servidor reiniciou): mostra o erro e não inventa onde parou", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("FALHOU", null) });
    await page.goto(`/processos/${ID}`);
    await expect(page.getByRole("alert").filter({ hasText: "A análise deste PDF falhou" })).toBeVisible();
    await expect(grupo(page)).toHaveCount(0);
  });
});

test.describe("transições e reconexões", () => {
  test("polling: fila → lendo → analisando → resultado, cada passo vindo da API", async ({ page }) => {
    const respostas = [
      processoEmAndamentoFalso("PENDENTE"),
      processoEmAndamentoFalso("ANALISANDO", progresso("LENDO_PDF", 10, 100)),
      processoEmAndamentoFalso("ANALISANDO", progresso("ANALISANDO_FASES", 50, 100)),
      detalheFalso({}, 3),
    ];
    await simularApi(page, { detalhe: (n) => respostas[Math.min(n, respostas.length) - 1] });
    await page.goto(`/processos/${ID}`);

    await expect(passo(page, "Documento recebido")).toHaveAttribute("aria-current", "step");
    await expect(page.getByText("10 de 100 páginas lidas")).toBeVisible({ timeout: 8000 });
    await expect(passo(page, "Extraindo conteúdo")).toHaveAttribute("aria-current", "step");
    await expect(page.getByText("50 de 100 páginas analisadas")).toBeVisible({ timeout: 8000 });
    await expect(passo(page, "Identificando o processo")).toContainText("concluída"); // etapa que o front nunca viu, mas o backend superou
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible({ timeout: 8000 });
    await expect(grupo(page)).toHaveCount(0);
    await expect(page.getByRole("progressbar")).toHaveCount(0);
  });

  test("SSE: eventos de etapa atualizam a tela e o 'fim' leva ao resultado", async ({ page }) => {
    const eventos = [
      ["estado", { status: "ANALISANDO", progresso: progresso("LENDO_PDF", 5, 10) }],
      ["estado", { status: "ANALISANDO", progresso: progresso("ANALISANDO_FASES", 3, 10) }],
      ["fim", { status: "CONCLUIDO", progresso: null }],
    ] as const;
    const corpo = eventos.map(([nome, dados]) => `event: ${nome}\ndata: ${JSON.stringify(dados)}\n\n`).join("");
    // 1ª consulta: ainda em análise; depois do 'fim' o resultado completo
    await simularApi(page, {
      detalhe: (n) => (n === 1 ? processoEmAndamentoFalso("ANALISANDO", progresso("LENDO_PDF", 1, 10)) : detalheFalso({}, 3)),
      eventos: { corpo },
    });
    const pediuFluxo = page.waitForRequest((r) => r.url().endsWith("/eventos"));
    await page.goto(`/processos/${ID}`);
    await pediuFluxo;
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible();
    await expect(page.getByText(/consultando a API/)).toHaveCount(0); // ficou no SSE, não caiu para o polling
  });

  test("queda de rede durante o acompanhamento: mantém o último estado, avisa e se recupera sozinha", async ({ page }) => {
    const respostas: (object | "ABORTAR")[] = [
      processoEmAndamentoFalso("ANALISANDO", progresso("LENDO_PDF", 20, 100)),
      "ABORTAR",
      "ABORTAR",
      processoEmAndamentoFalso("ANALISANDO", progresso("ANALISANDO_FASES", 10, 100)),
    ];
    await simularApi(page, { detalhe: (n) => respostas[Math.min(n, respostas.length) - 1] });
    await page.goto(`/processos/${ID}`);
    await expect(page.getByText("20 de 100 páginas lidas")).toBeVisible();
    const aviso = page.getByRole("note").filter({ hasText: "Sem conexão com a API" });
    await expect(aviso).toBeVisible({ timeout: 8000 });
    await expect(page.getByText("20 de 100 páginas lidas")).toBeVisible(); // o último estado continua à vista
    await expect(page.getByText("10 de 100 páginas analisadas")).toBeVisible({ timeout: 10_000 });
    await expect(aviso).toHaveCount(0); // recuperou
  });

  test("reanálise a partir de um resultado: mostra o andamento e volta ao resultado", async ({ page }) => {
    let reanalisou = false;
    await simularApi(page, {
      detalhe: (n) =>
        !reanalisou ? detalheFalso({}, 3) : n % 3 === 0 ? detalheFalso({}, 3) : processoEmAndamentoFalso("ANALISANDO", progresso("ANALISANDO_FASES", 30, 60)),
    });
    await page.route(/\/reanalisar$/, (rota) => {
      reanalisou = true;
      return rota.fulfill({ status: 202, headers: { "access-control-allow-origin": "*" }, json: processoEmAndamentoFalso("PENDENTE") });
    });
    await page.goto(`/processos/${ID}`);
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible();
    await page.getByRole("button", { name: "Analisar de novo" }).click();
    await expect(page.getByText("30 de 60 páginas analisadas")).toBeVisible();
    await expect(page.getByRole("button", { name: "Analisar de novo" })).toHaveCount(0); // enquanto roda, não oferece outra
    await expect(page.getByText("A dívida já foi paga?")).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("movimento", () => {
  const estiloDe = (page: Page, seletor: string) =>
    page.locator(seletor).first().evaluate((el) => {
      const css = getComputedStyle(el);
      return { nome: css.animationName, iteracoes: css.animationIterationCount, exibicao: css.display };
    });

  test("com movimento normal: o anel da etapa ativa gira sem parar, a barra indeterminada desliza", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso("VALIDANDO")) });
    await page.goto(`/processos/${ID}`);
    const anel = await estiloDe(page, '[aria-current="step"] span[class*="border-t-accent"]');
    expect(anel).toMatchObject({ nome: "spin", iteracoes: "infinite" });
    expect((await estiloDe(page, '[role="progressbar"]')).exibicao).not.toBe("none");
    // animação CONTÍNUA só na etapa ativa (as concluídas têm apenas uma entrada de 320 ms, que não se repete)
    const contínuos = await page.locator("ol li").evaluateAll((itens) =>
      itens.map((item) => ({
        ativo: item.getAttribute("aria-current") === "step",
        repete: [...item.querySelectorAll("svg, span")].some((el) => getComputedStyle(el).animationIterationCount === "infinite" && getComputedStyle(el).animationName !== "none"),
      })),
    );
    expect(contínuos.filter((i) => i.repete)).toEqual([{ ativo: true, repete: true }]);
  });

  test.describe("prefers-reduced-motion", () => {
    test.use({ reducedMotion: "reduce" });
    test("sem animação repetitiva: o anel não gira, o ícone não pulsa e a barra deslizante some; o texto segue informando", async ({ page }) => {
      await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso("VALIDANDO")) });
      await page.goto(`/processos/${ID}`);
      const anel = await estiloDe(page, '[aria-current="step"] span[class*="border-t-accent"]');
      expect(anel.nome === "none" || anel.iteracoes === "1").toBe(true);
      const icone = await page.locator('[aria-current="step"] svg').first().evaluate((el) => getComputedStyle(el).animationName);
      expect(icone).toBe("none");
      expect((await estiloDe(page, '[role="progressbar"]')).exibicao).toBe("none");
      await expect(page.getByText("Validando evidências.")).toBeVisible();
      await expect(passo(page, "Validando evidências")).toContainText("em andamento"); // o estado continua claro sem movimento
    });
  });
});
