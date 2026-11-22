"""processos/fila.py com threads de verdade: responde na hora, analisa depois, recupera após queda."""

import threading
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.main import criar_app
from backend import pipeline as modulo_fila
from backend.pipeline import analisar_processo
from backend.receive.models import Processo
from tests.apoio_backend import PDF_PAGO, PDF_REQUISICAO, BaseApi, configuracao


class TestFilaEmSegundoPlano(BaseApi):
    fila_sincrona = False

    def test_upload_responde_na_hora_e_a_analise_termina_depois(self):
        token = self.login()
        liberar = threading.Event()
        original = modulo_fila.analisar_processo

        def segura_ate_liberar(*args, **kwargs):  # simula uma análise demorada (autos de 300 páginas, OCR...)
            liberar.wait(10)
            return original(*args, **kwargs)

        with mock.patch.object(modulo_fila, "analisar_processo", segura_ate_liberar):
            resposta = self.enviar(token, ("p.pdf", PDF_PAGO))
            self.assertEqual(resposta.status_code, 202)
            resumo = resposta.json()["processos"][0]
            self.assertEqual(resumo["status"], "PENDENTE")
            self.assertIsNone(resumo["fase"])  # ainda sem resultado
            self.assertEqual(self.client.get("/api/processos", headers=self.cabecalho(token)).json()["processos"][0]["status"], "PENDENTE")
            liberar.set()
            detalhe = self.esperar(token, resumo["id"])
        self.assertEqual((detalhe["fase"], detalhe["divida_paga"]), ("QUITADO", "SIM"))
        self.assertTrue(detalhe["evidencias"])
        self.assertIsNotNone(detalhe["concluido_em"])

    def test_varios_pdfs_sao_analisados_em_paralelo(self):
        token = self.login()
        ids = [p["id"] for p in self.enviar(token, ("a.pdf", PDF_PAGO), ("b.pdf", PDF_REQUISICAO)).json()["processos"]]
        fases = {self.esperar(token, id_)["fase"] for id_ in ids}
        self.assertEqual(fases, {"QUITADO", "REQUISICAO"})

    def test_reanalisar_enquanto_na_fila_nao_duplica_o_trabalho(self):
        token = self.login()
        liberar = threading.Event()
        original = modulo_fila.analisar_processo
        chamadas = []

        def conta_e_segura(fabrica, armazem, id_, *resto):
            chamadas.append(id_)
            liberar.wait(10)
            return original(fabrica, armazem, id_, *resto)

        with mock.patch.object(modulo_fila, "analisar_processo", conta_e_segura):
            id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
            r = self.client.post(f"/api/processos/{id_}/reanalisar", headers=self.cabecalho(token))
            self.assertEqual(r.json()["status"], "PENDENTE")
            liberar.set()
            self.esperar(token, id_)
        self.assertEqual(len(chamadas), 1)


class TestReivindicacaoERecuperacao(BaseApi):
    def test_so_um_worker_analisa_o_mesmo_processo(self):
        token = self.login()
        id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]  # já CONCLUIDO
        antes = self.client.get(f"/api/processos/{id_}", headers=self.cabecalho(token)).json()
        with mock.patch("backend.pipeline.processar_pdf") as leitor:
            analisar_processo(self.app.state.fabrica, self.app.state.armazem, id_)  # segundo worker chega atrasado
        leitor.assert_not_called()
        self.assertEqual(self.client.get(f"/api/processos/{id_}", headers=self.cabecalho(token)).json(), antes)

    def test_ao_subir_devolve_pendentes_e_analisando_para_a_fila(self):
        token = self.login()
        with mock.patch("backend.pipeline.processar_pdf", side_effect=AssertionError("não deveria rodar")):
            pass
        # primeiro "servidor": aceita os envios mas não chega a analisar (como se tivesse caído)
        with mock.patch.object(self.app.state.fila, "enfileirar", lambda id_: None):
            enviados = self.enviar(token, ("a.pdf", PDF_PAGO), ("b.pdf", PDF_REQUISICAO)).json()["processos"]
        ids = [p["id"] for p in enviados]
        with self.app.state.fabrica() as db:  # um deles estava no meio da leitura quando caiu
            db.get(Processo, ids[0]).status = "ANALISANDO"
            db.commit()

        # segundo "servidor" sobe sobre o mesmo banco, com fila de threads de verdade
        with TestClient(criar_app(configuracao(self.pasta, fila_sincrona=False))) as novo:
            token2 = self.login(cliente=novo)
            fases = {self.esperar(token2, id_, cliente=novo)["fase"] for id_ in ids}
        self.assertEqual(fases, {"QUITADO", "REQUISICAO"})


if __name__ == "__main__":
    unittest.main()
