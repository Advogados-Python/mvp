from ..fabrica import criar_roteador
from . import FASE

# A API do módulo PAGAMENTO DISPONIBILIZADO, sob /api/fases/pagamento-disponibilizado:
#   GET /api/fases/pagamento-disponibilizado                         o que é, o que significa e os termos que a identificam
#   GET /api/fases/pagamento-disponibilizado/processos/{processo_id}  como um processo se relaciona com ela (situação na escada e evidências)
roteador = criar_roteador(FASE)
