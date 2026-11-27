import { expect, test, type Page } from "@playwright/test";
import { EMAIL } from "./apoio";

// O Registre-se cria contas DE VERDADE (ativas) na API de teste. Cada teste usa um e-mail novo; a API de teste
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

test("cadastro completo: a conta nasce ativa, entra direto e depois entra de novo pelo login", async ({ page }) => {
  const email = emailNovo();
  await page.addInitScript(() => window.localStorage.removeItem("ribeiro.token"));
  await page.goto("/registrar");
  await preencher(page, { nome: "Ana Maria Souza", email, senha: SENHA_NOVA, confirmacao: SENHA_NOVA, oab: "123.456/sp" });
  await page.getByLabel("OAB").blur();
  await expect(page.getByLabel("OAB")).toHaveValue("SP123456"); // já mostra como será gravada

  const resposta = page.waitForResponse("**/api/auth/registrar");
  await page.getByRole("button", { name: "Criar conta" }).click();
  const enviada = await resposta;
  expect(enviada.status()).toBe(201);
  expect(enviada.request().postDataJSON()).toEqual({ nome: "Ana Maria Souza", email, senha: SENHA_NOVA, oab: "SP123456" });
  expect((await enviada.json()).usuario).toMatchObject({ email, ativo: true, admin: false, oab: "SP123456" });

  // entrou sem passar pelo login, e só vê os próprios processos (nenhum)
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("Nenhum processo analisado ainda")).toBeVisible();
  await expect(page.getByText("Ana Maria Souza")).toBeVisible();

  // sai e entra de novo com a senha escolhida no cadastro
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA_NOVA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("Nenhum processo analisado ainda")).toBeVisible();
});

test("e-mail que já tem conta: o formulário avisa e continua na tela de cadastro", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.removeItem("ribeiro.token"));
  await page.goto("/registrar");
  await preencher(page, { nome: "Outra Pessoa", email: EMAIL, senha: SENHA_NOVA, confirmacao: SENHA_NOVA, oab: "GO12345" });
  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect(page.getByText("Já existe uma conta com esse e-mail. Entre com a sua senha.")).toBeVisible();
  await expect(page).toHaveURL(/\/registrar$/);
});
