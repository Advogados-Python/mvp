"""Classes de dados do MVP: Pagina, Evidencia e ResultadoProcesso."""

from dataclasses import asdict, dataclass, field
from typing import Optional

from . import constantes as const


@dataclass
class Pagina:
    """Uma página do PDF já convertida em texto."""
    numero: int                              # 1 = primeira página
    texto: str
    documento_id: Optional[str] = None       # PJe: id do documento a que a página pertence
    tipo_documento: Optional[str] = None     # PJe: "Sentença Tipo A", "Petição inicial"...
    assinante: Optional[str] = None          # PJe: quem assinou o documento

    @property
    def sem_texto(self) -> bool:
        return len(self.texto.strip()) < const.MIN_CARACTERES_PAGINA


@dataclass
class Evidencia:
    """Um trecho do PDF que casou com um termo do dicionário. É a 'prova' mostrada ao advogado."""
    fase: str                                # chave do DICIONARIO_TERMOS (ex.: "REQUISICAO")
    termo: str                               # nome do termo (ex.: "oficio_requisitorio")
    pagina: int
    trecho: str
    tipo_documento: Optional[str] = None
    hipotetico: bool = False                 # frase condicional/futura/negada ("aguarde-se o pagamento")
    origem_confiavel: bool = True            # False = veio de peça da parte (petição, manifestação...)

    @property
    def conta(self) -> bool:
        """Só evidências não hipotéticas e vindas do juízo decidem a fase."""
        return not self.hipotetico and self.origem_confiavel


@dataclass
class ResultadoProcesso:
    """Tudo o que o sistema descobriu sobre um PDF."""
    arquivo: str
    total_paginas: int = 0
    paginas_sem_texto: int = 0
    numero_processo: Optional[str] = None
    tribunal: Optional[str] = None
    classe: Optional[str] = None
    orgao_julgador: Optional[str] = None
    valor_causa: Optional[str] = None
    valor_requisitado: Optional[str] = None
    data_emissao_pdf: Optional[str] = None   # "posição" do processo quando o PDF foi gerado
    partes: list = field(default_factory=list)       # [{"nome": ..., "papel": ...}]
    advogados: list = field(default_factory=list)    # nomes
    oabs: list = field(default_factory=list)         # ["OAB/GO 12345", ...] mais frequentes
    juiz: Optional[str] = None
    fase: str = "SEM_INFORMACAO"
    fase_descricao: str = const.DESCRICAO_FASE["SEM_INFORMACAO"]
    divida_paga: str = const.DIVIDA_PAGA_SEM_INFO
    avisos: list = field(default_factory=list)
    evidencias: list = field(default_factory=list)   # list[Evidencia]

    def evidencia_principal(self) -> Optional[Evidencia]:
        """A evidência (que conta) da fase final: o que o advogado deve conferir primeiro."""
        for ev in self.evidencias:
            if ev.conta and ev.fase == self.fase:
                return ev
        return None

    def para_dict(self) -> dict:
        return asdict(self)
