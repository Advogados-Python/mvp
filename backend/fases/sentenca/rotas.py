from ..fabrica import criar_roteador
from . import FASE

# A API do módulo SENTENÇA, sob /api/fases/sentenca:
#   GET /api/fases/sentenca                         o que é, o que significa e os termos que a identificam
#   GET /api/fases/sentenca/processos/{processo_id}  como um processo se relaciona com ela (situação na escada e evidências)
roteador = criar_roteador(FASE)
