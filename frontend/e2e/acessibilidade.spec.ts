import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { detalheFalso, entrar, processoEmAndamentoFalso, resumoFalso, simularApi, tokenDaApi } from "./apoio";

const ID = "a".repeat(32); // o mesmo id dos dados fabricados (resumoFalso): o hook ignora um processo de outro id
const progresso = (etapa: string, atual: number | null = null, total: number | null = null, falhou = false) => ({ etapa, atual, total, falhou });

let token: string;
test.beforeAll(async ({ request }) => {
  token = await tokenDaApi(request);
});

/** axe-core com as regras WCAG 2.0/2.1/2.2 nível A e AA + boas práticas. Falha listando cada violação com o elemento. */
async function auditar(page: Page, onde: string) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const resumo = violations.map((v) => `[${v.impact}] ${v.id}: ${v.help}\n${v.nodes.slice(0, 4).map((n) => `    ${n.target.join(" ")}  ${n.failureSummary?.split("\n")[1] ?? ""}`).join("\n")}`);
  expect(resumo, `violações de acessibilidade em ${onde}`).toEqual([]);
}

const LISTA = [
  resumoFalso({ id: "1".padStart(32, "0"), avisos: ["Número do processo (CNJ) não encontrado."] }),
  resumoFalso({ id: "2".padStart(32, "0"), numero_processo: "7654321-10.2024.4.01.3500", fase: "QUITADO", divida_paga: "SIM" }),
  { ...processoEmAndamentoFalso("ANALISANDO", progresso("ANALISANDO_FASES", 120, 300)), id: "3".padStart(32, "0"), arquivo: "autos.pdf" },
  { ...processoEmAndamentoFalso("PENDENTE"), id: "4".padStart(32, "0"), arquivo: "fila.pdf" },
  { ...processoEmAndamentoFalso("FALHOU", progresso("LENDO_PDF", null, null, true)), id: "5".padStart(32, "0"), arquivo: "quebrado.pdf" },
  resumoFalso({ id: "6".padStart(32, "0"), numero_processo: "1111111-22.2023.8.26.0053", fase: "PAGAMENTO_DISPONIBILIZADO", divida_paga: "PROVAVEL" }),
  resumoFalso({ id: "7".padStart(32, "0"), numero_processo: "2222222-33.2023.8.26.0053", fase: "SEM_INFORMACAO", divida_paga: "SEM_INFORMACAO" }),
];

for (const tela of [{ nome: "desktop", largura: 1440, altura: 900 }, { nome: "celular", largura: 390, altura: 844 }]) {
  test.describe(`axe-core (${tela.nome})`, () => {
    test.use({ viewport: { width: tela.largura, height: tela.altura } });
    test.beforeEach(async ({ page }) => {
      await entrar(page, token);
    });

    test("login", async ({ page }) => {
      await page.addInitScript(() => window.localStorage.removeItem("ribeiro.token"));
      await page.goto("/login");
      await expect(page.getByRole("heading", { name: "Entrar" })).toBeVisible();
      await auditar(page, "login");
    });

    test("histórico vazio", async ({ page }) => {
      await simularApi(page, { lista: [] });
      await page.goto("/");
      await expect(page.getByText("Nenhum processo analisado ainda")).toBeVisible();
      await auditar(page, "histórico vazio");
    });

    test("histórico com todos os estados", async ({ page }) => {
      await simularApi(page, { lista: LISTA });
      await page.goto("/");
      await expect(page.locator("main ul > li")).toHaveCount(LISTA.length);
      await auditar(page, "histórico");
    });

    test("histórico sem resultado para o filtro", async ({ page }) => {
      await simularApi(page, { lista: LISTA });
      await page.goto("/");
      await page.getByRole("searchbox").fill("zzzz-nao-existe");
      await expect(page.getByText("Nenhum processo corresponde ao filtro")).toBeVisible();
      await auditar(page, "histórico filtrado sem resultados");
    });

    test("envio com arquivos selecionados e avisos", async ({ page }) => {
      await simularApi(page, { lista: LISTA });
      await page.goto("/");
      const arquivos = [
        ...Array.from({ length: 3 }, (_, i) => ({ name: `autos-${i}.pdf`, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\n") })),
        { name: "notas.txt", mimeType: "text/plain", buffer: Buffer.from("x") },
      ];
      await page.locator('input[type="file"]').setInputFiles(arquivos);
      await expect(page.getByText("3 arquivos selecionados")).toBeVisible();
      await auditar(page, "envio com arquivos selecionados");
    });

    test("detalhe concluído (com seções recolhidas e abertas)", async ({ page }) => {
      await simularApi(page, { detalhe: detalheFalso({ id: ID, paginas_sem_texto: 80, total_paginas: 120, avisos: ["Aviso de exemplo."] }, 40) });
      await page.goto(`/processos/${ID}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await auditar(page, "detalhe (seções recolhidas)");
      await page.getByRole("button", { name: /^Mais informações/ }).click();
      await page.getByRole("button", { name: /^Todas as evidências/ }).click();
      await page.waitForTimeout(450);
      await auditar(page, "detalhe (informações complementares e evidências abertas)");
    });

    test("detalhe em andamento, na fila e com falha", async ({ page }) => {
      for (const [descricao, resposta] of [
        ["em andamento com contagem", processoEmAndamentoFalso("ANALISANDO", progresso("LENDO_PDF", 10, 100))],
        ["em andamento sem contagem", processoEmAndamentoFalso("ANALISANDO", progresso("VALIDANDO"))],
        ["na fila", processoEmAndamentoFalso("PENDENTE")],
        ["falha", processoEmAndamentoFalso("FALHOU", progresso("IDENTIFICANDO", null, null, true))],
      ] as const) {
        await page.unroute(/\/api\/processos\/[0-9a-f]{32}$/).catch(() => {});
        await simularApi(page, { detalhe: resposta });
        await page.goto(`/processos/${ID}`);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await page.waitForTimeout(450); // fora da animação de entrada: o contraste é medido no estado final
        await auditar(page, `detalhe ${descricao}`);
      }
    });
  });
}

test.describe("teclado, leitores de tela e estrutura", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, token);
  });

  test("estrutura: um banner, um main, um h1 e títulos em ordem", async ({ page }) => {
    await simularApi(page, { lista: LISTA });
    await page.goto("/");
    await expect(page.getByRole("banner")).toHaveCount(1);
    await expect(page.getByRole("main")).toHaveCount(1);
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
    const niveis = await page.locator("main h1, main h2, main h3").evaluateAll((els) => els.map((el) => Number(el.tagName[1])));
    niveis.forEach((nivel, i) => i > 0 && expect(nivel - niveis[i - 1], "não pula nível de título").toBeLessThanOrEqual(1));
  });

  test("histórico: cada controle tem nome acessível único e o estado dos filtros é anunciado", async ({ page }) => {
    await simularApi(page, { lista: LISTA });
    await page.goto("/");
    const apagar = page.getByRole("button", { name: /^Apagar / });
    await expect(apagar).toHaveCount(LISTA.length);
    const nomes = await apagar.evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
    expect(new Set(nomes).size).toBe(nomes.length); // "Apagar <número>" distinto por linha
    const todos = page.getByRole("button", { name: /^Todos \(/ });
    await expect(todos).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: /^Paga \(/ }).press("Space");
    await expect(page.getByRole("button", { name: /^Paga \(/ })).toHaveAttribute("aria-pressed", "true");
    await expect(todos).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByRole("status").filter({ hasText: /Mostrando 1 de/ })).toBeVisible(); // o resultado do filtro é anunciado
  });

  test("histórico: a linha inteira é um link (abre o processo) e o teclado alcança a exclusão", async ({ page }) => {
    await simularApi(page, { lista: LISTA });
    await page.goto("/");
    const primeira = page.locator("main ul > li").first();
    const link = primeira.getByRole("link");
    await link.focus();
    await expect(link).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(primeira.getByRole("button", { name: /^Apagar/ })).toBeFocused();
    expect(await link.getAttribute("href")).toBe(`/processos/${"1".padStart(32, "0")}`);
  });

  test("seções recolhíveis: botão com aria-expanded, Enter/Espaço alternam e o recolhido sai do foco", async ({ page }) => {
    await simularApi(page, { detalhe: detalheFalso({ id: ID }, 5) });
    await page.goto(`/processos/${ID}`);
    const escada = page.getByRole("button", { name: /^Mais informações/ });
    await expect(escada).toHaveAttribute("aria-expanded", "false");
    const regiao = page.locator(`#${await escada.getAttribute("aria-controls")}`.replace(/:/g, "\\:"));
    await expect(regiao).toHaveAttribute("inert", ""); // recolhido: fora do foco e da árvore de acessibilidade
    await escada.focus();
    await page.keyboard.press("Enter");
    await expect(escada).toHaveAttribute("aria-expanded", "true");
    await expect(regiao).not.toHaveAttribute("inert", "");
    await page.keyboard.press("Space");
    await expect(escada).toHaveAttribute("aria-expanded", "false");
    await expect(regiao).toHaveAttribute("inert", "");
    // o botão aponta para a região que controla
    await expect(regiao).toHaveCount(1);
  });

  test("andamento: grupo e lista nomeados, etapa atual com aria-current, barras com nome, e só a mensagem é 'viva'", async ({ page }) => {
    await simularApi(page, { detalhe: processoEmAndamentoFalso("ANALISANDO", progresso("ANALISANDO_FASES", 120, 300)) });
    await page.goto(`/processos/${ID}`);
    const grupo = page.getByRole("group", { name: "Andamento da análise" });
    await expect(grupo.getByRole("listitem")).toHaveCount(6);
    await expect(grupo.locator('[aria-current="step"]')).toHaveCount(1);
    // cada etapa diz seu estado por texto (não só por cor/ícone)
    const textos = await grupo.getByRole("listitem").evaluateAll((els) => els.map((el) => /\((concluída|em andamento|aguardando|falhou aqui)\)/.test(el.textContent ?? "") || /(concluída|em andamento|aguardando|falhou aqui)/.test(el.textContent ?? "")));
    expect(textos.every(Boolean)).toBe(true);
    await expect(page.getByRole("progressbar", { name: "Páginas analisadas" })).toHaveAttribute("aria-valuetext", "120 de 300 páginas analisadas");
    // regiões vivas: exatamente a da mensagem da etapa (a contagem de páginas não é anunciada a cada atualização)
    const vivas = await page.locator('[role="status"], [aria-live]').evaluateAll((els) => els.map((el) => el.textContent?.slice(0, 40)).filter((t) => t && t.includes("Analisando as fases")));
    expect(vivas.length).toBe(1);
    expect(await page.locator('[role="status"]:has([role="progressbar"])').count()).toBe(0);
  });

  test("zoom de 200% / tela de 320 px: nada é perdido (reflow, WCAG 1.4.10)", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await simularApi(page, { detalhe: detalheFalso({ id: ID, avisos: ["Aviso longo ".repeat(20)] }, 12) });
    await page.goto(`/processos/${ID}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const medidas = await page.evaluate(() => ({ pagina: document.documentElement.scrollWidth, janela: window.innerWidth }));
    expect(medidas.pagina).toBeLessThanOrEqual(medidas.janela);
  });
});
