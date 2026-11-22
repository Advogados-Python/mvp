"""A escada do crédito (validate/ladder.py) e o dicionário de termos (search/terms.py): o vocabulário do RESULTADO."""

import unittest
from unittest import mock

from backend.search import terms
from backend.validate import ladder
from backend.validate.logic import responder_divida_paga
from backend.validate.models import Fase, RespostaDividaPaga
from tests.apoio_backend import BaseApi

ESCADA_ESPERADA = [
    ("SEM_INFORMACAO", RespostaDividaPaga.SEM_INFORMACAO),
    ("SENTENCA", RespostaDividaPaga.NAO),
    ("TRANSITO_EM_JULGADO", RespostaDividaPaga.NAO),
    ("CUMPRIMENTO_DE_SENTENCA", RespostaDividaPaga.NAO),
    ("REQUISICAO", RespostaDividaPaga.NAO),
    ("PAGAMENTO_DISPONIBILIZADO", RespostaDividaPaga.PROVAVEL),
    ("QUITADO", RespostaDividaPaga.SIM),
]


class TestEscada(unittest.TestCase):
    def test_seis_fases_do_credito_mais_o_ponto_de_partida_na_ordem(self):
        self.assertEqual([(f.codigo, f.divida_paga) for f in ladder.ESCADA], ESCADA_ESPERADA)
        self.assertEqual([f.ordem for f in ladder.ESCADA], [0, 1, 2, 3, 4, 5, 6])
        for fase in ladder.ESCADA:
            self.assertIsInstance(fase, Fase)
            self.assertTrue(fase.rotulo and fase.descricao)

    def test_as_tabelas_derivadas_da_escada(self):
        self.assertEqual(ladder.ORDEM_FASE, {f.codigo: f.ordem for f in ladder.ESCADA})
        self.assertEqual(ladder.DESCRICAO_FASE, {f.codigo: f.descricao for f in ladder.ESCADA})
        self.assertEqual(ladder.FASES, tuple((f.codigo, f.descricao) for f in ladder.ESCADA))
        self.assertIsNone(ladder.fase_da_escada("ALERTA"))  # o alerta não é um degrau
        self.assertIs(ladder.fase_da_escada("QUITADO"), ladder.QUITADO)

    def test_cada_fase_responde_sobre_a_divida_e_codigo_fora_da_escada_responde_nao(self):
        for codigo, resposta in ESCADA_ESPERADA:
            self.assertEqual(responder_divida_paga(codigo), resposta.value)
        self.assertEqual(responder_divida_paga("ALERTA"), "NAO")
        self.assertEqual(responder_divida_paga("QUALQUER"), "NAO")

    def test_a_escada_fora_de_ordem_ou_com_codigo_repetido_falha_na_subida(self):
        with mock.patch.object(ladder, "ESCADA", tuple(reversed(ladder.ESCADA))):
            with self.assertRaisesRegex(RuntimeError, "posições"):
                ladder._validar()
        repetida = (*ladder.ESCADA[:-1], ladder.ESCADA[-2])
        with mock.patch.object(ladder, "ESCADA", repetida):
            with self.assertRaises(RuntimeError):
                ladder._validar()


class TestDicionario(unittest.TestCase):
    def test_as_chaves_seguem_a_escada_e_o_alerta_vem_por_ultimo(self):
        self.assertEqual(list(terms.DICIONARIO_TERMOS), [c for c, _ in ESCADA_ESPERADA[1:]] + ["ALERTA"])
        for fase in terms.DICIONARIO_TERMOS:
            self.assertTrue(fase == "ALERTA" or ladder.fase_da_escada(fase), fase)

    def test_todo_termo_compila_e_o_nome_nao_se_repete_entre_fases(self):
        nomes = [(termo, padrao) for termos in terms.DICIONARIO_TERMOS.values() for termo, padrao in termos.items()]
        self.assertEqual(len(nomes), 30)
        self.assertEqual(len({n for n, _ in nomes}), len(nomes), "o nome do termo aparece no relatório: não pode se repetir")
        self.assertEqual([(f, t) for f, t, _ in terms.TERMOS_COMPILADOS], [(f, t) for f, ts in terms.DICIONARIO_TERMOS.items() for t in ts])
        for _, _, regex in terms.TERMOS_COMPILADOS:
            self.assertTrue(regex.flags & __import__("re").IGNORECASE)


class TestEscadaNaApi(BaseApi):
    def test_a_escada_e_publica_e_traz_as_fases_na_ordem(self):
        corpo = self.client.get("/api/fases").json()
        self.assertEqual([f["codigo"] for f in corpo["fases"]], [c for c, _ in ESCADA_ESPERADA])
        self.assertEqual([f["ordem"] for f in corpo["fases"]], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual([d["valor"] for d in corpo["divida_paga"]], ["SIM", "PROVAVEL", "NAO", "SEM_INFORMACAO"])
        self.assertTrue(all(f["rotulo"] and f["descricao"] for f in corpo["fases"]))


if __name__ == "__main__":
    unittest.main()
