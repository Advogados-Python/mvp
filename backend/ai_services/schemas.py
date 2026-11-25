"""O que entra e o que sai da camada de IA, e o contrato que o modelo de linguagem precisa devolver.

Entrada (PedidoIA): o resultado das fases de leitura (`processo`) e o texto inteiro, página a página, SEM o cabeçalho (`paginas`).
Cada página leva o seu número no PDF original: é por ele que a IA cita a evidência, e é ele que o advogado abre.

`ProcessoEntrada` aceita o `ResultadoProcesso.para_dict()` inteiro, mas só LÊ o que a IA precisa. Número do processo, nome do
arquivo, partes, advogados, OABs, juiz, classe, órgão e valores são descartados já aqui: nunca chegam ao modelo.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..validate.ladder import ESCADA
from ..validate.schemas import DividaPaga

CODIGOS_FASE = tuple(fase.codigo for fase in ESCADA)  # a escada do crédito é a fonte única: o modelo só pode responder com um degrau dela
FaseCodigo = Literal[CODIGOS_FASE]
Confianca = Literal["alta", "media", "baixa"]

MAX_PAGINAS = 5000
MAX_EVIDENCIAS_ENTRADA = 500


# ======================================================================================
# Entrada
# ======================================================================================
class PaginaEntrada(BaseModel):
    numero: int = Field(ge=1, description="Número da página no PDF ORIGINAL (a capa removida não renumera as demais)")
    texto: str


class EvidenciaEntrada(BaseModel):
    """Uma Evidencia da fase 4 (search/models.py)."""

    fase: str
    termo: str
    pagina: int = Field(ge=1)
    trecho: str
    tipo_documento: Optional[str] = None
    hipotetico: bool = False
    origem_confiavel: bool = True

    @property
    def conta(self) -> bool:
        return not self.hipotetico and self.origem_confiavel


class ProcessoEntrada(BaseModel):
    """O resultado das fases 2 a 5, no formato de `ResultadoProcesso.para_dict()`. Campos que não estão aqui são ignorados."""

    model_config = ConfigDict(extra="ignore")

    tribunal: Optional[str] = Field(default=None, max_length=40, description="Sigla (TRF1, TJSP...): é o único dado de identificação que segue")
    total_paginas: int = Field(default=0, ge=0)
    paginas_sem_texto: int = Field(default=0, ge=0)
    fase: FaseCodigo = "SEM_INFORMACAO"
    avisos: list[str] = Field(default_factory=list, max_length=200)
    evidencias: list[EvidenciaEntrada] = Field(default_factory=list, max_length=MAX_EVIDENCIAS_ENTRADA)


class PedidoIA(BaseModel):
    processo: ProcessoEntrada
    paginas: list[PaginaEntrada] = Field(min_length=1, max_length=MAX_PAGINAS, description="O texto inteiro, sem o cabeçalho")

    @model_validator(mode="after")
    def _paginas_sem_repeticao(self):
        numeros = [pagina.numero for pagina in self.paginas]
        if len(set(numeros)) != len(numeros):
            raise ValueError("Há páginas com o mesmo número: cada página só pode aparecer uma vez.")
        return self


# ======================================================================================
# O que o modelo de linguagem devolve (saída estruturada)
# ======================================================================================
class EvidenciaModelo(BaseModel):
    """Uma prova que sustenta a fase escolhida."""

    pagina: int = Field(description="Número da página, como aparece em '=== PÁGINA N ==='")
    trecho: str = Field(description="Cópia LITERAL de até 300 caracteres do texto DESSA página. Não parafraseie.")
    observacao: str = Field(description="Em uma frase, por que este trecho prova a fase")


class ParecerModelo(BaseModel):
    """O parecer da IA sobre em que fase do crédito o processo está."""

    fase: FaseCodigo = Field(description="O degrau mais alto da escada com prova confiável no texto; SEM_INFORMACAO se não houver prova")
    confianca: Confianca = Field(description="alta: prova direta e sem conflito · media: prova indireta · baixa: dúvida real")
    resumo: str = Field(description="Em 2 a 4 frases: onde o crédito está e o que falta para ser pago")
    justificativa: str = Field(description="Por que esta fase e não a anterior ou a seguinte; diga se discorda do resultado automático e por quê")
    evidencias: list[EvidenciaModelo] = Field(description="De 1 a 6 provas da fase escolhida; lista vazia só se a fase for SEM_INFORMACAO")
    pontos_de_atencao: list[str] = Field(description="O que o advogado deve conferir: menções ambíguas a pagamento, conflitos, páginas ilegíveis")


# ======================================================================================
# Saída
# ======================================================================================
class EvidenciaIA(BaseModel):
    pagina: int
    trecho: str
    observacao: str
    verificada: bool = Field(description="O trecho foi encontrado, literalmente, nessa página do texto enviado (a IA não inventou)")


class AnaliseIA(BaseModel):
    """O parecer da camada de IA, já conferido contra o texto."""

    modelo: str
    fase_sugerida: FaseCodigo
    fase_descricao: str
    divida_paga_sugerida: DividaPaga  # sai da fase, pela mesma escada do restante do sistema (validate/ladder.py)
    concorda_com_regras: bool         # a fase da IA é a mesma que as regras (regex + dicionário) concluíram
    confianca: Confianca
    resumo: str
    justificativa: str
    evidencias: list[EvidenciaIA]
    pontos_de_atencao: list[str]
    paginas_analisadas: int           # páginas que foram para o modelo
    paginas_cabecalho_removidas: int  # páginas de capa que ainda vinham no texto e foram retiradas aqui (0 se o chamador já as tirou)
    caracteres_enviados: int
