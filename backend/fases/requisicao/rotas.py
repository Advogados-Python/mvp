from ..fabrica import criar_roteador
from . import FASE

# A API do módulo REQUISIÇÃO, sob /api/fases/requisicao:
#   GET /api/fases/requisicao                         o que é, o que significa e os termos que a identificam
#   GET /api/fases/requisicao/processos/{processo_id}  como um processo se relaciona com ela (situação na escada e evidências)
roteador = criar_roteador(FASE)
