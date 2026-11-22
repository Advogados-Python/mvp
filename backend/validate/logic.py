"""Fase 5 da leitura, VALIDANDO AS EVIDÊNCIAS: pesa as evidências (só as que "contam" decidem), conclui a fase do crédito,
responde "a dívida já foi paga?" e levanta os avisos que o advogado precisa ler."""

from .ladder import DESCRICAO_FASE, DIVIDA_PAGA_NAO, ORDEM_FASE, SIGNIFICADO_DIVIDA_PAGA, ESCADA, fase_da_escada
from .models import Conclusao
from .schemas import FaseSaida, FasesSaida, SignificadoDivida


def classificar_fase(evidencias: list) -> str:
    """A fase é a mais avançada da escada que tenha ao menos uma evidência que 'conta'."""
    fase = "SEM_INFORMACAO"
    for ev in evidencias:
        if ev.conta and ev.fase in ORDEM_FASE and ORDEM_FASE[ev.fase] > ORDEM_FASE[fase]:
            fase = ev.fase
    return fase


def responder_divida_paga(fase: str) -> str:
    """Traduz a fase na resposta direta: SIM / PROVAVEL / NAO / SEM_INFORMACAO. Quem responde é a própria fase
    (validate/ladder.py: `divida_paga`). Um código que não é da escada responde NAO, como sempre."""
    degrau = fase_da_escada(fase)
    return degrau.divida_paga.value if degrau else DIVIDA_PAGA_NAO


def _avisar_mencoes_ignoradas(fase: str, evidencias: list) -> list:
    """Errar para 'não pago' é o erro caro (comprar crédito já quitado), então nada some em silêncio.

    Se há menção CONDICIONAL a pagamento/quitação acima da fase atual (texto-padrão tipo
    'após o pagamento, será intimada para o levantamento'), ela foi ignorada na classificação,
    mas fica sinalizada com as páginas para conferência humana.
    """
    atual = ORDEM_FASE[fase]
    paginas = sorted({
        ev.pagina for ev in evidencias
        if ev.hipotetico and ev.origem_confiavel
        and ev.fase in ("PAGAMENTO_DISPONIBILIZADO", "QUITADO")
        and ORDEM_FASE[ev.fase] > atual
    })
    if not paginas:
        return []
    return [
        "Menções condicionais/futuras a pagamento ou quitação foram ignoradas (pág. "
        + ", ".join(map(str, paginas[:10]))
        + "). Se alguma for pagamento real, a fase está subestimada."
    ]


def validar_evidencias(evidencias: list) -> Conclusao:
    """A fase inteira: da lista de evidências sai a Conclusao (fase final, descrição, dívida paga e avisos)."""
    fase = classificar_fase(evidencias)
    avisos = []
    if any(ev.fase == "ALERTA" and ev.conta for ev in evidencias):
        avisos.append("Encontrado 'julgo improcedente' em peça do juízo: confirme se existe mesmo crédito a receber.")
    avisos.extend(_avisar_mencoes_ignoradas(fase, evidencias))
    return Conclusao(fase=fase, fase_descricao=DESCRICAO_FASE[fase], divida_paga=responder_divida_paga(fase), avisos=avisos)



def montar_fases() -> FasesSaida:
    """A escada e o significado de cada resposta sobre a dívida, como a API a entrega (GET /api/fases)."""
    return FasesSaida(
        fases=[FaseSaida(codigo=f.codigo, rotulo=f.rotulo, descricao=f.descricao, ordem=f.ordem) for f in ESCADA],
        divida_paga=[
            SignificadoDivida(valor=resposta.value, significado=significado, acao=acao)
            for resposta, (significado, acao) in SIGNIFICADO_DIVIDA_PAGA.items()
        ],
    )
