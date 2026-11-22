"""O backend são as seis fases de leitura + userauths: a estrutura, os códigos de etapa e a API de cada fase."""

import unittest
from pathlib import Path

import backend
from backend.pipeline import ETAPAS
from backend.receive.models import STAGE as RECEBIDO
from tests.apoio_backend import PDF_PAGO, PDF_PROTEGIDO, PDF_REQUISICAO, BaseApi, gerar_pdf

RAIZ = Path(backend.__file__).parent
FASES = ["receive", "extract", "identify", "search", "validate", "finalize"]  # na ordem em que rodam
ARQUIVOS_PADRAO = {"__init__.py", "models.py", "logic.py", "schemas.py", "api.py"}
EXTRAS = {"receive": {"store.py"}, "identify": {"rules.py"}, "search": {"terms.py"}, "validate": {"ladder.py"}}


class TestEstrutura(unittest.TestCase):
    def test_o_backend_so_tem_as_seis_fases_e_userauths(self):
        pastas = {p.name for p in RAIZ.iterdir() if p.is_dir() and p.name != "__pycache__"}
        self.assertEqual(pastas, {*FASES, "userauths"})
        self.assertEqual({p.name for p in RAIZ.iterdir() if p.is_file()}, {"__init__.py", "main.py", "config.py", "db.py", "pipeline.py", "requirements.txt"})

    def test_cada_fase_tem_as_suas_classes_a_sua_logica_e_a_sua_api(self):
        for fase in FASES:
            arquivos = {p.name for p in (RAIZ / fase).iterdir() if p.suffix == ".py"}
            self.assertEqual(arquivos, ARQUIVOS_PADRAO | EXTRAS.get(fase, set()), fase)
        self.assertEqual({p.name for p in (RAIZ / "userauths").iterdir() if p.suffix == ".py"}, {"__init__.py", "models.py", "schemas.py", "logic.py", "deps.py", "api.py", "cli.py"})

    def test_os_codigos_de_andamento_vem_das_fases_na_ordem(self):
        self.assertEqual(ETAPAS, ("LENDO_PDF", "IDENTIFICANDO", "BUSCANDO_TERMOS", "VALIDANDO", "FINALIZANDO"))
        self.assertEqual(RECEBIDO, "RECEBIDO")  # o recebimento é o status PENDENTE, não uma etapa


class TestApiDeCadaFase(BaseApi):
    def get(self, token, caminho):
        return self.client.get(caminho, headers=self.cabecalho(token) if token else {})

    def enviar_um(self, token, nome, pdf):
        return self.enviar(token, (nome, pdf)).json()["processos"][0]["id"]

    def test_cada_fase_tem_a_sua_rota_por_processo(self):
        caminhos = self.app.openapi()["paths"]
        for fase in FASES:
            self.assertIn(f"/api/processos/{{processo_id}}/{fase}", caminhos, fase)

    def test_o_que_cada_fase_produziu_para_um_processo(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_REQUISICAO)
        detalhe = self.get(token, f"/api/processos/{id_}").json()
        base = f"/api/processos/{id_}/%s"

        recebido = self.get(token, base % "receive").json()
        self.assertEqual((recebido["arquivo"], recebido["tamanho_bytes"], recebido["status"]), ("p.pdf", detalhe["tamanho_bytes"], "CONCLUIDO"))

        extracao = self.get(token, base % "extract").json()
        self.assertEqual((extracao["total_paginas"], extracao["paginas_lidas"], extracao["paginas_sem_texto"], extracao["pouco_legivel"]), (2, 2, 0, False))

        identificacao = self.get(token, base % "identify").json()
        self.assertEqual((identificacao["numero_processo"], identificacao["tribunal"]), ("1234567-89.2025.4.01.3500", "TRF1"))

        busca = self.get(token, base % "search").json()
        self.assertEqual((busca["total_evidencias"], busca["por_fase"]), (1, {"REQUISICAO": 1}))
        self.assertEqual(busca["evidencias"], detalhe["evidencias"])  # a mesma lista que o processo mostra

        validacao = self.get(token, base % "validate").json()
        self.assertEqual((validacao["fase"], validacao["divida_paga"], validacao["evidencias_que_contam"]), ("REQUISICAO", "NAO", 1))
        self.assertEqual(validacao["evidencia_principal"], detalhe["evidencia_principal"])
        self.assertEqual(validacao["avisos"], detalhe["avisos"])

        final = self.get(token, base % "finalize").json()
        self.assertEqual((final["status"], final["fase"], final["resultado_gravado"]), ("CONCLUIDO", "REQUISICAO", True))
        self.assertIsNotNone(final["concluido_em"])

    def test_pouco_legivel_vem_do_mesmo_corte_do_aviso(self):
        token = self.login()
        id_ = self.enviar_um(token, "scan.pdf", gerar_pdf("Numero: 1234567-89.2025.4.01.3500", "", "", ""))  # 3 de 4 páginas sem texto
        extracao = self.get(token, f"/api/processos/{id_}/extract").json()
        self.assertEqual((extracao["paginas_sem_texto"], extracao["percentual_sem_texto"], extracao["pouco_legivel"]), (3, 0.75, True))

    def test_receber_e_finalizar_valem_em_qualquer_status_as_demais_exigem_analise_concluida(self):
        token = self.login()
        falhou = self.enviar_um(token, "protegido.pdf", PDF_PROTEGIDO)
        base = f"/api/processos/{falhou}/%s"
        self.assertEqual(self.get(token, base % "receive").json()["status"], "FALHOU")
        final = self.get(token, base % "finalize").json()
        self.assertEqual((final["status"], final["resultado_gravado"], "protegido" in final["erro"]), ("FALHOU", False, True))
        for fase in ("extract", "identify", "search", "validate"):
            resposta = self.get(token, base % fase)
            self.assertEqual(resposta.status_code, 409, fase)
            self.assertIn("falhou", resposta.json()["detail"])

    def test_processo_de_outra_pessoa_ou_inexistente_e_404_em_todas_as_fases(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_PAGO)
        outro = self.criar_usuario("outro@teste.com")
        for fase in FASES:
            with self.subTest(fase=fase):
                self.assertEqual(self.get(None, f"/api/processos/{id_}/{fase}").status_code, 401)
                self.assertEqual(self.get(outro, f"/api/processos/{id_}/{fase}").status_code, 404)
                self.assertEqual(self.get(token, f"/api/processos/{'0' * 32}/{fase}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
