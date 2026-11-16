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

conda env create -f environment.yml    # cria o ambiente "ribeiro-e-souza" (Python 3.12 + pymupdf)
conda activate ribeiro-e-souza         # ative sempre que for trabalhar no projeto
```

Comandos úteis:

```bash
conda deactivate                                  # sair do ambiente
conda env update -f environment.yml --prune       # após mudar o requirements.txt / environment.yml
conda env remove -n ribeiro-e-souza               # apagar o ambiente (recomeçar do zero)
conda env list                                    # listar ambientes
```

> Rode `conda env create` **dentro da pasta do projeto**: o `environment.yml` lê o `requirements.txt` pelo caminho relativo.
> As dependências **do programa** ficam só em `requirements.txt`. O `environment.yml` escolhe o Python, reaproveita esse arquivo e acrescenta `jupyterlab`, `ipykernel` e `pandas`, que servem apenas ao notebook de apresentação (seção 1.3).

**Opção B — venv (sem conda)**

```bash
cd ribeiro_e_souza
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1.2 Executar

Com o ambiente ativado:

```bash
# coloque os PDFs em input/ e rode
python main.py                            # processa todos os PDFs de input/
python main.py "input/meu_processo.pdf"   # ou um PDF específico
python main.py --saida resultados         # grava em outra pasta (padrão: output/)

# testes
python -m unittest discover -s tests -t . -v
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
├── main.py              # CLI: lê argumentos, percorre os PDFs, imprime e exporta
├── app/
│   ├── constantes.py    # ⭐ DICIONÁRIO DE TERMOS, regex, fases, parâmetros
│   ├── classes.py       # Pagina, Evidencia, ResultadoProcesso (dataclasses)
│   ├── erros.py         # ErroPdfNaoEncontrado, ErroPdfProtegido, ErroLeituraPdf
│   └── funcoes.py       # o pipeline (abaixo)
├── input/               # PDFs de entrada (ignorados pelo git)
├── output/              # JSON e CSV gerados (ignorados pelo git)
├── tests/               # testes com textos sintéticos
├── labs/                # notebooks: apresentacao.ipynb (roteiro do projeto, com dados fictícios)
├── requirements.txt     # dependências Python do programa (pymupdf)
└── environment.yml      # ambiente conda: Python 3.12 + requirements.txt + jupyterlab/pandas (notebook)
```

### Pipeline (`app/funcoes.py`)

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

---

## 3. O dicionário de termos

Fica em `app/constantes.py` → `DICIONARIO_TERMOS`, no formato `fase → {nome_do_termo: regex}`:

```python
"QUITADO": {
    "extincao_da_execucao": r"(?:extin[çc][ãa]o|extint[ao]s?|extingo)\s+(?:d[ao]s?\s+|a\s+|o\s+)?(?:execu[çc][ãa]o|cumprimento\s+de\s+senten[çc]a|obriga[çc][ãa]o)",
    "art_924_inciso_II":    r"art(?:igo|\.)?\s*924,?\s*(?:inciso\s+)?II\b",
    ...
}
```

**Para ensinar um termo novo**: acrescente uma linha na fase certa. Não precisa mexer em mais nada. Os testes em `tests/` mostram como validar.

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

**Ressalva importante:** nenhum dos 3 está pago, então o caminho `SIM`/`PROVAVEL` foi validado apenas com **textos sintéticos** (`tests/`), não com um caso real.

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
5. Só então considerar um LLM para estruturar campos ambíguos — mantendo regex como primeira camada e a evidência (página/trecho) como saída obrigatória.

## 7. Dados pessoais (LGPD)

Autos contêm CPF, RG, endereço e, às vezes, dados de saúde. Por isso `input/` e `output/` estão no `.gitignore`: **nunca versione PDFs ou resultados**. Os testes usam apenas dados fictícios.
