# Frontend — Ribeiro e Souza, Leitor de Processos

Interface web (Next.js 16, App Router, Tailwind 4) do backend em [`../backend/`](../backend/). O guia completo de como rodar está no [README da raiz](../README.md#14-interface-web-backend--frontend).

```bash
npm install
npm run dev      # http://localhost:3000  (a API precisa estar em http://localhost:8000)
npm run lint
npm run build
```

## Como está organizado

| Caminho | Papel |
|---|---|
| `src/app/login/page.tsx` | Tela de login |
| `src/app/page.tsx` | Tela inicial: envio de PDFs + lista de processos |
| `src/app/processos/[id]/page.tsx` | Detalhe: resposta "dívida paga?", avisos, escada de fases, dados e evidências |
| `src/lib/api.ts` | Cliente da API (`NEXT_PUBLIC_API_URL`): login, token, upload com progresso, link assinado do PDF |
| `src/lib/sessao.ts` | Guarda o token no navegador e avisa quando a sessão expira |
| `src/lib/tipos.ts` | Contrato com a API: mantenha em sincronia com `backend/*/schemas.py` |
| `src/components/auth-provider.tsx` · `protegido.tsx` | Sessão (quem está logado) e a guarda que manda para `/login` |
| `src/components/` | Demais telas: upload, lista, escada de fases, evidências, selos de status |

## Decisões que valem saber

- **Os dados são buscados no navegador**, direto na API (CORS liberado só para as origens configuradas no backend).
- **Login por token no `localStorage`** (cabeçalho `Authorization`). Um 401 em qualquer chamada limpa o token e leva a `/login`. Se a **API estiver fora do ar**, a tela avisa e oferece "tentar de novo" em vez de deslogar.
- **Sair e expirar fazem navegação completa** (`window.location.assign`), não troca de rota do Next: com o Cache Components as telas anteriores ficam em memória, e isso mostraria por um instante a lista de quem saiu para o próximo login na mesma máquina.
- **PDF numa nova aba:** a aba não envia `Authorization`, então o botão pede à API um link assinado (2 min, só para aquele PDF) e abre a aba já no clique, para o navegador não bloquear o pop-up.
- **Análise em segundo plano:** a lista e o detalhe buscam de novo a cada 2 s enquanto houver processo `PENDENTE` ou `ANALISANDO`, e param sozinhos.
- **Cache Components está ligado** (padrão do Next 16.4). Na rota dinâmica, o `params` é lido dentro de um `<Suspense>`, como a documentação exige; `useSearchParams` (login) também.
- **A cor nunca é o único sinal**: cada resposta de `divida_paga` e cada status tem ícone e texto. "Ainda não paga" usa o tom azul de propósito, porque é a situação normal de um crédito em aberto, não um erro.
- Os rótulos e a ordem das fases vêm de `GET /api/fases`: uma fase nova em `backend/validate/ladder.py` aparece aqui sem mexer no frontend.
- `output: "standalone"` gera a imagem Docker enxuta ([`Dockerfile`](Dockerfile)). `NEXT_PUBLIC_API_URL` é um argumento de **build**.
