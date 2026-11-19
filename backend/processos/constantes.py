import re

from ..leitor.erros import ErroLeituraPdf, ErroPdfNaoEncontrado, ErroPdfProtegido

BLOCO_LEITURA = 1024 * 1024
RE_ID = re.compile(r"^[0-9a-f]{32}$")  # ids são gerados por nós (uuid4 hex); o id vira nome de arquivo

# Acompanhamento ao vivo (SSE). A conexão é encerrada de tempos em tempos de propósito (Configuracoes.sse_duracao_maxima):
# proxies cortam conexões longas e um servidor que reinicia não pode esperar para sempre por uma aba aberta.
# O front reconecta na hora (é só um "oi" de novo).
SSE_PING_SEGUNDOS = 15                # comentário periódico para a conexão não parecer ociosa
SSE_INTERVALO_MINIMO_SEGUNDOS = 0.2   # no máximo ~5 eventos por segundo, mesmo que o PDF tenha mil páginas

# Mensagens mostradas ao usuário quando o leitor falha.
MENSAGEM_POR_ERRO = {
    ErroPdfProtegido: "O PDF está protegido por senha.",
    ErroLeituraPdf: "Não foi possível abrir o arquivo como PDF (corrompido ou formato inválido).",
    ErroPdfNaoEncontrado: "O arquivo do PDF não foi encontrado no servidor.",
}
MENSAGEM_ERRO_INESPERADO = "Erro inesperado ao analisar o arquivo. Tente de novo; se persistir, avise o suporte."
