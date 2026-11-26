import { defineConfig, devices } from "@playwright/test";

/**
 * Testes de ponta a ponta (integração, responsividade, acessibilidade e acompanhamento da análise).
 *
 * Rodam contra uma stack REAL e DESCARTÁVEL (banco e pasta de dados próprios): eles criam e APAGAM todos os processos da conta
 * de teste. Por segurança só rodam com E2E_EMAIL começando por "e2e" (a conta é a RIBEIRO_ADMIN_EMAIL da API de teste).
 *   1. API:       RIBEIRO_BANCO_URL=sqlite:///e2e.db RIBEIRO_PASTA_DADOS=./e2e-dados RIBEIRO_JWT_SEGREDO=... \
 *                 RIBEIRO_ADMIN_EMAIL=e2e@teste.com RIBEIRO_ADMIN_SENHA=... RIBEIRO_SSE_DURACAO_MAXIMA=4 \
 *                 RIBEIRO_REGISTRO_MAX_POR_IP=1000 \
 *                 RIBEIRO_CORS_ORIGINS=http://127.0.0.1:3101 uvicorn backend.main:app --port 8101
 *      (RIBEIRO_SSE_DURACAO_MAXIMA curto faz o teste de reconexão do SSE rodar com um PDF de segundos;
 *       RIBEIRO_REGISTRO_MAX_POR_IP alto porque registro.spec.ts cria contas, e o padrão aceita só 5 por hora)
 *   2. Frontend:  NEXT_PUBLIC_API_URL=http://127.0.0.1:8101 npm run build && npx next start -p 3101
 *   3. Testes:    E2E_EMAIL=e2e@teste.com E2E_SENHA=... npm run test:e2e   (a mesma senha da RIBEIRO_ADMIN_SENHA)
 * Variáveis: E2E_BASE_URL (frontend, padrão http://127.0.0.1:3101), E2E_API_URL (padrão http://127.0.0.1:8101).
 */
export default defineConfig({
  testDir: "./e2e",
  workers: 1, // a stack é compartilhada: os testes apagam e criam processos da mesma conta
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3101",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  // channel "chromium": o Chromium completo (e não o headless shell), que exibe PDF em vez de baixá-lo e se comporta como o navegador real.
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chromium" } }],
});
