from ..fabrica import criar_roteador
from . import FASE

# A API do módulo TRÂNSITO EM JULGADO, sob /api/fases/transito-em-julgado:
#   GET /api/fases/transito-em-julgado                         o que é, o que significa e os termos que a identificam
#   GET /api/fases/transito-em-julgado/processos/{processo_id}  como um processo se relaciona com ela (situação na escada e evidências)
roteador = criar_roteador(FASE)
