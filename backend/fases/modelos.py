"""As classes do domínio das fases do crédito: o que é uma fase, como ela se identifica e onde um processo está na escada.

Cada fase mora no seu próprio módulo (backend/fases/<fase>/) e define a sua classe em <fase>/modelos.py, herdando de `Fase`.
Este arquivo é a base comum e não conhece nenhuma fase em particular.

    ModuloDeAnalise   uma parte da análise: código, rótulo, descrição e os termos que a identificam nos autos
      ├─ Fase         um degrau da escada do crédito: tem posição (`ordem`) e responde "a dívida já foi paga?"
      └─ Alerta       fora da escada: não define a fase, só gera aviso
    Termo             um termo do dicionário: o nome legível e a expressão regular
    FaseNoProcesso    como UM processo se relaciona com um módulo: a situação na escada e as evidências que são dele
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional


class RespostaDividaPaga(str, Enum):
    """A resposta objetiva à pergunta "a dívida já foi paga?" que cada fase dá quando é a fase final do processo."""

    SIM = "SIM"
    PROVAVEL = "PROVAVEL"
    NAO = "NAO"
    SEM_INFORMACAO = "SEM_INFORMACAO"


class SituacaoNaEscada(str, Enum):
    """Onde uma fase está em relação à fase atual de um processo (o que a tela mostra na escada)."""

    ALCANCADA = "ALCANCADA"          # a fase do processo está depois desta: esta etapa já foi passada
    ATUAL = "ATUAL"                  # é a fase do processo
    NAO_ALCANCADA = "NAO_ALCANCADA"  # a fase do processo ainda está antes desta


@dataclass(frozen=True)
class Termo:
    """Um termo do dicionário. O `nome` aparece no relatório, então use algo que um advogado entenda."""

    nome: str
    padrao: str  # a expressão regular, em texto (sempre compilada sem diferenciar maiúsculas de minúsculas)
    regex: "re.Pattern[str]" = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "regex", re.compile(self.padrao, re.IGNORECASE))


def _campo(evidencia: Any, nome: str) -> Any:
    """Lê um campo da evidência, venha ela do leitor (objeto Evidencia) ou do banco (dict)."""
    return evidencia[nome] if isinstance(evidencia, dict) else getattr(evidencia, nome)


@dataclass(frozen=True)
class FaseNoProcesso:
    """Como um processo se relaciona com um módulo: a situação dele na escada e as evidências que pertencem a ele."""

    modulo: "ModuloDeAnalise"
    situacao: Optional[SituacaoNaEscada]  # None para quem está fora da escada (o alerta)
    evidencias: list
    evidencia_principal: Optional[Any]    # só na fase ATUAL: a primeira evidência que "conta" (o que conferir primeiro)

    @property
    def evidencias_que_contam(self) -> int:
        return sum(1 for ev in self.evidencias if _campo(ev, "conta"))


class ModuloDeAnalise:
    """Uma parte da análise dos autos. Cada subclasse preenche os atributos abaixo (veja qualquer <fase>/modelos.py)."""

    codigo: str                        # a chave que as evidências e o banco guardam (ex.: "REQUISICAO")
    rotulo: str                        # nome curto para telas e chips
    descricao: str                     # o que significa, numa frase
    termos: tuple[Termo, ...] = ()     # as expressões que identificam o módulo nos autos

    @property
    def slug(self) -> str:
        """O nome do módulo na URL: REQUISICAO -> requisicao, TRANSITO_EM_JULGADO -> transito-em-julgado."""
        return self.codigo.lower().replace("_", "-")

    def evidencias_de(self, evidencias: Iterable[Any]) -> list:
        """Só as evidências que este módulo encontrou."""
        return [ev for ev in evidencias if _campo(ev, "fase") == self.codigo]

    def situacao_em(self, atual: "Fase") -> Optional[SituacaoNaEscada]:
        """Fora da escada não há situação. As fases sobrescrevem isto."""
        return None

    def no_processo(self, atual: "Fase", evidencias: Iterable[Any]) -> FaseNoProcesso:
        """O módulo visto por um processo cuja fase atual é `atual` e que tem estas evidências (todas, de todos os módulos)."""
        proprias = self.evidencias_de(evidencias)
        situacao = self.situacao_em(atual)
        principal = None
        if situacao is SituacaoNaEscada.ATUAL:
            principal = next((ev for ev in proprias if _campo(ev, "conta")), None)
        return FaseNoProcesso(modulo=self, situacao=situacao, evidencias=proprias, evidencia_principal=principal)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.codigo}>"


class Fase(ModuloDeAnalise):
    """Um degrau da escada do crédito. A fase do processo é a MAIS ALTA que tiver evidência confiável."""

    ordem: int                         # 0 = ponto de partida (sem informação) ... quanto maior, mais perto de "dívida paga"
    divida_paga: RespostaDividaPaga    # o que esta fase responde quando é a fase final do processo

    def situacao_em(self, atual: "Fase") -> SituacaoNaEscada:
        if self.ordem == atual.ordem:
            return SituacaoNaEscada.ATUAL
        return SituacaoNaEscada.ALCANCADA if self.ordem < atual.ordem else SituacaoNaEscada.NAO_ALCANCADA


class Alerta(ModuloDeAnalise):
    """Fora da escada: um sinal de que a conclusão pode estar errada (ex.: "julgo improcedente" => talvez não haja crédito).
    Gera um aviso no relatório; nunca muda a fase."""
