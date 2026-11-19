# Ribeiro e Souza — Leitor de Processos (MVP)

Lê PDFs de processos judiciais e responde, com **evidência (página + trecho)**, às perguntas do escritório:

- Qual é o processo, as partes, os advogados (e OAB) e o juiz?
- Em que fase está o crédito contra o Estado — sentença, trânsito em julgado, requisição (RPV/OPV/precatório), pagamento?
- **A dívida já foi paga/liquidada?** (`SIM` / `PROVAVEL` / `NAO` / `SEM_INFORMACAO`)

O MVP usa só **regex + dicionário de termos** (sem IA generativa). Cada decisão é rastreável até uma página do PDF.

---

## 1. Como rodar

Requer Python 3.10+ (o `environment.yml` usa 3.12). Escolha **uma** das opções de ambiente.

### 1.1 Criar o ambiente (uma vez só)

**Opção A — conda (recomendada)**

```bash
cd ribeiro_e_souza

conda env create -f environment.yml    # cria o ambiente "ribeiro-e-souza" (Python 3.12 + dependências + jupyter)
conda activate ribeiro-e-souza         # ative sempre que for trabalhar no projeto
```

Comandos úteis:

```bash
conda deactivate                                  # sair do ambiente
conda env update -f environment.yml --prune       # após mudar o requirements.txt / environment.yml
conda env remove -n ribeiro-e-souza               # apagar o ambiente (recomeçar do zero)
conda env list                                    # listar ambientes
```

> Rode `conda env create` **dentro da pasta do projeto**: o `environment.yml` lê os arquivos de requisitos pelo caminho relativo.
> As dependências **do programa** ficam em `requirements.txt` (o CLI só precisa do `pymupdf`; o resto é a API). O `environment.yml` escolhe o Python, reaproveita esse arquivo e acrescenta o `httpx` (só dos testes da API) e `jupyterlab`, `ipykernel` e `pandas`, que servem apenas ao notebook de apresentação (seção 1.3).

**Opção B — venv (sem conda)**

```bash
cd ribeiro_e_souza
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install httpx                      # só se for rodar os testes da API
```

### 1.2 Executar

Com o ambiente ativado:

```bash
# coloque os PDFs em input/ e rode
python main.py                            # processa todos os PDFs de input/
python main.py "input/meu_processo.pdf"   # ou um PDF específico
python main.py --saida resultados         # grava em outra pasta (padrão: output/)

# testes (um arquivo por módulo; a API sobe de verdade, com SQLite temporário)
python -m unittest discover -s tests -t . -v
python -m unittest tests.test_leitor -v   # só o leitor de PDFs (rápido e sem FastAPI)

# a mesma suíte num Postgres de verdade (as tabelas desse banco são APAGADAS: use um banco só para testes)
RIBEIRO_TESTE_BANCO_URL=postgresql://usuario:senha@localhost:5432/teste python -m unittest discover -s tests -t .
```

Sem ativar o ambiente (útil em scripts/agendador), com conda:

```bash
conda run -n ribeiro-e-souza python main.py
```

### 1.3 Notebook de apresentação

[`labs/apresentacao.ipynb`](labs/apresentacao.ipynb) conta o projeto do início ao fim: o problema, cada arquivo (`constantes` → `erros` → `classes` → `funcoes`), o pipeline passo a passo até o **JSON**, o `main.py`, os filtros de segurança e as limitações. Ele já vem executado (as saídas estão salvas).

Usa **dois processos fictícios gerados no próprio notebook**, então não expõe dados de clientes e pode ser versionado. Os PDFs reais de `input/` só são lidos se você ligar a chave `USAR_PDFS_REAIS` do apêndice (nesse caso, limpe as saídas antes de salvar ou versionar).

```bash
conda activate ribeiro-e-souza
python -m jupyterlab labs/apresentacao.ipynb      # abre no navegador
```

No **VS Code**: abra o arquivo e, em *Select Kernel*, escolha o ambiente `ribeiro-e-souza` (ou o kernel *Python (ribeiro-e-souza)*, se registrado).

> ⚠️ Use `python -m jupyterlab` (e não só `jupyter lab`): se houver outro Jupyter no `PATH` (ex.: instalado pelo Homebrew), o comando `jupyter` pode abrir **aquele**, sem o `pandas`/`pymupdf` do ambiente. Para registrar o kernel do ambiente (uma vez):
> ```bash
> python -m ipykernel install --user --name ribeiro-e-souza --display-name "Python (ribeiro-e-souza)"
> ```

Para apresentar fora do Jupyter (HTML estático, abre em qualquer navegador):

```bash
python -m nbconvert --to html labs/apresentacao.ipynb
```

Para rodar o notebook inteiro de novo e regravar as saídas:

```bash
python -m nbconvert --to notebook --execute --inplace labs/apresentacao.ipynb
```

### 1.4 Interface web (backend + frontend)

Além da linha de comando, há uma interface web: um **backend** FastAPI ([`backend/`](backend/)) com login, banco de dados e análise em segundo plano, e um **frontend** Next.js ([`frontend/`](frontend/)). Cada pessoa entra com a sua conta, envia PDFs arrastando-os, acompanha a análise, vê a "escada" de fases, os avisos e as evidências, e abre o PDF direto na página citada.

**Rodar localmente** (3 passos; com o ambiente ativado):

```bash
# 1) primeira vez: crie o primeiro administrador (a senha é pedida no terminal)
python -m backend.cli criar-usuario --email voce@exemplo.com --nome "Seu Nome" --admin

# 2) API: http://localhost:8000 (documentação interativa em /docs)
uvicorn backend.main:app --reload

# 3) frontend: http://localhost:3000
cd frontend && npm install && npm run dev
```

> **Prefere rodar de dentro da pasta `backend/`?** Lá há um `requirements.txt` próprio: `pip install -r requirements.txt` instala as dependências **e** o pacote em modo editável, e depois os mesmos comandos (`python -m backend.cli ...`, `uvicorn backend.main:app --reload`) funcionam a partir dessa pasta.

Sem configurar nada, o backend usa **SQLite** em `data/ribeiro.db` e guarda os PDFs em `data/pdfs/` (a pasta `data/` está no `.gitignore`). Sem `RIBEIRO_JWT_SEGREDO` ele gera um segredo temporário: os logins caem ao reiniciar. Em vez do passo 1, dá para definir `RIBEIRO_ADMIN_EMAIL` e `RIBEIRO_ADMIN_SENHA`: o administrador é criado na primeira subida, se o banco ainda não tiver usuários.

**Rodar com Docker** (Postgres + API + frontend):

```bash
cp .env.example .env        # preencha POSTGRES_PASSWORD, RIBEIRO_JWT_SEGREDO (openssl rand -hex 32) e o administrador
docker compose up --build   # frontend em http://localhost:3000, API em http://localhost:8000/docs
```

Todas as variáveis de ambiente estão documentadas em [`.env.example`](.env.example). As principais: `DATABASE_URL` (Postgres; sem ela, SQLite), `RIBEIRO_PASTA_DADOS`, `RIBEIRO_JWT_SEGREDO`, `RIBEIRO_CORS_ORIGINS` (endereço do frontend) e, no frontend, `NEXT_PUBLIC_API_URL` (gravada no build: mudou o endereço, faça o build de novo).

| Rota | O que faz |
|---|---|
| `POST /api/auth/login` | Entra com e-mail e senha (formulário OAuth2) e devolve o token JWT |
| `GET /api/auth/eu` · `POST /api/auth/senha` | Quem está logado · trocar a própria senha (derruba os outros logins) |
| `GET/POST /api/usuarios` · `PATCH /api/usuarios/{id}` | **Administrador:** listar, criar, desativar, redefinir a senha |
| `POST /api/processos` | Envia 1+ PDFs (multipart, campo `arquivos`). Responde **na hora** (202); a análise segue em segundo plano. Arquivo vazio, grande demais ou que não é PDF volta em `falhas`, sem derrubar o lote |
| `GET /api/processos` | Lista os **seus** processos, com `status` (`PENDENTE`, `ANALISANDO`, `CONCLUIDO`, `FALHOU`) |
| `GET /api/processos/{id}` | Resultado completo, com todas as evidências. Em `ANALISANDO` traz `progresso` (a etapa atual); em `FALHOU`, a etapa onde parou |
| `GET /api/processos/{id}/eventos` | Acompanha a análise **ao vivo** (Server-Sent Events, mesmo login por cabeçalho). Só traz status e etapa; ao terminar (`fim`) o resultado vem do `GET` acima |
| `POST /api/processos/{id}/reanalisar` | Refaz a análise (útil depois de ensinar termos novos ao dicionário) |
| `POST /api/processos/{id}/pdf-link` · `GET .../pdf` | Link assinado de 2 min para abrir o PDF numa nova aba (`#page=N`) · o PDF |
| `DELETE /api/processos/{id}` | Apaga o PDF e o resultado |
| `GET /api/fases` · `GET /api/saude` | A escada de fases (pública) · saúde da API e do banco (healthcheck) |
| `GET /api/fases/{fase}` | A API de **cada fase** (`sentenca`, `transito-em-julgado`, `cumprimento-de-sentenca`, `requisicao`, `pagamento-disponibilizado`, `quitado`, mais `sem-informacao` e `alerta`): o que é, o que responde sobre a dívida e os termos que a identificam (exige login) |
| `GET /api/fases/{fase}/processos/{id}` | Como **um processo** se relaciona com a fase: a situação dela na escada (`ALCANCADA`, `ATUAL` ou `NAO_ALCANCADA`) e as evidências que são dela. Só para análise concluída (409 enquanto roda ou se falhou) |

**Como funciona, e o que vale saber:**

- **Cada processo pertence a quem o enviou.** Os outros usuários, **inclusive o administrador**, recebem 404. O mesmo PDF enviado de novo pelo mesmo usuário reaproveita o registro e refaz a análise.
- **Login:** token JWT (8 h por padrão) guardado no `localStorage` do navegador. Trocar a senha, desativar a conta ou redefinir a senha derruba os logins antigos na hora. Após 5 falhas seguidas (por IP + e-mail) o login é bloqueado por 15 min; e-mail inexistente e senha errada dão a mesma resposta. As senhas ficam em Argon2id.
- **PDF numa nova aba:** a aba não envia o cabeçalho `Authorization`, então a API entrega um link assinado de vida curta, válido só para aquele PDF e para aquele usuário.
- **Análise em segundo plano:** a fila é um conjunto de threads do próprio processo, e quem manda é a coluna `status` do banco. Se o servidor cair no meio, ao subir ele devolve os processos pendentes e "analisando" para a fila. **Rode a API com um único worker** (a fila vive na memória de um processo).
- **Acompanhamento da análise:** o leitor informa cada etapa real do pipeline (ler o PDF página a página → identificar o processo → buscar termos página a página → validar as evidências → gravar). A tela mostra só isso: **nada é estimado**, não há percentual geral, e a contagem de páginas só aparece onde o leitor a informa. O andamento fica na memória da API (como a fila): se ela reiniciar, a análise volta para a fila e recomeça. A tela usa SSE e, se ele não conectar ou cair, consulta a API a cada 2 s e tenta o SSE de novo. A conexão SSE é encerrada a cada `RIBEIRO_SSE_DURACAO_MAXIMA` segundos (30) e a tela reabre sozinha: proxies cortam conexões longas e um deploy não fica esperando uma aba aberta (o `Dockerfile` usa `--timeout-graceful-shutdown`).
- **Banco:** `create_all` cria as tabelas que faltam, mas **não altera as existentes**: uma mudança de esquema futura pede migrações (Alembic).

**Testes**

```bash
python -m unittest discover -s tests -t .        # backend: leitor, API, fila e progresso (SQLite temporário)
```

Interface (Playwright + axe-core): integração com a API real, estados do acompanhamento, responsividade em 4 larguras (320 a 1440 px; salva capturas em `frontend/test-results/telas/`) e acessibilidade (WCAG 2.2 A/AA). Rodam contra uma stack **descartável**, porque criam e apagam processos: veja o cabeçalho de [`frontend/playwright.config.ts`](frontend/playwright.config.ts) para subir a API e o frontend de teste. Depois: `cd frontend && npm run test:e2e`. Os testes exercitam o frontend **já compilado** (`npm run build`): recompile depois de mudar o código.

**Deploy no Railway** (segue a configuração dos arquivos [`railway.json`](railway.json) e [`frontend/railway.json`](frontend/railway.json); o que foi exercitado aqui foi o Docker Compose, **o deploy no Railway em si não foi testado**):

1. Crie o projeto com o plugin **Postgres** e dois serviços a partir deste repositório: a **API** (raiz do repositório, usa o `Dockerfile`) e o **frontend** (*Root Directory* = `frontend`).
2. Variáveis da API: `RIBEIRO_AMBIENTE=producao`, `RIBEIRO_JWT_SEGREDO` (`openssl rand -hex 32`), `DATABASE_URL` (referência ao Postgres), `RIBEIRO_CORS_ORIGINS` (o endereço público do frontend), `RIBEIRO_ADMIN_EMAIL`/`RIBEIRO_ADMIN_SENHA` e `FORWARDED_ALLOW_IPS=*` (atrás do proxy, para o limite de login enxergar o IP real).
3. Monte um **volume em `/data`** no serviço da API (é onde ficam os PDFs). Se o volume vier sem permissão de escrita para o usuário da imagem, defina `RAILWAY_RUN_UID=0`.
4. Variável do frontend: `NEXT_PUBLIC_API_URL` = endereço público da API (é um argumento de build).
5. Mantenha **uma** réplica da API.

### O que sai

| Saída | Conteúdo |
|---|---|
| Terminal | Resumo legível por processo: dados, fase, `DÍVIDA PAGA?`, avisos e as evidências da fase |
| `output/<nome-do-pdf>.json` | Resultado completo, com **todas** as evidências (inclusive as ignoradas) |
| `output/resumo.csv` | Uma linha por processo (`;` e UTF-8 com BOM: abre direto no Excel pt-BR) |

Como ler `divida_paga`:

| Valor | Significa | Ação sugerida |
|---|---|---|
| `SIM` | Há evidência de levantamento/extinção por pagamento | Conferir a página indicada |
| `PROVAVEL` | Valor depositado/disponibilizado, falta confirmar o levantamento | Conferir a página indicada |
| `NAO` | Ainda não pago (a `fase` diz onde está: ex. `REQUISICAO`) | — |
| `SEM_INFORMACAO` | Nenhum termo de fase encontrado | Ler o PDF / verificar `avisos` |

> **Sempre leia o campo `avisos`.** Ele informa páginas que não puderam ser lidas (scan) e menções a pagamento que foram ignoradas por serem condicionais.

---

## 2. Arquitetura

```
ribeiro_e_souza/
├── main.py                  # CLI: lê argumentos, percorre os PDFs, imprime e exporta (só precisa do leitor)
├── backend/                 # um papel por pasta; dentro de cada uma, os mesmos nomes de arquivo
│   ├── main.py              # a API: monta o FastAPI, o ciclo de vida e as rotas
│   ├── cli.py               # gerência de usuários: python -m backend.cli criar-usuario ...
│   ├── leitor/              # ⭐ o pipeline que lê o PDF (era o app/): usado pelo CLI e pela API
│   │   ├── constantes.py    #    regex, parâmetros; lê a escada e o dicionário de backend/fases/
│   │   ├── classes.py       #    Pagina, Evidencia, ResultadoProcesso (dataclasses)
│   │   ├── erros.py         #    ErroPdfNaoEncontrado, ErroPdfProtegido, ErroLeituraPdf
│   │   └── funcoes.py       #    o pipeline (abaixo)
│   ├── nucleo/              # configuração (variáveis de ambiente), banco, dependências comuns, /api/saude
│   ├── fases/               # ⭐ a escada do crédito: CADA FASE É UM MÓDULO, com as suas classes e a sua API
│   │   ├── modelos.py       #    classes-base: ModuloDeAnalise, Fase, Alerta, Termo, FaseNoProcesso (+ enums)
│   │   ├── registro.py      #    a escada na ordem (e o alerta); recusa ordem errada ou termo repetido
│   │   ├── fabrica.py       #    a API padrão de um módulo · rotas.py agrupa todas sob /api/fases
│   │   ├── sentenca/  transito_em_julgado/  cumprimento_de_sentenca/  requisicao/  pagamento_disponibilizado/  quitado/
│   │   ├── sem_informacao/  alerta/     # o ponto de partida e o que fica fora da escada
│   │   │   └── (em cada um)  constantes.py (os TERMOS) · modelos.py (a classe da fase) · rotas.py (a API) · __init__.py (FASE)
│   │   └── schemas.py  funcoes.py  constantes.py        # formatos da API, montagem das respostas, significado da dívida
│   ├── usuarios/            # tabela de usuários e administração
│   ├── autenticacao/        # login, senhas (Argon2), tokens JWT, link assinado do PDF, proteção das rotas
│   └── processos/           # upload, PDFs em disco, fila de análise, resultados no banco
│       ├── modelos.py  schemas.py  rotas.py  dependencias.py
│       └── armazem.py  fila.py  analise.py  funcoes.py  constantes.py  erros.py
├── frontend/                # interface web (Next.js + Tailwind): login, upload, lista, detalhe com evidências
├── tests/                   # um arquivo por módulo; textos sintéticos, nenhum dado real
├── labs/                    # notebooks: apresentacao.ipynb (roteiro do leitor, com dados fictícios)
├── input/  output/          # PDFs e resultados do CLI (ignorados pelo git: LGPD)
├── data/                    # SQLite e PDFs enviados pela API em desenvolvimento (ignorado pelo git)
├── Dockerfile  docker-compose.yml  railway.json  .env.example
└── requirements.txt  environment.yml
```

### Pipeline (`backend/leitor/funcoes.py`)

```
PDF ─► ler_pdf ─► identificar_documentos ─► extrair_metadados ─► buscar_termos ─► classificar_fase ─► exportar
       (texto     (PJe: id/tipo/assinante   (nº, tribunal,        (dicionário +    (fase mais alta      (JSON, CSV,
        por pág.)  de cada página)           partes, OAB, juiz)    regex → pág.     com evidência        terminal)
                                                                   + trecho)        confiável)
```

1. **`ler_pdf`** — PyMuPDF, texto por página em ordem de leitura. Ignora texto rotacionado (a assinatura vertical do e-SAJ). PDF sem texto não dá erro: as páginas voltam marcadas `sem_texto`.
2. **`identificar_documentos`** — os autos do PJe juntam dezenas de documentos num só PDF. Cada página traz `Num. <id> - Pág. N` e `Documento id <id> - <tipo>`; isso diz de que **tipo** de peça é cada página e quem a assinou.
3. **`extrair_metadados`** — número CNJ (e o tribunal pelo código `J.TR`), classe, órgão, valor da causa, partes, advogados, OABs mais citadas, valor requisitado e **juiz** (no PJe: quem assina a sentença; no e-SAJ: `Juiz(a) de Direito: Dr(a). ...`).
4. **`buscar_termos`** — aplica o dicionário e guarda cada achado como `Evidencia` (página, trecho, tipo do documento).
5. **`classificar_fase`** — sobe uma "escada" de fases; vale a **mais alta com evidência confiável**.

### A escada de fases

```
SENTENCA ► TRANSITO_EM_JULGADO ► CUMPRIMENTO_DE_SENTENCA ► REQUISICAO ► PAGAMENTO_DISPONIBILIZADO ► QUITADO
                                                          (RPV/OPV/precatório)   (depositado)        (levantado/extinto)
                                                          └── ainda NÃO pago ──┘   └─ PROVAVEL ─┘      └─ SIM ─┘
```

**Cada fase é um módulo do backend** (`backend/fases/<fase>/`), no mesmo desenho dos demais pacotes:

| Arquivo | O que tem | Exemplo (`requisicao/`) |
|---|---|---|
| `modelos.py` | a **classe da fase** (herda de `Fase`): código, rótulo, descrição, posição na escada, o que responde sobre a dívida e os termos | `class Requisicao(Fase)`: `ordem = 4`, `divida_paga = NAO` |
| `constantes.py` | os **termos** (regex) que a identificam nos autos | `oficio_requisitorio`, `expedicao_rpv_precatorio`... |
| `rotas.py` | a **API** da fase | `GET /api/fases/requisicao` |

As classes comuns ficam em `backend/fases/modelos.py`: `ModuloDeAnalise` (código, rótulo, descrição e termos) é a base de `Fase` (um degrau da escada: tem `ordem` e `divida_paga`) e de `Alerta` (fora da escada: só gera aviso). `Termo` é um termo do dicionário e `FaseNoProcesso` é o que uma fase diz sobre *um* processo (a situação dela na escada e as evidências que são dela). `registro.py` junta os módulos na ordem e falha na subida se a escada estiver fora de ordem ou se dois termos tiverem o mesmo nome.

Para acrescentar uma fase: crie a pasta com os quatro arquivos, copiando uma existente, e inclua-a em `registro.py` e em `rotas.py`.

---

## 3. O dicionário de termos

Cada fase guarda os seus termos em `backend/fases/<fase>/constantes.py`, no formato `{nome_do_termo: regex}` (por exemplo, `backend/fases/quitado/constantes.py`):

```python
TERMOS = {
    "extincao_da_execucao": r"(?:extin[çc][ãa]o|extint[ao]s?|extingo)\s+(?:d[ao]s?\s+|a\s+|o\s+)?(?:execu[çc][ãa]o|cumprimento\s+de\s+senten[çc]a|obriga[çc][ãa]o)",
    "art_924_inciso_II":    r"art(?:igo|\.)?\s*924,?\s*(?:inciso\s+)?II\b",
    ...
}
```

O leitor junta tudo no `DICIONARIO_TERMOS` (`backend/leitor/constantes.py`), na ordem da escada. **Para ensinar um termo novo**: acrescente uma linha no `constantes.py` da fase certa. Não precisa mexer em mais nada. Os testes em `tests/test_leitor.py` mostram como validar.

Regra de ouro: **use frases específicas, nunca palavras soltas.** "pagamento" aparece dezenas de vezes nos autos do INSS falando do *benefício*; `pagamento efetuado/realizado/disponibilizado` é o que significa algo.

### Como o sistema evita falso "pago" (e falso "não pago")

Autos judiciais estão cheios de texto-padrão no futuro ("*Após o pagamento, a parte será intimada para o levantamento…*"). Num dos processos de teste isso, sem proteção, viraria "pagamento disponibilizado". Por isso cada achado passa por dois filtros:

| Filtro | Efeito |
|---|---|
| **Contexto hipotético** — palavras como *após, será, caso, aguarde, requer, sob pena, antes da…* na mesma frase, ou *não/sem* colado no termo | Evidência fica `hipotetico: true`: aparece no JSON mas **não muda a fase** |
| **Origem do documento** (PJe) — só peças do juízo (sentença, decisão, despacho, certidão, ofício, alvará…) decidem a fase; petições, contestações e manifestações das partes não | Evidência fica `origem_confiavel: false` |

Para não esconder um pagamento real, quando algo condicional acima da fase atual é ignorado o relatório **avisa as páginas** para conferência humana.

---

## 4. Resultado nos PDFs de exemplo

Foram testados 3 autos reais: 1 do TJSP (e-SAJ, 72 págs.) e 2 de JEF Cível do TRF1 (PJe, 163 e 306 págs.). Cada um processa em ~1 s.

| Processo | Fase detectada | Dívida paga? | Conferência manual |
|---|---|---|---|
| TJSP (e-SAJ) | `REQUISICAO` — decisão manda expedir ofício requisitório e "aguardar quitação" | `NAO` | Coerente com a decisão |
| JEF 13ª Vara | `REQUISICAO` — RPV expedida; PDF gerado 8 dias depois | `NAO` | Coerente com a linha do tempo |
| JEF 14ª Vara | `REQUISICAO` — RPV expedida; PDF gerado 1 mês depois | `NAO` | Coerente com a linha do tempo |

**Ressalva importante:** nenhum dos 3 está pago, então o caminho `SIM`/`PROVAVEL` foi validado apenas com **textos sintéticos** (`tests/test_leitor.py`), não com um caso real.

---

## 5. Limitações conhecidas

- **Falta validar com um processo realmente pago.** Os termos de `PAGAMENTO_DISPONIBILIZADO` e `QUITADO` são hipóteses razoáveis (CPC art. 924, II; alvará; levantamento), mas só um caso real confirma quais frases cada tribunal usa. **Próximo passo mais valioso: o escritório fornecer 3–5 PDFs de processos já pagos.**
- **PDFs escaneados (imagem) não são lidos.** No exemplo do TJSP, 52 de 72 páginas são imagem; o relatório lista as páginas não lidas. O OCR não está implementado (requer Tesseract instalado); o caminho natural é aplicar OCR só nessas páginas (PyMuPDF tem `page.get_textpage_ocr`).
- **Os PDFs de exemplo são "autos do processo", não o Diário da Justiça.** O parser de capa cobre PJe e e-SAJ. O formato do Diário (DJe/DJEN) tem só um fallback para advogado (`ADV: NOME (OAB…)`) e **não foi testado** com PDF real de Diário.
- A fase é a mais alta com evidência: um único trecho mal interpretado em fase alta distorce o resultado, daí a obrigação de conferir a página citada.
- Frases quebradas entre duas páginas não são detectadas (a busca é por página).
- Só reconhece a numeração CNJ (`NNNNNNN-DD.AAAA.J.TR.OOOO`).

## 6. Próximos passos sugeridos

1. Validar e ampliar o dicionário com PDFs de processos pagos.
2. OCR nas páginas sem texto.
3. Consulta por número do processo: avaliar a API pública do **DataJud (CNJ)** em vez de raspar sites de tribunais (verifique termos de uso e limites antes de automatizar consultas em massa).
4. Entrada opcional de Diário da Justiça (DJe/DJEN): obter um PDF real e calibrar os regex.
5. **Migrações de banco (Alembic)** antes da primeira mudança de esquema; **HTTPS** na frente da API; rotina de **expiração dos PDFs** enviados (LGPD); e, se o escritório quiser compartilhar processos entre usuários, um modelo de equipes (hoje cada processo é só de quem o enviou).
6. Só então considerar um LLM para estruturar campos ambíguos — mantendo regex como primeira camada e a evidência (página/trecho) como saída obrigatória.

## 7. Dados pessoais (LGPD)

Autos contêm CPF, RG, endereço e, às vezes, dados de saúde. Por isso `input/`, `output/`, `data/` e `.env` estão no `.gitignore`: **nunca versione PDFs, resultados, bancos ou segredos**. Os testes usam apenas dados fictícios.

Na API, cada processo só é visível para quem o enviou, os PDFs ficam em disco com permissão `0600` e as respostas do PDF saem com `Cache-Control: private, no-store`. O usuário pode apagar o PDF e o resultado a qualquer momento. Lembre que o token de login fica no `localStorage` do navegador: use a API sempre por HTTPS fora da sua máquina.
