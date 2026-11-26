import { expect, test, type Page } from "@playwright/test";
import { API_URL, tokenDaApi } from "./apoio";

// O Registre-se cria contas DE VERDADE (inativas) na API de teste. Cada teste usa um e-mail novo; a API de teste
// precisa de RIBEIRO_REGISTRO_MAX_POR_IP alto (o padrão, 5 por hora, acaba no meio da suíte; veja playwright.config.ts).
const emailNovo = () => `e2e-registro-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@teste.com`;
const SENHA_NOVA = "senha-da-ana-123";

async function preencher(page: Page, dados: { nome?: string; email?: string; senha?: string; confirmacao?: string; oab?: string }) {
  if (dados.nome !== undefined) await page.getByLabel("Nome completo").fill(dados.nome);
  if (dados.email !== undefined) await page.getByLabel("E-mail").fill(dados.email);
  if (dados.senha !== undefined) await page.getByLabel("Senha", { exact: true }).fill(dados.senha);
  if (dados.confirmacao !== undefined) await page.getByLabel("Confirmação de senha").fill(dados.confirmacao);
  if (dados.oab !== undefined) await page.getByLabel("OAB").fill(dados.oab);
}

test("o link Registre-se fica logo abaixo do botão Entrar e leva ao cadastro", async ({ page }) => {
  await page.goto("/login");
  const botao = page.getByRole("button", { name: "Entrar" });
  const link = page.getByRole("link", { name: "Registre-se" });
  await expect(link).toBeVisible();
  const [caixaBotao, caixaLink] = [await botao.boundingBox(), await link.boundingBox()];
  expect(caixaLink!.y).toBeGreaterThanOrEqual(caixaBotao!.y + caixaBotao!.height);

  await link.click();
  await expect(page).toHaveURL(/\/registrar$/);
  await expect(page.getByRole("heading", { name: "Registre-se" })).toBeVisible();
  await page.getByRole("link", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("o formulário confere os campos antes de enviar: vazios, senhas diferentes e OAB inválida", async ({ page }) => {
  let chamadas = 0;
  await page.route("**/api/auth/registrar", (rota) => {
    chamadas += 1;
    return rota.continue();
  });
  await page.goto("/registrar");

  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect(page.getByText("Informe o seu nome completo.")).toBeVisible();
  await expect(page.getByText("Informe o número da OAB.")).toBeVisible();
  await expect(page.getByLabel("Nome completo")).toBeFocused(); // o foco vai para o primeiro campo com erro

  await preencher(page, { nome: "Ana Maria Souza", email: emailNovo(), senha: "curta", confirmacao: "outra", oab: "XX12345" });
  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect(page.getByText("A senha precisa ter pelo menos 10 caracteres.")).toBeVisible();
  await expect(page.getByText("As senhas não conferem.")).toBeVisible();
  await expect(page.getByText("A sigla de estado 'XX' não existe.")).toBeVisible();
  await expect(page.getByLabel("Senha", { exact: true })).toBeFocused();
  await expect(page.getByLabel("OAB")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("OAB")).toHaveAccessibleDescription("A sigla de estado 'XX' não existe.");

  // corrigir o campo apaga o erro dele na hora
  await page.getByLabel("OAB").fill("GO12345");
  await expect(page.getByText("A sigla de estado 'XX' não existe.")).toHaveCount(0);
  expect(chamadas).toBe(0);
});

test("cadastro completo: conta nasce inativa, o login explica a espera e, liberada pelo admin, entra", async ({ page, request }) => {
  const email = emailNovo();
  await page.goto("/registrar");
  await preencher(page, { nome: "Ana Maria Souza", email, senha: SENHA_NOVA, confirmacao: SENHA_NOVA, oab: "123.456/sp" });
  await page.getByLabel("OAB").blur();
  await expect(page.getByLabel("OAB")).toHaveValue("SP123456"); // já mostra como será gravada

  const resposta = page.waitForResponse("**/api/auth/registrar");
  await page.getByRole("button", { name: "Criar conta" }).click();
  const enviada = await resposta;
  expect(enviada.status()).toBe(202);
  expect(enviada.request().postDataJSON()).toEqual({ nome: "Ana Maria Souza", email, senha: SENHA_NOVA, oab: "SP123456" });
  await expect(page.getByText("Cadastro recebido", { exact: true })).toBeVisible();
  await expect(page.getByText("Você poderá entrar assim que a sua conta for liberada.")).toBeVisible();

  // antes da liberação: o login recusa com a explicação (e não com "senha inválida")
  await page.getByRole("link", { name: "Voltar para Entrar" }).click();
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA_NOVA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("Sua conta ainda não está liberada")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);

  // o administrador libera (PATCH ativo=true) e a mesma pessoa entra
  const admin = { Authorization: `Bearer ${await tokenDaApi(request)}` };
  const usuarios = await (await request.get(`${API_URL}/api/usuarios`, { headers: admin })).json();
  const nova = usuarios.find((u: { email: string }) => u.email === email);
  expect(nova).toMatchObject({ ativo: false, admin: false, oab: "SP123456", nome: "Ana Maria Souza" });
  expect((await request.patch(`${API_URL}/api/usuarios/${nova.id}`, { headers: admin, data: { ativo: true } })).ok()).toBe(true);

  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("Nenhum processo analisado ainda")).toBeVisible(); // conta nova: só os próprios processos
});
