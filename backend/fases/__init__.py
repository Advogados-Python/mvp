"""As fases do crédito. Cada fase da escada é um módulo próprio, com a sua API e as suas classes.

    fases/
      modelos.py            as classes-base do domínio: ModuloDeAnalise, Fase, Termo, FaseNoProcesso (e as enums)
      registro.py           a escada na ordem (e o alerta): quem existe e em que posição
      fabrica.py            monta a API padrão de um módulo (a mesma para todos)
      rotas.py              GET /api/fases (a escada) + as APIs de cada módulo, abaixo dela
      schemas.py · funcoes.py · constantes.py   formatos da API, regras de montagem, textos da escada

      sem_informacao/   0  Nenhuma informação de fase encontrada (o ponto de partida)
      sentenca/         1  Sentença/condenação proferida
      transito_em_julgado/        2  Transitou em julgado
      cumprimento_de_sentenca/    3  Em cumprimento de sentença / cálculos
      requisicao/       4  Requisição (RPV/OPV/precatório) determinada ou expedida
      pagamento_disponibilizado/  5  Valor depositado/disponibilizado, aguardando levantamento
      quitado/          6  Dívida paga/liquidada
      alerta/           fora da escada: sinais de que pode não haver crédito (ex.: sentença improcedente)

Dentro de cada módulo, o mesmo desenho dos demais pacotes do backend:
    constantes.py   os TERMOS (regex) que identificam a fase nos autos. Para ensinar um termo novo, acrescente uma linha aqui
    modelos.py      a classe da fase (herda de Fase): código, rótulo, descrição, posição, o que diz sobre a dívida e os termos
    rotas.py        a API da fase: o que ela é e como o sistema a reconhece, e como um processo se relaciona com ela
    __init__.py     expõe FASE, a instância usada pelo registro

Escolha bons nomes de termo (aparecem no relatório) e evite termos soltos como "pagamento" ou "quitação": no INSS, por exemplo,
"pagamento" aparece 40x só falando do benefício. Prefira frases específicas.

Este pacote NÃO importa o leitor nem os processos (só as rotas conhecem os processos): o leitor é quem usa as fases.
"""
