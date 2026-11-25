"""O grafo da camada de IA (LangGraph) e o modelo de linguagem.

    START ─► analisar ─► verificar ─► END
             (o modelo     (sem IA: confere cada trecho citado,
              lê os autos)  letra por letra, contra a página)

Mesmo padrão do workflow do ai-agent-sales: estado em TypedDict, um nó por responsabilidade, saída estruturada em Pydantic.
O que veio de lá e o que não veio: ficam o `StateGraph`, o `ChatOpenAI` com `with_structured_output` e os prompts num módulo à
parte. Não vieram as ferramentas de CRM, o RAG e o roteador de intenções: aqui há uma única pergunta, e o texto já chega inteiro.

`langgraph` e `langchain_openai` só são importados quando o grafo é montado: a API sobe, e as demais rotas funcionam, mesmo num
ambiente sem as bibliotecas de IA ou sem chave. A rota de IA é que responde 503.
"""

import re
from typing import Any

from typing_extensions import TypedDict

from ..config import Configuracoes
from ..extract.logic import normalizar_espacos
from .prompt import montar_mensagens
from .schemas import EvidenciaIA, ParecerModelo

MAX_EVIDENCIAS = 8      # a IA é instruída a dar até 6; o que passar disso é cortado
MAX_TRECHO = 500        # caracteres devolvidos por evidência
MIN_TRECHO = 10         # um trecho com menos letras que isso casa em qualquer lugar: não prova nada
ESFORCO_SO_NOS_MODELOS = ("gpt-5", "o1", "o3", "o4")  # `reasoning_effort` dá erro em modelo que não raciocina (gpt-4o...)


class IANaoConfigurada(Exception):
    """Falta a chave da OpenAI ou as bibliotecas de IA: a rota responde 503 com esta mensagem."""


class EstadoIA(TypedDict, total=False):
    processo: Any              # ProcessoEntrada (já sem identificação)
    paginas: list              # list[PaginaEntrada] (já sem capa e anonimizadas)
    parecer: ParecerModelo     # o que o modelo respondeu
    evidencias: list           # list[EvidenciaIA], cada uma conferida contra o texto
    confianca: str
    pontos_de_atencao: list


# ======================================================================================
# O modelo
# ======================================================================================
def criar_modelo(config: Configuracoes):
    """O ChatOpenAI configurado pelo ambiente (RIBEIRO_IA_*). A chave vem do objeto de configuração, que também lê o .env."""
    if not config.openai_api_key:
        raise IANaoConfigurada("A camada de IA não está configurada: defina OPENAI_API_KEY (ou RIBEIRO_OPENAI_API_KEY).")
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise IANaoConfigurada("A camada de IA precisa de langchain-openai e langgraph: instale o requirements.txt.") from None

    argumentos: dict = dict(model=config.ia_modelo, api_key=config.openai_api_key, timeout=config.ia_timeout_segundos, max_retries=2)
    if config.ia_modelo.startswith(ESFORCO_SO_NOS_MODELOS):
        argumentos["reasoning_effort"] = config.ia_esforco
    else:
        argumentos["temperature"] = 0  # modelos de raciocínio só aceitam a temperatura padrão
    return ChatOpenAI(**argumentos)


# ======================================================================================
# A verificação (sem IA)
# ======================================================================================
_RETICENCIAS = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]|\.{3,}|…")


def _normalizar(texto: str) -> str:
    return normalizar_espacos(texto).casefold()


def trecho_confere(trecho: str, texto_da_pagina: str) -> bool:
    """O trecho está, literalmente, no texto da página? Espaços, quebras de linha e maiúsculas não contam.

    Reticências ("...", "[...]", "…") separam fragmentos, e cada um precisa estar na página: a IA costuma abreviar uma citação longa.
    """
    fragmentos = [_normalizar(fragmento) for fragmento in _RETICENCIAS.split(trecho)]
    fragmentos = [fragmento for fragmento in fragmentos if fragmento]
    if sum(len(fragmento) for fragmento in fragmentos) < MIN_TRECHO:
        return False
    texto = _normalizar(texto_da_pagina)
    return all(fragmento in texto for fragmento in fragmentos)


def verificar_parecer(parecer: ParecerModelo, paginas: list) -> tuple:
    """(evidências conferidas, confiança final, pontos de atenção). A IA não pode se declarar mais segura do que as provas permitem."""
    por_numero = {pagina.numero: pagina.texto for pagina in paginas}
    evidencias = [
        EvidenciaIA(
            pagina=evidencia.pagina,
            trecho=evidencia.trecho.strip()[:MAX_TRECHO],
            observacao=evidencia.observacao.strip(),
            verificada=trecho_confere(evidencia.trecho, por_numero.get(evidencia.pagina, "")),
        )
        for evidencia in parecer.evidencias[:MAX_EVIDENCIAS]
    ]
    confianca = parecer.confianca
    pontos = [ponto.strip() for ponto in parecer.pontos_de_atencao if ponto.strip()]
    if parecer.fase == "SEM_INFORMACAO":
        return evidencias, confianca, pontos

    nao_conferem = [evidencia for evidencia in evidencias if not evidencia.verificada]
    if not evidencias:
        confianca = "baixa"
        pontos.append("A IA concluiu uma fase sem citar nenhuma evidência: confira lendo os autos.")
    elif len(nao_conferem) == len(evidencias):
        confianca = "baixa"
        pontos.append("Nenhum trecho citado pela IA foi encontrado literalmente no texto enviado: confira a fase lendo os autos.")
    elif nao_conferem:
        paginas_citadas = ", ".join(str(n) for n in sorted({evidencia.pagina for evidencia in nao_conferem}))
        pontos.append(f"{len(nao_conferem)} trecho(s) citado(s) pela IA não foram encontrados literalmente no texto (pág. {paginas_citadas}).")
        if confianca == "alta":
            confianca = "media"
    return evidencias, confianca, pontos


# ======================================================================================
# O grafo
# ======================================================================================
def construir_grafo(modelo):
    """Compila o grafo em cima de um modelo qualquer que tenha `with_structured_output` (nos testes, um modelo falso)."""
    from langgraph.graph import END, START, StateGraph

    estruturado = modelo.with_structured_output(ParecerModelo)

    async def analisar(estado: EstadoIA) -> EstadoIA:
        resposta = await estruturado.ainvoke(montar_mensagens(estado["processo"], estado["paginas"]))
        return {"parecer": ParecerModelo.model_validate(resposta)}  # aceita o objeto ou um dict; None (recusa) vira erro

    def verificar(estado: EstadoIA) -> EstadoIA:
        evidencias, confianca, pontos = verificar_parecer(estado["parecer"], estado["paginas"])
        return {"evidencias": evidencias, "confianca": confianca, "pontos_de_atencao": pontos}

    grafo = StateGraph(EstadoIA)
    grafo.add_node("analisar", analisar)
    grafo.add_node("verificar", verificar)
    grafo.add_edge(START, "analisar")
    grafo.add_edge("analisar", "verificar")
    grafo.add_edge("verificar", END)
    return grafo.compile()
