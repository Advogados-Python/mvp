import { expect, test, type Page } from "@playwright/test";
import { detalheFalso, entrar, processoEmAndamentoFalso, resumoFalso, simularApi, tokenDaApi } from "./apoio";

const TELAS = [
  { nome: "mobile-320", largura: 320, altura: 700 },
  { nome: "mobile-390", largura: 390, altura: 844 },
  { nome: "tablet-820", largura: 820, altura: 1180 },
  { nome: "desktop-1440", largura: 1440, altura: 900 },
] as const;

const idN = (n: number) => n.toString(16).padStart(32, "0");
const progresso = (etapa: string, atual: number | null = null, total: number | null = null) => ({ etapa, atual, total, falhou: false });

// Histórico com todos os estados possíveis e textos longos (o que mais quebra layout).
const LISTA = [
  resumoFalso({
    id: idN(1),
    numero_processo: "0001234-56.2024.8.09.0051",
    partes: [
      { nome: "MARIA APARECIDA DA SILVA SANTOS OLIVEIRA DE ALBUQUERQUE", papel: "EXEQUENTE" },
      { nome: "ESTADO DE GOIÁS", papel: "EXECUTADO" },
    ],
    classe: "Cumprimento de Sentença contra a Fazenda Pública com um nome de classe bem comprido",
    avisos: ["Menções condicionais/futuras a pagamento foram ignoradas (pág. 4, 9).", "Número do processo (CNJ) não encontrado."],
  }),
  resumoFalso({ id: idN(2), numero_processo: "7654321-10.2024.4.01.3500", tribunal: "TRF1", fase: "QUITADO", divida_paga: "SIM", fase_descricao: "Paga." }),
  { ...processoEmAndamentoFalso("ANALISANDO", progresso("ANALISANDO_FASES", 120, 300)), id: idN(3), arquivo: "autos-completos-vol-1-de-3-com-nome-muito-comprido-para-testar-truncamento.pdf" },
  { ...processoEmAndamentoFalso("PENDENTE"), id: idN(4), arquivo: "na-fila.pdf" },
  { ...processoEmAndamentoFalso("FALHOU", progresso("LENDO_PDF")), id: idN(5), arquivo: "quebrado.pdf" },
  resumoFalso({ id: idN(6), numero_processo: null, tribunal: null, classe: null, partes: [], fase: "SEM_INFORMACAO", divida_paga: "SEM_INFORMACAO", arquivo: "sem-numero.pdf", avisos: ["Número do processo (CNJ) não encontrado."] }),
  resumoFalso({ id: idN(7), numero_processo: "1111111-22.2023.8.26.0053", tribunal: "TJSP", fase: "PAGAMENTO_DISPONIBILIZADO", divida_paga: "PROVAVEL" }),
];

let token: string;
test.beforeAll(async ({ request }) => {
  token = await tokenDaApi(request);
});
test.beforeEach(async ({ page }) => {
  await entrar(page, token);
});

async function semRolagemHorizontal(page: Page) {
  const medidas = await page.evaluate(() => ({ pagina: document.documentElement.scrollWidth, janela: window.innerWidth }));
  expect(medidas.pagina, `a página ficou ${medidas.pagina}px numa janela de ${medidas.janela}px`).toBeLessThanOrEqual(medidas.janela);
}

/** Nenhum número de processo cortado (sem reticências, sem estouro da própria caixa). */
async function numerosInteiros(page: Page, seletor: string) {
  const cortados = await page.locator(seletor).evaluateAll((els) =>
    els
      .filter((el) => (el as HTMLElement).offsetParent !== null)
      .filter((el) => el.scrollWidth > el.clientWidth + 1 || getComputedStyle(el).textOverflow === "ellipsis")
      .map((el) => el.textContent),
  );
  expect(cortados).toEqual([]);
}

const caixas = async (page: Page, seletor: string) => (await page.locator(seletor).evaluateAll((els) => els.map((el) => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; })));

for (const tela of TELAS) {
  test.describe(`tela ${tela.nome}`, () => {
    test.use({ viewport: { width: tela.largura, height: tela.altura }, hasTouch: tela.largura < 800 });

    test("histórico: sem rolagem horizontal, números inteiros e a linha se reorganiza", async ({ page }) => {
      await simularApi(page, { lista: LISTA });
      await page.goto("/");
      const linhas = page.locator("main ul > li");
      await expect(linhas).toHaveCount(LISTA.length);
      await expect(page.getByText("0001234-56.2024.8.09.0051")).toBeVisible();

      await semRolagemHorizontal(page);
      await numerosInteiros(page, "main li p.font-mono");
      await page.screenshot({ path: `test-results/telas/home-${tela.nome}.png`, fullPage: true });

      // as quatro áreas de uma linha (data-area): A número+partes · B fase · C situação · D data+avisos
      const area = async (nome: string) => (await caixas(page, `main ul > li:first-child [data-area="${nome}"]`))[0];
      const [A, B, C, D] = [await area("A"), await area("B"), await area("C"), await area("D")];
      const mesmaLinha = (a: { y: number }, b: { y: number }) => Math.abs(a.y - b.y) < 12;
      const seCruzam = (a: { x: number; y: number; w: number; h: number }, b: typeof a) =>
        a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1 && a.y < b.y + b.h - 1 && b.y < a.y + a.h - 1;
      expect(seCruzam(C, D), "situação e data nunca se sobrepõem").toBe(false);
      if (tela.largura >= 1024) {
        expect(mesmaLinha(A, B) && mesmaLinha(A, C) && mesmaLinha(A, D), "desktop: uma linha só").toBe(true);
        expect(A.x < B.x && B.x < C.x && C.x < D.x, "desktop: colunas na ordem número, fase, situação, data").toBe(true);
      } else if (tela.largura >= 768) {
        expect(mesmaLinha(A, C), "tablet: número e situação na mesma linha").toBe(true);
        expect(mesmaLinha(B, D) && B.y > A.y + 8, "tablet: fase e data na segunda linha").toBe(true);
        expect(D.x).toBeGreaterThan(B.x);
      } else {
        // celular: número+partes em largura total, depois a fase, e um rodapé com a situação e a data
        expect(B.y, "celular: fase abaixo do número").toBeGreaterThan(A.y + 8);
        expect(C.y, "celular: rodapé abaixo da fase").toBeGreaterThan(B.y + 8);
        expect(D.y + D.h, "celular: a data fica no rodapé, abaixo da fase").toBeGreaterThan(B.y + B.h);
        const linha = (await caixas(page, "main ul > li:first-child"))[0];
        expect(A.w, "celular: o número usa a largura útil da linha (não divide com o selo)").toBeGreaterThan(linha.w * 0.65);
      }

      // filtros: no celular rolam na horizontal; do tablet em diante quebram linha (sem rolagem)
      const filtros = page.getByRole("group", { name: "Filtrar por situação da dívida" });
      const { rolagem, ancho, overflowX } = await filtros.evaluate((el) => ({ rolagem: el.scrollWidth, ancho: el.clientWidth, overflowX: getComputedStyle(el).overflowX }));
      if (tela.largura < 768) {
        expect(overflowX).toBe("auto");
        expect(rolagem, "filtros com rolagem horizontal").toBeGreaterThan(ancho);
      } else {
        expect(rolagem).toBeLessThanOrEqual(ancho);
      }

      // alvos de toque: botão de apagar com pelo menos 44 × 44; filtros com pelo menos 28 de altura (WCAG 2.2: mínimo de 24)
      const apagar = (await caixas(page, 'main li button[aria-label^="Apagar"]'))[0];
      expect(apagar.w).toBeGreaterThanOrEqual(44);
      expect(apagar.h).toBeGreaterThanOrEqual(44);
      for (const chip of await caixas(page, '[role="group"][aria-label^="Filtrar"] button')) expect(chip.h).toBeGreaterThanOrEqual(28);
    });

    test("upload: faixa horizontal compacta que não estoura a largura", async ({ page }) => {
      await simularApi(page, { lista: LISTA });
      await page.goto("/");
      const faixa = page.getByText("Arraste os PDFs aqui").locator("xpath=ancestor::label");
      const caixa = (await faixa.boundingBox())!;
      expect(caixa.height).toBeLessThan(tela.largura < 640 ? 150 : 100);
      expect(caixa.x + caixa.width).toBeLessThanOrEqual(tela.largura);
      await semRolagemHorizontal(page);
      // com 20 arquivos de nome comprido ainda não estoura
      const nomes = Array.from({ length: 20 }, (_, i) => ({ name: `autos-do-processo-com-nome-extremamente-longo-numero-${i}.pdf`, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\n") }));
      await page.locator('input[type="file"]').setInputFiles(nomes);
      await expect(page.getByText("20 arquivos selecionados")).toBeVisible();
      await semRolagemHorizontal(page);
      await page.screenshot({ path: `test-results/telas/upload-${tela.nome}.png`, fullPage: false });
    });

    test("detalhe concluído: hierarquia, ações adaptadas à largura e seções recolhíveis", async ({ page }) => {
      const detalhe = detalheFalso(
        {
          id: idN(1),
          paginas_sem_texto: 80,
          total_paginas: 120,
          avisos: ["80/120 páginas sem texto (imagem/scan) NÃO foram lidas: pág. 1, 2, 3... Mais da metade do PDF não foi lida: resultado pouco confiável.", "Menções condicionais/futuras a pagamento ou quitação foram ignoradas (pág. 4, 9)."],
          numero_processo: "0001234-56.2024.8.09.0051",
        },
        40,
      );
      await simularApi(page, { detalhe });
      await page.goto(`/processos/${idN(1)}`);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("0001234-56.2024.8.09.0051");
      await semRolagemHorizontal(page);
      await numerosInteiros(page, "main h1");

      // ações no cabeçalho: as três visíveis, dentro da tela, e no celular dividem a largura
      const acoes = ["Abrir PDF", "Analisar de novo", "Apagar"].map((nome) => page.getByRole("button", { name: new RegExp(`^${nome}`) }));
      for (const botao of acoes) {
        const c = (await botao.last().boundingBox())!;
        expect(c.x).toBeGreaterThanOrEqual(0);
        expect(c.x + c.width).toBeLessThanOrEqual(tela.largura);
        expect(c.height).toBeGreaterThanOrEqual(36);
      }

      // ordem de leitura: informações do processo → andamento do crédito (o centro) → confiabilidade → todas as evidências
      const y = async (texto: string) => (await page.getByText(texto, { exact: false }).first().boundingBox())!.y;
      expect(await y("Informações do processo")).toBeLessThan(await y("Andamento do crédito"));
      expect(await y("Andamento do crédito")).toBeLessThan(await y("A dívida já foi paga?"));
      expect(await y("A dívida já foi paga?")).toBeLessThan(await y("Confiabilidade da análise"));
      expect(await y("Confiabilidade da análise")).toBeLessThan(await y("Todas as evidências"));
      // a evidência principal fica no próprio andamento, junto da fase que ela sustenta
      const andamento = page.locator("section").filter({ has: page.getByRole("heading", { name: "Andamento do crédito" }) });
      await expect(andamento.getByText("Evidência principal")).toBeVisible();
      await expect(andamento.getByRole("button", { name: /Conferir na pág\. 42/ })).toBeVisible();
      await expect(andamento.getByText("Fase atual do crédito")).toBeVisible();
      await expect(andamento.getByText("Ação recomendada")).toBeVisible();
      await expect(andamento.getByRole("listitem")).toHaveCount(6); // a escada reaproveitada: as 6 etapas
      await expect(andamento.getByText("Etapa 4 de 6")).toBeVisible();
      await expect(page.getByRole("button", { name: /^Dados do processo/ })).toHaveCount(0);

      // resumo compacto em colunas (autor/réu, juiz(a), valor requisitado): 4 no desktop, 2 no tablet, partes em linha cheia no celular
      const campo = async (rotulo: string) => (await page.getByText(rotulo, { exact: true }).first().boundingBox())!;
      const [exequente, executado, juiz, requisitado] = [await campo("Exequente"), await campo("Executado"), await campo("Juiz(a)"), await campo("Valor requisitado")];
      const mesmaLinha = (a: { y: number }, b: { y: number }) => Math.abs(a.y - b.y) < 6;
      if (tela.largura >= 1024) {
        expect([exequente, executado, juiz, requisitado].every((c) => mesmaLinha(c, exequente)), "desktop: quatro campos na mesma linha").toBe(true);
        expect(exequente.x < executado.x && executado.x < juiz.x && juiz.x < requisitado.x).toBe(true);
      } else if (tela.largura >= 640) {
        expect(mesmaLinha(exequente, executado) && mesmaLinha(juiz, requisitado), "tablet: dois campos por linha").toBe(true);
        expect(juiz.y).toBeGreaterThan(exequente.y + 8);
      } else {
        expect(executado.y, "celular: cada parte em linha cheia").toBeGreaterThan(exequente.y + 8);
        expect(mesmaLinha(juiz, requisitado), "celular: juiz(a) e valor lado a lado").toBe(true);
      }

      // o complemento fica numa seção expansível (recolhida por padrão)
      const maisInfo = page.getByRole("button", { name: /^Mais informações/ });
      await expect(maisInfo).toHaveAttribute("aria-expanded", "false");
      await maisInfo.click();
      await expect(maisInfo).toHaveAttribute("aria-expanded", "true");
      for (const rotulo of ["Órgão julgador", "Valor da causa", "Advogados", "OAB (mais citadas)", "Posição do processo", "Arquivo"]) {
        await expect(page.getByText(rotulo, { exact: true })).toBeVisible();
      }
      await maisInfo.click();
      await expect(maisInfo).toHaveAttribute("aria-expanded", "false");

      // espaçamento consistente entre as seções (12 px no celular, 16 px a partir do tablet) e largura de leitura de até 6xl (1152 px)
      const secoes = await caixas(page, "main > div > section");
      expect(secoes).toHaveLength(4);
      const esperado = tela.largura >= 640 ? 16 : 12;
      secoes.slice(1).forEach((secao, i) => expect(Math.abs(secao.y - (secoes[i].y + secoes[i].h) - esperado), `espaço entre as seções ${i + 1} e ${i + 2}`).toBeLessThanOrEqual(1.5));
      expect(Math.max(...secoes.map((secao) => secao.w))).toBeLessThanOrEqual(1152 + 1);

      // alertas críticos nunca recolhidos
      await expect(page.getByRole("alert").filter({ hasText: "Mais da metade do PDF não foi lida" })).toBeVisible();
      await expect(page.getByText("Leia estes avisos antes de confiar no resultado")).toBeVisible();

      // evidências: muitas (40) → começa recolhida; ao abrir mostra 10 e o resto sob demanda
      const botaoEvidencias = page.getByRole("button", { name: /^Todas as evidências/ });
      await expect(botaoEvidencias).toHaveAttribute("aria-expanded", "false");
      await botaoEvidencias.click();
      await expect(botaoEvidencias).toHaveAttribute("aria-expanded", "true");
      const itens = page.locator("section[aria-labelledby^='fase-'] li");
      // visão padrão "que decidem a fase": 28 dos 40 achados (os demais são condicionais ou de peça da parte)
      await expect(page.getByRole("button", { name: "Que decidem a fase (28)" })).toHaveAttribute("aria-pressed", "true");
      await expect(itens).toHaveCount(10);
      await page.getByRole("button", { name: /^Mostrar mais/ }).click();
      await expect(itens).toHaveCount(28);
      await expect(page.getByRole("button", { name: /^Mostrar mais/ })).toHaveCount(0);
      // "Todas (40)": volta a 10 e o "Mostrar todas" abre o restante de uma vez
      await page.getByRole("button", { name: "Todas (40)" }).click();
      await expect(itens).toHaveCount(10);
      await page.getByRole("button", { name: /^Mostrar todas/ }).click();
      await expect(itens).toHaveCount(40);
      await semRolagemHorizontal(page);
      await page.waitForTimeout(500); // a seção anima a altura (300 ms): fotografa só depois de assentar
      await page.screenshot({ path: `test-results/telas/detalhe-${tela.nome}.png`, fullPage: true });
    });

    test("detalhe em andamento: etapas na horizontal no desktop e na vertical no celular", async ({ page }) => {
      await simularApi(page, { detalhe: { ...processoEmAndamentoFalso("ANALISANDO", progresso("ANALISANDO_FASES", 120, 300)), id: idN(3) } });
      await page.goto(`/processos/${idN(3)}`);
      await expect(page.getByText("120 de 300 páginas analisadas")).toBeVisible();
      await semRolagemHorizontal(page);
      const passos = await caixas(page, 'ol li');
      expect(passos).toHaveLength(6);
      if (tela.largura >= 768) {
        expect(new Set(passos.map((p) => Math.round(p.y))).size, "etapas lado a lado").toBe(1);
      } else {
        expect(passos.every((p, i) => i === 0 || p.y > passos[i - 1].y), "etapas empilhadas").toBe(true);
      }
      await page.waitForTimeout(500); // deixa a animação de entrada (320 ms) terminar
      await page.screenshot({ path: `test-results/telas/andamento-${tela.nome}.png`, fullPage: true });
    });

    test("detalhe com falha e o estado vazio do histórico", async ({ page }) => {
      await simularApi(page, { detalhe: { ...processoEmAndamentoFalso("FALHOU", { etapa: "IDENTIFICANDO", atual: null, total: null, falhou: true }), id: idN(5) } });
      await page.goto(`/processos/${idN(5)}`);
      await expect(page.getByText("A análise parou em “Identificando o processo”.")).toBeVisible();
      await semRolagemHorizontal(page);
      await page.screenshot({ path: `test-results/telas/falha-${tela.nome}.png`, fullPage: true });

      await page.unroute(/\/api\/processos\/[0-9a-f]{32}$/);
      await simularApi(page, { lista: [] });
      await page.goto("/");
      await expect(page.getByText("Nenhum processo analisado ainda")).toBeVisible();
      await semRolagemHorizontal(page);
      await page.screenshot({ path: `test-results/telas/vazio-${tela.nome}.png`, fullPage: true });
    });
  });
}
