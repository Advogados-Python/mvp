from fastapi import APIRouter

from .alerta import rotas as alerta
from .cumprimento_de_sentenca import rotas as cumprimento_de_sentenca
from .funcoes import montar_fases
from .pagamento_disponibilizado import rotas as pagamento_disponibilizado
from .quitado import rotas as quitado
from .requisicao import rotas as requisicao
from .schemas import FasesSaida
from .sem_informacao import rotas as sem_informacao
from .sentenca import rotas as sentenca
from .transito_em_julgado import rotas as transito_em_julgado

roteador = APIRouter(prefix="/api/fases")


@roteador.get("", response_model=FasesSaida, tags=["fases"], summary="A escada de fases e o significado de divida_paga")
def fases():
    return montar_fases()


# A API de cada módulo, abaixo da escada: /api/fases/<fase> e /api/fases/<fase>/processos/{id}. Mantenha na ordem da escada.
for modulo in (
    sem_informacao,
    sentenca,
    transito_em_julgado,
    cumprimento_de_sentenca,
    requisicao,
    pagamento_disponibilizado,
    quitado,
    alerta,
):
    roteador.include_router(modulo.roteador)
