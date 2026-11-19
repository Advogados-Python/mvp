from ..fabrica import criar_roteador
from . import FASE

# A API do módulo CUMPRIMENTO DE SENTENÇA, sob /api/fases/cumprimento-de-sentenca:
#   GET /api/fases/cumprimento-de-sentenca                         o que é, o que significa e os termos que a identificam
#   GET /api/fases/cumprimento-de-sentenca/processos/{processo_id}  como um processo se relaciona com ela (situação na escada e evidências)
roteador = criar_roteador(FASE)
