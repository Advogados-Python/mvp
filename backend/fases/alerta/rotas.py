from ..fabrica import criar_roteador
from . import ALERTA

# A API do módulo ALERTA, sob /api/fases/alerta:
#   GET /api/fases/alerta                         o que é, o que significa e os termos que a identificam
#   GET /api/fases/alerta/processos/{processo_id}  como um processo se relaciona com ela (situação na escada e evidências)
roteador = criar_roteador(ALERTA)
