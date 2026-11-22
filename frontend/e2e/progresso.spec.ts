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

const FASES = ["Documento recebido", "Extraindo conteúdo", "Identificando o processo", "Buscando os termos", "Validando evidências", "Finalizando resultado"];
const lista = (page: Page) => page.getByRole("list", { name: "Fases do processo" });
const fase = (page: Page, rotulo: string) => lista(page).getByRole("listitem").filter({ hasText: rotulo });
const progresso = (etapa: string, atual: number | null = null, total: number | null = null, falhou = false) => ({ etapa, atual, total, falhou });

test.describe("o processo, fase a fase: cada estado vem do que a API informou", () => {
  test("na fila: só o recebimento está ativo e nenhuma fase de leitura é afirmada", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("PENDENTE") });
    await page.goto(`/processos/${ID}`);
    await expect(lista(page).getByRole("listitem")).toHaveCount(6);
    await expect(fase(page, "Documento recebido")).toHaveAttribute("aria-current", "step");
    for (const outra of FASES.slice(1)) await expect(fase(page, outra)).toContainText("aguardando");
    await expect(page.getByText("O PDF foi recebido e está na fila")).toBeVisible();
    await expect(page.getByRole("progressbar")).toHaveCount(0); // sem barra: não há o que medir
  });

  for (const [indice, etapa] of [[1, "LENDO_PDF"], [2, "IDENTIFICANDO"], [3, "BUSCANDO_TERMOS"], [4, "VALIDANDO"], [5, "FINALIZANDO"]] as const) {
    test(`fase ${indice + 1} (${etapa}): ativa só ${FASES[indice]}; as anteriores concluídas, as seguintes aguardando`, async ({ page }) => {
      await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso(etapa)) });
      await page.goto(`/processos/${ID}`);
      await expect(lista(page).locator('[aria-current="step"]')).toHaveCount(1);
      await expect(fase(page, FASES[indice])).toHaveAttribute("aria-current", "step");
      await expect(fase(page, FASES[indice])).toContainText("em andamento");
      for (const anterior of FASES.slice(0, indice)) await expect(fase(page, anterior)).toContainText("concluída");
      for (const seguinte of FASES.slice(indice + 1)) await expect(fase(page, seguinte)).toContainText("aguardando");
    });
  }

  test("a contagem de páginas só aparece com os dois números informados pelo servidor", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso("BUSCANDO_TERMOS", 120, 300)) });
    await page.goto(`/processos/${ID}`);
    const barra = page.getByRole("progressbar", { name: "Páginas analisadas" });
    await expect(barra).toHaveAttribute("aria-valuenow", "120");
    await expect(barra).toHaveAttribute("aria-valuemax", "300");
    await expect(barra).toHaveAttribute("aria-valuetext", "120 de 300 páginas analisadas");
    await expect(page.getByText("120 de 300 páginas analisadas")).toBeVisible();
    await expect(fase(page, "Buscando os termos")).toContainText("120/300 pág.");
    expect(await page.locator("body").innerText()).not.toMatch(/\d+\s?%/); // não existe percentual geral inventado
  });

  test("fase sem contagem (ex.: validando) mostra barra indeterminada, sem valor", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso("VALIDANDO")) });
    await page.goto(`/processos/${ID}`);
    const barra = page.getByRole("progressbar", { name: "Validando evidências: em andamento" });
    await expect(barra).toBeVisible();
    await expect(barra).not.toHaveAttribute("aria-valuenow", /.*/);
  });

  for (const [descricao, valor] of [["sem fase", null], ["com fase desconhecida (backend mais novo que o front)", progresso("FASE_DO_FUTURO", 1, 2)]] as const) {
    test(`análise ${descricao}: indeterminada, sem marcar nenhuma fase como atual`, async ({ page }) => {
      await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", valor) });
      await page.goto(`/processos/${ID}`);
      await expect(page.getByText("O servidor ainda não informou em que fase está.")).toBeVisible();
      await expect(lista(page).locator('[aria-current="step"]')).toHaveCount(0);
      await expect(fase(page, "Documento recebido")).toContainText("concluída"); // só o recebimento está confirmado
      await expect(fase(page, "Extraindo conteúdo")).toContainText("aguardando");
      await expect(page.getByRole("progressbar", { name: "Análise em andamento" })).toBeVisible();
    });
  }

  test("falha: marca a fase onde parou, mantém as anteriores concluídas, mostra o motivo e oferece nova tentativa", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("FALHOU", progresso("IDENTIFICANDO", null, null, true)) });
    await page.goto(`/processos/${ID}`);
    await expect(page.getByRole("alert").filter({ hasText: "A análise deste PDF falhou" })).toContainText("corrompido ou formato inválido");
    await expect(fase(page, "Identificando o processo")).toContainText("falhou aqui");
    await expect(fase(page, "Identificando o processo")).toContainText("A análise parou aqui");
    await expect(fase(page, "Extraindo conteúdo")).toContainText("concluída");
    await expect(fase(page, "Buscando os termos")).toContainText("aguardando");
    await expect(page.getByRole("button", { name: "Analisar de novo" })).toBeEnabled();
    await expect(lista(page).locator('[aria-current="step"]')).toHaveCount(0); // nada em andamento
  });

  test("falha sem fase conhecida (servidor reiniciou): mostra o erro e não inventa onde parou", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("FALHOU", null) });
    await page.goto(`/processos/${ID}`);
    await expect(page.getByRole("alert").filter({ hasText: "A análise deste PDF falhou" })).toBeVisible();
    await expect(fase(page, "Documento recebido")).toContainText("concluída");
    for (const outra of FASES.slice(1)) await expect(fase(page, outra)).toContainText("aguardando");
    await expect(page.getByText("falhou aqui")).toHaveCount(0);
  });
});

test.describe("o processo concluído mostra o que cada fase produziu", () => {
  test("seis fases concluídas, cada uma com o seu resumo e os seus dados", async ({ page }) => {
    await simularApi(page, { detalhe: detalheFalso({ total_paginas: 163, paginas_sem_texto: 4, avisos: ["Aviso de exemplo."] }, 4) });
    await page.goto(`/processos/${ID}`);
    for (const nome of FASES) await expect(fase(page, nome)).toContainText("concluída");
    // nenhuma FASE DE LEITURA em andamento (o aria-current da escada do crédito, dentro da validação, é outra coisa)
    await expect(lista(page).locator(':scope > li[aria-current="step"]')).toHaveCount(0);
    await expect(fase(page, "Documento recebido")).toContainText("recebido em"); // resumo: tamanho e data
    await expect(fase(page, "Extraindo conteúdo")).toContainText("159 de 163 páginas lidas");
    await expect(fase(page, "Identificando o processo")).toContainText("0001234-56.2024.8.09.0051 · TJGO");
    await expect(fase(page, "Buscando os termos")).toContainText("4 achados");
    await expect(fase(page, "Validando evidências")).toContainText("Requisição (RPV/precatório)");
    await expect(fase(page, "Finalizando resultado")).toContainText("Gravado em");

    // a identificação e a validação começam abertas; recebimento, extração e finalização recolhidos (o resumo já diz o essencial)
    await expect(page.getByText("Órgão julgador", { exact: true })).toBeVisible();
    await expect(page.getByText("Ação recomendada")).toBeVisible();
    const extracao = page.getByRole("button", { name: /2\. Extraindo conteúdo/ });
    await expect(extracao).toHaveAttribute("aria-expanded", "false");
    await extracao.click();
    await expect(page.getByText("(4 sem texto)")).toBeVisible();
    await expect(page.getByText("o que estiver escrito nelas não entra no resultado")).toBeVisible();
  });

  test("a resposta fica em destaque no topo e os avisos nunca ficam dentro de uma fase recolhida", async ({ page }) => {
    await simularApi(page, { detalhe: detalheFalso({ total_paginas: 100, paginas_sem_texto: 80, avisos: ["Aviso A.", "Aviso B."] }, 3) });
    await page.goto(`/processos/${ID}`);
    const destaque = page.getByRole("region", { name: "Resultado da análise" });
    await expect(destaque).toContainText("A dívida já foi paga?");
    await expect(destaque).toContainText("Etapa 4 de 6");
    await expect(destaque.getByRole("button", { name: /Conferir no PDF · pág\. 42/ })).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: "Mais da metade do PDF não foi lida" })).toBeVisible();
    await expect(page.getByText("Leia estes avisos antes de confiar no resultado")).toBeVisible();
    // acima das fases, sem precisar abrir nada
    const yAviso = (await page.getByText("Leia estes avisos antes de confiar no resultado").boundingBox())!.y;
    const yFases = (await lista(page).boundingBox())!.y;
    expect(yAviso).toBeLessThan(yFases);
  });

  test("o corpo de cada fase usa os componentes de sempre: escada, evidências com link para a página do PDF", async ({ page }) => {
    await simularApi(page, { detalhe: detalheFalso({}, 4) });
    await page.goto(`/processos/${ID}`);
    await expect(fase(page, "Validando evidências").getByRole("listitem")).toHaveCount(6); // a escada do crédito, reaproveitada
    await expect(fase(page, "Validando evidências").getByRole("button", { name: /Conferir na pág\. 42/ })).toBeVisible();
    const busca = page.getByRole("button", { name: /4\. Buscando os termos/ });
    await expect(busca).toHaveAttribute("aria-expanded", "true"); // 4 evidências: aberta
    await expect(fase(page, "Buscando os termos").getByRole("button", { name: /pág\. \d+ .*abre o PDF/ }).first()).toBeVisible();
  });
});

test.describe("transições e reconexões", () => {
  test("polling: fila → lendo → buscando → resultado, cada passo vindo da API", async ({ page }) => {
    const respostas = [
      processoEmAndamentoFalso("PENDENTE"),
      processoEmAndamentoFalso("ANALISANDO", progresso("LENDO_PDF", 10, 100)),
      processoEmAndamentoFalso("ANALISANDO", progresso("BUSCANDO_TERMOS", 50, 100)),
      detalheFalso({}, 3),
    ];
    await simularApi(page, { detalhe: (n) => respostas[Math.min(n, respostas.length) - 1] });
    await page.goto(`/processos/${ID}`);

    await expect(fase(page, "Documento recebido")).toHaveAttribute("aria-current", "step");
    await expect(page.getByText("10 de 100 páginas lidas")).toBeVisible({ timeout: 8000 });
    await expect(fase(page, "Extraindo conteúdo")).toHaveAttribute("aria-current", "step");
    await expect(page.getByText("50 de 100 páginas analisadas")).toBeVisible({ timeout: 8000 });
    await expect(fase(page, "Identificando o processo")).toContainText("concluída"); // fase que o front nunca viu, mas o backend superou
    await expect(page.getByRole("region", { name: "Resultado da análise" })).toBeVisible({ timeout: 8000 });
    for (const nome of FASES) await expect(fase(page, nome)).toContainText("concluída"); // o processo continua na tela, agora completo
    await expect(page.getByRole("progressbar")).toHaveCount(0);
  });

  test("SSE: eventos de fase atualizam a tela e o 'fim' leva ao resultado", async ({ page }) => {
    const eventos = [
      ["estado", { status: "ANALISANDO", progresso: progresso("LENDO_PDF", 5, 10) }],
      ["estado", { status: "ANALISANDO", progresso: progresso("BUSCANDO_TERMOS", 3, 10) }],
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
    await expect(page.getByRole("region", { name: "Resultado da análise" })).toBeVisible();
    await expect(page.getByText(/consultando a API/)).toHaveCount(0); // ficou no SSE, não caiu para o polling
  });

  test("queda de rede durante o acompanhamento: mantém o último estado, avisa e se recupera sozinha", async ({ page }) => {
    const respostas: (object | "ABORTAR")[] = [
      processoEmAndamentoFalso("ANALISANDO", progresso("LENDO_PDF", 20, 100)),
      "ABORTAR",
      "ABORTAR",
      processoEmAndamentoFalso("ANALISANDO", progresso("BUSCANDO_TERMOS", 10, 100)),
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
        !reanalisou ? detalheFalso({}, 3) : n % 3 === 0 ? detalheFalso({}, 3) : processoEmAndamentoFalso("ANALISANDO", progresso("BUSCANDO_TERMOS", 30, 60)),
    });
    await page.route(/\/reanalisar$/, (rota) => {
      reanalisou = true;
      return rota.fulfill({ status: 202, headers: { "access-control-allow-origin": "*" }, json: processoEmAndamentoFalso("PENDENTE") });
    });
    await page.goto(`/processos/${ID}`);
    await expect(page.getByRole("region", { name: "Resultado da análise" })).toBeVisible();
    await page.getByRole("button", { name: "Analisar de novo" }).click();
    await expect(page.getByText("30 de 60 páginas analisadas")).toBeVisible();
    await expect(page.getByRole("button", { name: "Analisar de novo" })).toHaveCount(0); // enquanto roda, não oferece outra
    await expect(page.getByRole("region", { name: "Resultado da análise" })).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("movimento", () => {
  const estiloDe = (page: Page, seletor: string) =>
    page.locator(seletor).first().evaluate((el) => {
      const css = getComputedStyle(el);
      return { nome: css.animationName, iteracoes: css.animationIterationCount, exibicao: css.display };
    });

  test("com movimento normal: o anel da fase ativa gira sem parar, a barra indeterminada desliza", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso("VALIDANDO")) });
    await page.goto(`/processos/${ID}`);
    const anel = await estiloDe(page, '[aria-current="step"] span[class*="border-t-accent"]');
    expect(anel).toMatchObject({ nome: "spin", iteracoes: "infinite" });
    expect((await estiloDe(page, '[role="progressbar"]')).exibicao).not.toBe("none");
    // animação CONTÍNUA só na fase ativa (as concluídas têm apenas uma entrada de 320 ms, que não se repete)
    const continuos = await page.locator('ol[aria-label="Fases do processo"] > li').evaluateAll((itens) =>
      itens.map((item) => ({
        ativo: item.getAttribute("aria-current") === "step",
        repete: [...item.querySelectorAll("svg, span")].some((el) => getComputedStyle(el).animationIterationCount === "infinite" && getComputedStyle(el).animationName !== "none"),
      })),
    );
    expect(continuos.filter((i) => i.repete)).toEqual([{ ativo: true, repete: true }]);
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
      await expect(page.getByText("Separando as evidências que decidem a fase")).toBeVisible();
      await expect(fase(page, "Validando evidências")).toContainText("em andamento"); // o estado continua claro sem movimento
    });
  });
});
