"""backend/fases/: cada fase do crédito é um módulo (classes em modelos.py, termos em constantes.py, API em rotas.py)."""

import importlib
import unittest
from pathlib import Path
from unittest import mock

from fastapi import APIRouter

from backend.fases import registro
from backend.fases.modelos import Alerta, Fase, ModuloDeAnalise, RespostaDividaPaga, SituacaoNaEscada, Termo
from backend.leitor import constantes as const
from backend.leitor.classes import Evidencia
from backend.leitor.funcoes import responder_divida_paga
from tests.apoio_backend import PDF_PAGO, PDF_PROTEGIDO, PDF_REQUISICAO, BaseApi

PASTA_FASES = Path(registro.__file__).parent
ESCADA_ESPERADA = [
    ("SEM_INFORMACAO", "sem-informacao", RespostaDividaPaga.SEM_INFORMACAO),
    ("SENTENCA", "sentenca", RespostaDividaPaga.NAO),
    ("TRANSITO_EM_JULGADO", "transito-em-julgado", RespostaDividaPaga.NAO),
    ("CUMPRIMENTO_DE_SENTENCA", "cumprimento-de-sentenca", RespostaDividaPaga.NAO),
    ("REQUISICAO", "requisicao", RespostaDividaPaga.NAO),
    ("PAGAMENTO_DISPONIBILIZADO", "pagamento-disponibilizado", RespostaDividaPaga.PROVAVEL),
    ("QUITADO", "quitado", RespostaDividaPaga.SIM),
]


class TestCadaFaseEUmModulo(unittest.TestCase):
    def test_a_escada_tem_as_seis_fases_e_o_ponto_de_partida_na_ordem(self):
        self.assertEqual([(f.codigo, f.slug, f.divida_paga) for f in registro.ESCADA], ESCADA_ESPERADA)
        self.assertEqual([f.ordem for f in registro.ESCADA], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual([m.codigo for m in registro.MODULOS], [c for c, _, _ in ESCADA_ESPERADA] + ["ALERTA"])

    def test_cada_modulo_tem_a_estrutura_padrao_e_a_sua_classe_em_modelos_py(self):
        for modulo in registro.MODULOS:
            pasta = PASTA_FASES / modulo.slug.replace("-", "_")
            with self.subTest(modulo=modulo.codigo):
                for arquivo in ("__init__.py", "constantes.py", "modelos.py", "rotas.py"):
                    self.assertTrue((pasta / arquivo).is_file(), f"{pasta.name}/{arquivo} não existe")
                # a classe da fase mora no modelos.py da própria pasta, e a API dela no rotas.py da própria pasta
                self.assertEqual(type(modulo).__module__, f"backend.fases.{pasta.name}.modelos")
                rotas = importlib.import_module(f"backend.fases.{pasta.name}.rotas")
                self.assertIsInstance(rotas.roteador, APIRouter)
                self.assertEqual(rotas.roteador.prefix, f"/{modulo.slug}")

    def test_toda_fase_herda_da_base_comum_e_o_alerta_fica_fora_da_escada(self):
        for fase in registro.ESCADA:
            self.assertIsInstance(fase, Fase)
            self.assertTrue(fase.rotulo and fase.descricao)
        self.assertIsInstance(registro.ALERTA, Alerta)
        self.assertNotIsInstance(registro.MODULOS[-1], Fase)
        self.assertIsNone(registro.fase_da_escada("ALERTA"))
        self.assertIsNone(registro.fase_da_escada("QUALQUER"))

    def test_so_o_ponto_de_partida_nao_tem_termos(self):
        for modulo in registro.MODULOS:
            self.assertEqual(bool(modulo.termos), modulo.codigo != "SEM_INFORMACAO", modulo.codigo)
            for termo in modulo.termos:
                self.assertIsInstance(termo, Termo)
                self.assertEqual(termo.regex.pattern, termo.padrao)

    def test_o_dicionario_do_leitor_vem_dos_modulos_na_ordem_da_escada(self):
        self.assertEqual(list(const.DICIONARIO_TERMOS), [c for c, _, _ in ESCADA_ESPERADA[1:]] + ["ALERTA"])
        self.assertEqual(const.DICIONARIO_TERMOS, registro.dicionario_de_termos())
        for modulo in registro.MODULOS:
            self.assertEqual(const.DICIONARIO_TERMOS.get(modulo.codigo, {}), {t.nome: t.padrao for t in modulo.termos})
        self.assertEqual(const.ORDEM_FASE, {f.codigo: f.ordem for f in registro.ESCADA})
        self.assertEqual(const.DESCRICAO_FASE, {f.codigo: f.descricao for f in registro.ESCADA})

    def test_cada_fase_responde_sobre_a_divida_e_codigo_fora_da_escada_responde_nao(self):
        for codigo, _, resposta in ESCADA_ESPERADA:
            self.assertEqual(responder_divida_paga(codigo), resposta.value)
        self.assertEqual(responder_divida_paga("ALERTA"), "NAO")
        self.assertEqual(responder_divida_paga("QUALQUER"), "NAO")

    def test_situacao_de_cada_fase_em_relacao_a_fase_atual(self):
        requisicao = registro.por_codigo("REQUISICAO")
        situacoes = [fase.situacao_em(requisicao) for fase in registro.ESCADA]
        A, T, N = SituacaoNaEscada.ALCANCADA, SituacaoNaEscada.ATUAL, SituacaoNaEscada.NAO_ALCANCADA
        self.assertEqual(situacoes, [A, A, A, A, T, N, N])
        partida = registro.ESCADA[0]
        self.assertEqual([f.situacao_em(partida) for f in registro.ESCADA], [T, N, N, N, N, N, N])
        self.assertIsNone(registro.MODULOS[-1].situacao_em(requisicao))  # fora da escada

    def test_evidencias_de_aceita_o_objeto_do_leitor_e_o_dict_do_banco(self):
        objeto = Evidencia(fase="REQUISICAO", termo="oficio_requisitorio", pagina=2, trecho="x")
        dict_ = {"fase": "QUITADO", "termo": "divida_paga", "pagina": 9, "trecho": "y", "conta": True}
        requisicao, quitado = registro.por_codigo("REQUISICAO"), registro.por_codigo("QUITADO")
        self.assertEqual(requisicao.evidencias_de([objeto, dict_]), [objeto])
        self.assertEqual(quitado.evidencias_de([objeto, dict_]), [dict_])

    def test_a_visao_do_processo_so_traz_a_principal_na_fase_atual(self):
        evidencias = [
            {"fase": "REQUISICAO", "termo": "a", "pagina": 1, "trecho": "", "conta": False},
            {"fase": "REQUISICAO", "termo": "b", "pagina": 2, "trecho": "", "conta": True},
            {"fase": "SENTENCA", "termo": "c", "pagina": 3, "trecho": "", "conta": True},
        ]
        atual = registro.por_codigo("REQUISICAO")
        visao = atual.no_processo(atual, evidencias)
        self.assertEqual((visao.situacao, visao.evidencia_principal["termo"], visao.evidencias_que_contam), (SituacaoNaEscada.ATUAL, "b", 1))
        sentenca = registro.por_codigo("SENTENCA").no_processo(atual, evidencias)
        self.assertEqual((sentenca.situacao, sentenca.evidencia_principal), (SituacaoNaEscada.ALCANCADA, None))

    def test_o_registro_recusa_escada_fora_de_ordem_e_termo_ou_codigo_repetido(self):
        with mock.patch.object(registro, "ESCADA", tuple(reversed(registro.ESCADA))):
            with self.assertRaisesRegex(RuntimeError, "posições"):
                registro._validar()
        repetido = (*registro.MODULOS, registro.MODULOS[1])
        with mock.patch.object(registro, "MODULOS", repetido):
            with self.assertRaisesRegex(RuntimeError, "repetido"):
                registro._validar()

        class Copia(ModuloDeAnalise):  # outro módulo reaproveitando o nome de um termo de Sentença
            codigo, rotulo, descricao = "COPIA", "Cópia", "x"
            termos = (registro.por_codigo("SENTENCA").termos[0],)

        with mock.patch.object(registro, "MODULOS", (*registro.MODULOS, Copia())):
            with self.assertRaisesRegex(RuntimeError, "mesmo nome"):
                registro._validar()


class TestApiDeCadaFase(BaseApi):
    def get(self, token, caminho):
        return self.client.get(caminho, headers=self.cabecalho(token) if token else {})

    def enviar_um(self, token, nome, pdf):
        return self.enviar(token, (nome, pdf)).json()["processos"][0]["id"]

    def test_a_escada_continua_publica_e_igual(self):
        corpo = self.client.get("/api/fases").json()
        self.assertEqual([f["codigo"] for f in corpo["fases"]], [c for c, _, _ in ESCADA_ESPERADA])
        self.assertEqual([f["ordem"] for f in corpo["fases"]], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual([d["valor"] for d in corpo["divida_paga"]], ["SIM", "PROVAVEL", "NAO", "SEM_INFORMACAO"])

    def test_a_definicao_de_cada_modulo_exige_login_e_traz_os_termos(self):
        token = self.login()
        for modulo in registro.MODULOS:
            with self.subTest(modulo=modulo.codigo):
                caminho = f"/api/fases/{modulo.slug}"
                self.assertEqual(self.get(None, caminho).status_code, 401)
                corpo = self.get(token, caminho).json()
                self.assertEqual((corpo["codigo"], corpo["rotulo"], corpo["descricao"]), (modulo.codigo, modulo.rotulo, modulo.descricao))
                self.assertEqual([(t["nome"], t["padrao"]) for t in corpo["termos"]], [(t.nome, t.padrao) for t in modulo.termos])
        requisicao = self.get(token, "/api/fases/requisicao").json()
        self.assertEqual((requisicao["ordem"], requisicao["divida_paga"], requisicao["acao"]), (4, "NAO", "Acompanhar a fase."))
        quitado = self.get(token, "/api/fases/quitado").json()
        self.assertEqual((quitado["ordem"], quitado["divida_paga"]), (6, "SIM"))
        alerta = self.get(token, "/api/fases/alerta").json()  # fora da escada: sem posição e sem resposta sobre a dívida
        self.assertEqual((alerta["ordem"], alerta["divida_paga"], alerta["significado"]), (None, None, None))
        self.assertEqual(self.get(token, "/api/fases/inexistente").status_code, 404)

    def test_um_processo_na_requisicao_visto_por_cada_fase(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_REQUISICAO)
        detalhe = self.get(token, f"/api/processos/{id_}").json()
        self.assertEqual(detalhe["fase"], "REQUISICAO")

        situacoes = {}
        for codigo, slug, _ in ESCADA_ESPERADA:
            corpo = self.get(token, f"/api/fases/{slug}/processos/{id_}").json()
            self.assertEqual(corpo["codigo"], codigo)
            situacoes[codigo] = corpo["situacao"]
        self.assertEqual(
            situacoes,
            {"SEM_INFORMACAO": "ALCANCADA", "SENTENCA": "ALCANCADA", "TRANSITO_EM_JULGADO": "ALCANCADA", "CUMPRIMENTO_DE_SENTENCA": "ALCANCADA",
             "REQUISICAO": "ATUAL", "PAGAMENTO_DISPONIBILIZADO": "NAO_ALCANCADA", "QUITADO": "NAO_ALCANCADA"},
        )

        requisicao = self.get(token, f"/api/fases/requisicao/processos/{id_}").json()
        self.assertEqual((requisicao["total_evidencias"], requisicao["evidencias_que_contam"]), (1, 1))
        self.assertEqual(requisicao["evidencias"][0]["termo"], "oficio_requisitorio")
        self.assertEqual(requisicao["evidencia_principal"], detalhe["evidencia_principal"])  # é a mesma que o processo mostra
        for slug in ("sentenca", "quitado"):  # a evidência principal só existe na fase atual
            self.assertIsNone(self.get(token, f"/api/fases/{slug}/processos/{id_}").json()["evidencia_principal"])
        alerta = self.get(token, f"/api/fases/alerta/processos/{id_}").json()  # fora da escada: sem situação
        self.assertEqual((alerta["situacao"], alerta["evidencias"]), (None, []))

    def test_as_evidencias_dos_modulos_somam_as_do_processo(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_PAGO)
        detalhe = self.get(token, f"/api/processos/{id_}").json()
        self.assertEqual(detalhe["fase"], "QUITADO")
        juntas = []
        for modulo in registro.MODULOS:
            juntas += self.get(token, f"/api/fases/{modulo.slug}/processos/{id_}").json()["evidencias"]
        chave = lambda ev: (ev["fase"], ev["termo"], ev["pagina"])  # noqa: E731
        self.assertEqual(sorted(juntas, key=chave), sorted(detalhe["evidencias"], key=chave))  # nada some e nada se repete
        quitado = self.get(token, f"/api/fases/quitado/processos/{id_}").json()
        self.assertEqual(quitado["situacao"], "ATUAL")
        self.assertEqual(quitado["evidencia_principal"], detalhe["evidencia_principal"])

    def test_processo_de_outra_pessoa_inexistente_ou_sem_resultado(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_PAGO)
        outro = self.criar_usuario("outro@teste.com")
        self.assertEqual(self.get(None, f"/api/fases/quitado/processos/{id_}").status_code, 401)
        self.assertEqual(self.get(outro, f"/api/fases/quitado/processos/{id_}").status_code, 404)  # não revela que existe
        self.assertEqual(self.get(token, f"/api/fases/quitado/processos/{'0' * 32}").status_code, 404)
        falhou = self.enviar_um(token, "protegido.pdf", PDF_PROTEGIDO)
        resposta = self.get(token, f"/api/fases/quitado/processos/{falhou}")
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("falhou", resposta.json()["detail"])  # não diz "ainda não terminou" de uma análise que falhou


if __name__ == "__main__":
    unittest.main()
