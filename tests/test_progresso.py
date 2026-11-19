"""Progresso da análise: o leitor informa as etapas, o registro guarda, a API expõe e o SSE transmite.

Regra que estes testes protegem: só aparece o que o pipeline de fato informou (nada estimado) e o resultado,
a fase e a "dívida paga" são exatamente os mesmos com ou sem acompanhamento.
"""

import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from backend.leitor import constantes as const
from backend.leitor.funcoes import processar_pdf as processar_de_verdade
from backend.processos import fila as modulo_fila
from backend.processos import progresso as modulo_progresso
from backend.processos.progresso import ETAPAS, RegistroProgresso
from tests.apoio_backend import PDF_PAGO, PDF_PROTEGIDO, PDF_REQUISICAO, BaseApi, gerar_pdf

ANALISE = "backend.processos.analise.processar_pdf"
FILA = "backend.processos.fila.analisar_processo"


class TestLeitorInformaAsEtapas(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.caminho = Path(self._tmp.name) / "autos.pdf"
        self.caminho.write_bytes(gerar_pdf("Numero: 1234567-89.2025.4.01.3500", "Expeça-se ofício requisitório.", "fim"))

    def test_as_etapas_vem_na_ordem_real_com_as_paginas_de_verdade(self):
        chamadas = []
        processar_de_verdade(self.caminho, lambda etapa, atual=None, total=None: chamadas.append((etapa, atual, total)))

        etapas = [etapa for etapa, _, _ in chamadas]
        sem_repeticao = [e for i, e in enumerate(etapas) if i == 0 or e != etapas[i - 1]]
        self.assertEqual(
            sem_repeticao,
            [const.ETAPA_LENDO_PDF, const.ETAPA_IDENTIFICANDO, const.ETAPA_ANALISANDO_FASES, const.ETAPA_VALIDANDO],
        )
        for etapa in (const.ETAPA_LENDO_PDF, const.ETAPA_ANALISANDO_FASES):
            paginas = [(atual, total) for e, atual, total in chamadas if e == etapa and atual is not None]
            self.assertEqual(paginas[0], (0, 3))  # o total é conhecido antes da primeira página
            self.assertEqual(paginas[-1], (3, 3))  # e termina em n/n
            self.assertEqual([a for a, _ in paginas], sorted(a for a, _ in paginas))  # nunca anda para trás
        for etapa in (const.ETAPA_IDENTIFICANDO, const.ETAPA_VALIDANDO):  # etapas sem página a página não inventam contagem
            self.assertEqual({(a, t) for e, a, t in chamadas if e == etapa}, {(None, None)})

    def test_acompanhar_nao_muda_o_resultado(self):
        sem = processar_de_verdade(self.caminho)
        com = processar_de_verdade(self.caminho, lambda *args: None)
        self.assertEqual(com.para_dict(), sem.para_dict())
        self.assertEqual((com.fase, com.divida_paga), ("REQUISICAO", "NAO"))


class TestRegistro(unittest.TestCase):
    def test_o_que_cada_status_pode_mostrar(self):
        registro = RegistroProgresso()
        self.assertIsNone(registro.visivel("a", "ANALISANDO"))  # nada informado ainda: nada a mostrar

        registro.atualizar("a", "LENDO_PDF", 4, 10)
        andamento = registro.visivel("a", "ANALISANDO")
        self.assertEqual((andamento.etapa, andamento.atual, andamento.total, andamento.falhou), ("LENDO_PDF", 4, 10, False))
        for status in ("PENDENTE", "CONCLUIDO", "FALHOU"):  # só ANALISANDO mostra andamento
            self.assertIsNone(registro.visivel("a", status))

        registro.falhar("a")
        self.assertTrue(registro.visivel("a", "FALHOU").falhou)
        self.assertEqual(registro.visivel("a", "FALHOU").etapa, "LENDO_PDF")  # onde parou
        for status in ("PENDENTE", "ANALISANDO", "CONCLUIDO"):  # sobra de uma execução anterior não vaza
            self.assertIsNone(registro.visivel("a", status))

        registro.atualizar("a", "LENDO_PDF")  # nova execução: a falha antiga deixa de valer
        self.assertFalse(registro.obter("a").falhou)
        registro.descartar("a")
        self.assertIsNone(registro.obter("a"))

    def test_falhar_sem_entrada_e_descartar_repetido_nao_quebram(self):
        registro = RegistroProgresso()
        registro.falhar("nada")
        registro.descartar("nada")
        self.assertIsNone(registro.obter("nada"))

    def test_o_registro_tem_teto(self):
        with mock.patch.object(modulo_progresso, "MAX_REGISTROS", 3):
            registro = RegistroProgresso()
            for numero in range(5):
                registro.atualizar(f"p{numero}", "LENDO_PDF")
        self.assertEqual([registro.obter(f"p{n}") is not None for n in range(5)], [False, False, True, True, True])

    def test_a_assinatura_acorda_com_mudancas_de_outra_thread_e_se_desfaz(self):
        registro = RegistroProgresso()

        async def cenario():
            with registro.assinar("x") as mudou:
                threading.Timer(0.05, registro.atualizar, ["x", "LENDO_PDF", 1, 2]).start()
                await asyncio.wait_for(mudou.wait(), 3)
                mudou.clear()
                threading.Timer(0.05, registro.descartar, ["x"]).start()
                await asyncio.wait_for(mudou.wait(), 3)

        asyncio.run(cenario())
        self.assertEqual(registro._ouvintes, {})  # sem ouvintes pendurados

    def test_as_etapas_do_registro_batem_com_as_do_leitor(self):
        self.assertEqual(
            ETAPAS,
            (const.ETAPA_LENDO_PDF, const.ETAPA_IDENTIFICANDO, const.ETAPA_ANALISANDO_FASES, const.ETAPA_VALIDANDO, "FINALIZANDO"),
        )


class BaseComLeitorLento(BaseApi):
    fila_sincrona = False

    def leitor_que_para(self, etapa="ANALISANDO_FASES", atual=3, total=10):
        """Um leitor que informa a etapa e fica parado até liberarem; depois faz o trabalho de verdade."""
        chegou, liberar = threading.Event(), threading.Event()

        def leitor(caminho, aviso=None):
            aviso(etapa, atual, total)
            chegou.set()
            liberar.wait(15)
            return processar_de_verdade(caminho, aviso)

        return leitor, chegou, liberar

    def get(self, token, caminho):
        return self.client.get(caminho, headers=self.cabecalho(token))


class TestProgressoNaApi(BaseComLeitorLento):
    def test_em_analise_mostra_a_etapa_real_e_ao_concluir_some(self):
        token = self.login()
        leitor, chegou, liberar = self.leitor_que_para("ANALISANDO_FASES", 3, 10)
        with mock.patch(ANALISE, leitor):
            id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
            self.assertTrue(chegou.wait(5))
            esperado = {"etapa": "ANALISANDO_FASES", "atual": 3, "total": 10, "falhou": False}

            detalhe = self.get(token, f"/api/processos/{id_}").json()
            self.assertEqual((detalhe["status"], detalhe["progresso"]), ("ANALISANDO", esperado))
            na_lista = self.get(token, "/api/processos").json()["processos"][0]
            self.assertEqual(na_lista["progresso"], esperado)

            liberar.set()
            concluido = self.esperar(token, id_)
        self.assertIsNone(concluido["progresso"])
        self.assertEqual((concluido["fase"], concluido["divida_paga"]), ("QUITADO", "SIM"))

    def test_na_fila_nao_tem_progresso(self):
        token = self.login()
        liberar = threading.Event()
        original = modulo_fila.analisar_processo

        def segura(*args):
            liberar.wait(10)
            return original(*args)

        with mock.patch(FILA, segura):
            resumo = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]
            self.assertEqual((resumo["status"], resumo["progresso"]), ("PENDENTE", None))
            liberar.set()
            self.esperar(token, resumo["id"])

    def test_falha_guarda_a_etapa_onde_parou_e_a_reanalise_limpa_isso(self):
        token = self.login()
        id_ = self.enviar(token, ("protegido.pdf", PDF_PROTEGIDO)).json()["processos"][0]["id"]
        falhou = self.esperar(token, id_, "FALHOU")
        self.assertEqual(falhou["progresso"], {"etapa": "LENDO_PDF", "atual": None, "total": None, "falhou": True})
        self.assertIn("protegido", falhou["erro"])

        # reanálise: enquanto não reinicia, o processo está na fila e a falha antiga não aparece
        original = modulo_fila.analisar_processo
        liberar = threading.Event()
        with mock.patch(FILA, lambda *a: (liberar.wait(10), original(*a))[1]):
            reenfileirado = self.client.post(f"/api/processos/{id_}/reanalisar", headers=self.cabecalho(token)).json()
            self.assertEqual((reenfileirado["status"], reenfileirado["progresso"]), ("PENDENTE", None))
            liberar.set()
            de_novo = self.esperar(token, id_, "FALHOU")
        self.assertTrue(de_novo["progresso"]["falhou"])

    def test_apagar_no_meio_da_analise_limpa_o_registro(self):
        token = self.login()
        registro = self.app.state.fila.progresso
        leitor, chegou, liberar = self.leitor_que_para()
        with mock.patch(ANALISE, leitor):
            id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
            self.assertTrue(chegou.wait(5))
            self.assertIsNotNone(registro.obter(id_))
            self.assertEqual(self.client.delete(f"/api/processos/{id_}", headers=self.cabecalho(token)).status_code, 204)
            self.assertIsNone(registro.obter(id_))
            liberar.set()
            # a análise ainda termina, encontra o registro apagado e não deixa rastro nem exceção
            for _ in range(100):
                if registro.obter(id_) is None and self.get(token, "/api/processos").json()["total"] == 0:
                    break
                threading.Event().wait(0.05)
        self.assertIsNone(registro.obter(id_))


def ler_eventos(resposta) -> list:
    """[(nome, dados)] do corpo text/event-stream; comentários (": ping") viram ("ping", None)."""
    eventos = []
    for bloco in resposta.text.strip().split("\n\n"):
        nome, dados = None, None
        for linha in bloco.splitlines():
            if linha.startswith("event: "):
                nome = linha[7:]
            elif linha.startswith("data: "):
                dados = json.loads(linha[6:])
            elif linha.startswith(":"):
                nome = "ping"
        if nome:
            eventos.append((nome, dados))
    return eventos


class TestEventosSse(BaseComLeitorLento):
    def url(self, id_):
        return f"/api/processos/{id_}/eventos"

    def test_exige_login_e_so_o_dono_acompanha(self):
        token = self.login()
        id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
        self.assertEqual(self.client.get(self.url(id_)).status_code, 401)
        outro = self.criar_usuario("outro@teste.com")
        self.assertEqual(self.get(outro, self.url(id_)).status_code, 404)
        self.assertEqual(self.get(token, self.url("0" * 32)).status_code, 404)

    def test_processo_ja_terminado_responde_o_fim_e_fecha(self):
        token = self.login()
        id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
        self.esperar(token, id_)
        resposta = self.get(token, self.url(id_))
        self.assertEqual(resposta.headers["content-type"].split(";")[0], "text/event-stream")
        self.assertEqual(resposta.headers["cache-control"], "no-store")
        self.assertEqual(ler_eventos(resposta), [("fim", {"status": "CONCLUIDO", "progresso": None})])

    def test_acompanha_a_analise_e_termina_em_fim(self):
        token = self.login()
        leitor, chegou, liberar = self.leitor_que_para("ANALISANDO_FASES", 3, 10)
        with mock.patch(ANALISE, leitor):
            id_ = self.enviar(token, ("p.pdf", PDF_REQUISICAO)).json()["processos"][0]["id"]
            self.assertTrue(chegou.wait(5))
            threading.Timer(0.5, liberar.set).start()  # o TestClient só devolve o corpo quando a transmissão acaba
            eventos = ler_eventos(self.get(token, self.url(id_)))

        nomes = [nome for nome, _ in eventos]
        self.assertEqual(nomes[0], "estado")
        self.assertEqual(
            eventos[0][1],
            {"status": "ANALISANDO", "progresso": {"etapa": "ANALISANDO_FASES", "atual": 3, "total": 10, "falhou": False}},
        )
        self.assertEqual(nomes[-1], "fim")
        self.assertEqual(eventos[-1][1], {"status": "CONCLUIDO", "progresso": None})
        self.assertEqual(nomes.count("fim"), 1)
        etapas = [d["progresso"]["etapa"] for n, d in eventos if n == "estado" and d["progresso"]]
        self.assertEqual(etapas, sorted(etapas, key=ETAPAS.index))  # nunca volta para uma etapa anterior
        self.assertEqual(self.get(token, f"/api/processos/{id_}").json()["fase"], "REQUISICAO")  # o resultado vem do GET

    def test_falha_chega_no_fim_com_a_etapa_onde_parou(self):
        token = self.login()
        liberar = threading.Event()
        original = modulo_fila.analisar_processo
        with mock.patch(FILA, lambda *a: (liberar.wait(10), original(*a))[1]):
            id_ = self.enviar(token, ("protegido.pdf", PDF_PROTEGIDO)).json()["processos"][0]["id"]
            threading.Timer(0.3, liberar.set).start()
            eventos = ler_eventos(self.get(token, self.url(id_)))
        self.assertEqual(eventos[0], ("estado", {"status": "PENDENTE", "progresso": None}))
        self.assertEqual(
            eventos[-1],
            ("fim", {"status": "FALHOU", "progresso": {"etapa": "LENDO_PDF", "atual": None, "total": None, "falhou": True}}),
        )

    def test_apagar_durante_a_transmissao_avisa_removido(self):
        token = self.login()
        leitor, chegou, liberar = self.leitor_que_para()
        with mock.patch(ANALISE, leitor):
            id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
            self.assertTrue(chegou.wait(5))
            threading.Timer(
                0.4, lambda: self.client.delete(f"/api/processos/{id_}", headers=self.cabecalho(token))
            ).start()
            eventos = ler_eventos(self.get(token, self.url(id_)))
            liberar.set()
        self.assertEqual(eventos[-1], ("removido", {}))

    def test_o_limite_de_duracao_pede_para_reconectar_e_ha_ping_no_meio(self):
        token = self.login()
        leitor, chegou, liberar = self.leitor_que_para()
        with mock.patch(ANALISE, leitor), mock.patch.object(self.app.state.config, "sse_duracao_maxima", 0.5), \
                mock.patch("backend.processos.rotas.SSE_PING_SEGUNDOS", 0.1):
            id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
            self.assertTrue(chegou.wait(5))
            eventos = ler_eventos(self.get(token, self.url(id_)))
            liberar.set()
            self.esperar(token, id_)
        nomes = [nome for nome, _ in eventos]
        self.assertEqual((nomes[0], nomes[-1]), ("estado", "reconectar"))
        self.assertIn("ping", nomes)


if __name__ == "__main__":
    unittest.main()
