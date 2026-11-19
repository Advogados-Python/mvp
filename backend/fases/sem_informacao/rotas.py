from ..fabrica import criar_roteador
from . import FASE

# A API do módulo SEM INFORMAÇÃO, sob /api/fases/sem-informacao:
#   GET /api/fases/sem-informacao                         o que é, o que significa e os termos que a identificam
#   GET /api/fases/sem-informacao/processos/{processo_id}  como um processo se relaciona com ela (situação na escada e evidências)
roteador = criar_roteador(FASE)
