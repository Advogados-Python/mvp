"""processos/: upload, isolamento entre usuários, link assinado do PDF, apagar, reanalisar, filtros."""

import unittest
from unittest import mock

from backend.userauths import logic as autenticacao
from backend.userauths.models import Usuario
from tests.apoio_backend import PDF_PAGO, PDF_PROTEGIDO, PDF_REQUISICAO, BaseApi


class TestEnvioEConsulta(BaseApi):
    def test_upload_analisa_e_devolve_resumo(self):
        token = self.login()
        resposta = self.enviar(token, ("processo.pdf", PDF_PAGO))
        self.assertEqual(resposta.status_code, 202)
        corpo = resposta.json()
        self.assertEqual(corpo["falhas"], [])
        (resumo,) = corpo["processos"]
        self.assertEqual(resumo["arquivo"], "processo.pdf")
        self.assertEqual(resumo["status"], "CONCLUIDO")  # análise síncrona neste teste
        self.assertEqual(resumo["numero_processo"], "1234567-89.2025.4.01.3500")
        self.assertEqual(resumo["fase"], "QUITADO")
        self.assertEqual(resumo["divida_paga"], "SIM")
        self.assertEqual(resumo["evidencia_principal"]["pagina"], 2)
        self.assertGreaterEqual(resumo["evidencias_que_contam"], 1)
        self.assertNotIn("evidencias", resumo)  # o resumo é leve

    def test_detalhe_traz_evidencias_com_campo_conta(self):
        token = self.login()
        id_ = self.enviar(token, ("p.pdf", PDF_REQUISICAO)).json()["processos"][0]["id"]
        detalhe = self.client.get(f"/api/processos/{id_}", headers=self.cabecalho(token)).json()
        self.assertEqual((detalhe["fase"], detalhe["divida_paga"]), ("REQUISICAO", "NAO"))
        self.assertTrue(detalhe["evidencias"])
        self.assertTrue(all("conta" in ev for ev in detalhe["evidencias"]))

    def test_datas_saem_em_utc_com_fuso(self):
        token = self.login()
        resumo = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]
        self.assertTrue(resumo["criado_em"].endswith(("Z", "+00:00")), resumo["criado_em"])

    def test_listagem_pagina_e_filtra_por_status(self):
        token = self.login()
        h = self.cabecalho(token)
        self.enviar(token, ("a.pdf", PDF_PAGO), ("b.pdf", PDF_REQUISICAO))
        lista = self.client.get("/api/processos", headers=h).json()
        self.assertEqual((lista["total"], len(lista["processos"])), (2, 2))
        self.assertNotIn("evidencias", lista["processos"][0])
        self.assertEqual(len(self.client.get("/api/processos?limite=1", headers=h).json()["processos"]), 1)
        self.assertEqual(self.client.get("/api/processos?status=FALHOU", headers=h).json()["total"], 0)
        self.assertEqual(self.client.get("/api/processos?status=CONCLUIDO", headers=h).json()["total"], 2)
        self.assertEqual(self.client.get("/api/processos?status=NADA", headers=h).status_code, 422)

    def test_reenvio_do_mesmo_pdf_nao_duplica(self):
        token = self.login()
        self.enviar(token, ("a.pdf", PDF_PAGO))
        self.enviar(token, ("copia.pdf", PDF_PAGO))
        lista = self.client.get("/api/processos", headers=self.cabecalho(token)).json()
        self.assertEqual(lista["total"], 1)
        self.assertEqual(lista["processos"][0]["arquivo"], "copia.pdf")  # fica com o nome mais recente

    def test_lote_com_arquivo_ruim_nao_derruba_os_bons(self):
        token = self.login()
        corpo = self.enviar(token, ("bom.pdf", PDF_PAGO), ("texto.pdf", b"isto nao e um pdf"), ("vazio.pdf", b"")).json()
        self.assertEqual([p["arquivo"] for p in corpo["processos"]], ["bom.pdf"])
        erros = {f["arquivo"]: f["erro"] for f in corpo["falhas"]}
        self.assertIn("não é um PDF", erros["texto.pdf"])
        self.assertIn("vazio", erros["vazio.pdf"])

    def test_arquivo_acima_do_limite_e_recusado_e_nada_fica_no_disco(self):
        token = self.login()
        self.app.state.armazem.max_bytes = 100
        corpo = self.enviar(token, ("grande.pdf", PDF_PAGO)).json()
        self.assertEqual(corpo["processos"], [])
        self.assertIn("limite", corpo["falhas"][0]["erro"])
        self.assertEqual(list(self.app.state.armazem.pasta.glob("*")), [])

    def test_mais_arquivos_que_o_limite_e_413(self):
        token = self.login()
        r = self.enviar(token, *[(f"{i}.pdf", PDF_PAGO) for i in range(21)])
        self.assertEqual(r.status_code, 413)

    def test_pdf_protegido_por_senha_vira_falha_com_motivo(self):
        token = self.login()
        resumo = self.enviar(token, ("senha.pdf", PDF_PROTEGIDO)).json()["processos"][0]
        self.assertEqual(resumo["status"], "FALHOU")
        self.assertIn("senha", resumo["erro"])
        self.assertIsNone(resumo["fase"])

    def test_nome_do_arquivo_nao_escapa_da_pasta(self):
        token = self.login()
        resumo = self.enviar(token, ("../../etc/passwd.pdf", PDF_PAGO)).json()["processos"][0]
        self.assertEqual(resumo["arquivo"], "passwd.pdf")

    def test_id_fora_do_formato_ou_inexistente_e_404(self):
        h = self.cabecalho(self.login())
        for id_ in ("nao-existe", "0" * 32, "..%2F..%2Fsegredo", "A" * 32):
            self.assertEqual(self.client.get(f"/api/processos/{id_}", headers=h).status_code, 404, id_)


class TestIsolamento(BaseApi):
    def test_um_usuario_nao_enxerga_nem_mexe_nos_processos_do_outro(self):
        ana = self.criar_usuario("ana@teste.com")
        bia = self.criar_usuario("bia@teste.com")
        id_ = self.enviar(ana, ("ana.pdf", PDF_PAGO)).json()["processos"][0]["id"]
        h = self.cabecalho(bia)
        self.assertEqual(self.client.get("/api/processos", headers=h).json()["total"], 0)
        self.assertEqual(self.client.get(f"/api/processos/{id_}", headers=h).status_code, 404)
        self.assertEqual(self.client.post(f"/api/processos/{id_}/pdf-link", headers=h).status_code, 404)
        self.assertEqual(self.client.post(f"/api/processos/{id_}/reanalisar", headers=h).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/processos/{id_}", headers=h).status_code, 404)
        self.assertEqual(self.client.get(f"/api/processos/{id_}/pdf", headers=h).status_code, 404)
        # ... e o administrador também só vê os próprios
        self.assertEqual(self.client.get("/api/processos", headers=self.cabecalho(self.login())).json()["total"], 0)
        self.assertEqual(self.client.get(f"/api/processos/{id_}", headers=self.cabecalho(self.login())).status_code, 404)

    def test_o_mesmo_pdf_em_duas_contas_vira_dois_processos(self):
        ana, bia = self.criar_usuario("ana@teste.com"), self.criar_usuario("bia@teste.com")
        id_ana = self.enviar(ana, ("a.pdf", PDF_PAGO)).json()["processos"][0]["id"]
        id_bia = self.enviar(bia, ("a.pdf", PDF_PAGO)).json()["processos"][0]["id"]
        self.assertNotEqual(id_ana, id_bia)
        self.client.delete(f"/api/processos/{id_ana}", headers=self.cabecalho(ana))
        self.assertEqual(self.client.get(f"/api/processos/{id_bia}", headers=self.cabecalho(bia)).status_code, 200)


class TestPdf(BaseApi):
    def _processo(self):
        token = self.login()
        return token, self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]

    def test_pdf_com_login(self):
        token, id_ = self._processo()
        r = self.client.get(f"/api/processos/{id_}/pdf", headers=self.cabecalho(token))
        self.assertEqual((r.status_code, r.content), (200, PDF_PAGO))
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertTrue(r.headers["content-disposition"].startswith("inline"))
        self.assertIn("no-store", r.headers["cache-control"])

    def test_pdf_sem_login_nem_link_e_401(self):
        _token, id_ = self._processo()
        self.assertEqual(self.client.get(f"/api/processos/{id_}/pdf").status_code, 401)

    def test_link_assinado_abre_o_pdf_sem_cabecalho(self):
        token, id_ = self._processo()
        link = self.client.post(f"/api/processos/{id_}/pdf-link", headers=self.cabecalho(token)).json()
        self.assertTrue(link["url"].startswith(f"/api/processos/{id_}/pdf?assinatura="))
        r = self.client.get(link["url"])  # sem Authorization, como numa nova aba
        self.assertEqual((r.status_code, r.content), (200, PDF_PAGO))

    def test_link_de_um_processo_nao_abre_outro(self):
        token, id_ = self._processo()
        outro = self.enviar(token, ("o.pdf", PDF_REQUISICAO)).json()["processos"][0]["id"]
        link = self.client.post(f"/api/processos/{id_}/pdf-link", headers=self.cabecalho(token)).json()["url"]
        trocado = link.replace(id_, outro, 1)
        self.assertEqual(self.client.get(trocado).status_code, 401)

    def test_link_expirado_ou_adulterado_e_401(self):
        token, id_ = self._processo()
        self.app.state.config.link_pdf_segundos = -5
        expirado = self.client.post(f"/api/processos/{id_}/pdf-link", headers=self.cabecalho(token)).json()["url"]
        self.assertEqual(self.client.get(expirado).status_code, 401)
        self.assertEqual(self.client.get(f"/api/processos/{id_}/pdf?assinatura=lixo").status_code, 401)

    def test_link_morre_quando_o_usuario_e_desativado(self):
        admin = self.login()
        ana = self.criar_usuario("ana@teste.com", token_admin=admin)
        id_ = self.enviar(ana, ("a.pdf", PDF_PAGO)).json()["processos"][0]["id"]
        link = self.client.post(f"/api/processos/{id_}/pdf-link", headers=self.cabecalho(ana)).json()["url"]
        ana_id = self.client.get("/api/auth/eu", headers=self.cabecalho(ana)).json()["id"]
        self.client.patch(f"/api/usuarios/{ana_id}", headers=self.cabecalho(admin), json={"ativo": False})
        self.assertEqual(self.client.get(link).status_code, 401)

    def test_token_de_login_nao_vale_como_assinatura_de_pdf(self):
        token, id_ = self._processo()
        self.assertEqual(self.client.get(f"/api/processos/{id_}/pdf?assinatura={token}").status_code, 401)


class TestApagarEReanalisar(BaseApi):
    def test_excluir_remove_pdf_do_disco_e_o_registro(self):
        token = self.login()
        h = self.cabecalho(token)
        id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
        arquivo = self.app.state.armazem.caminho(id_)
        self.assertTrue(arquivo.is_file())
        self.assertEqual(self.client.delete(f"/api/processos/{id_}", headers=h).status_code, 204)
        self.assertFalse(arquivo.exists())
        self.assertEqual(self.client.get(f"/api/processos/{id_}", headers=h).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/processos/{id_}", headers=h).status_code, 404)

    def test_reanalisar_refaz_a_analise(self):
        token = self.login()
        id_ = self.enviar(token, ("p.pdf", PDF_PAGO)).json()["processos"][0]["id"]
        r = self.client.post(f"/api/processos/{id_}/reanalisar", headers=self.cabecalho(token))
        self.assertEqual(r.status_code, 202)
        self.assertEqual((r.json()["status"], r.json()["divida_paga"]), ("CONCLUIDO", "SIM"))

    def test_falha_inesperada_nao_vaza_detalhes_internos(self):
        token = self.login()
        with mock.patch("backend.pipeline.processar_pdf", side_effect=RuntimeError("caminho /etc/segredo-interno")):
            with self.assertLogs("ribeiro.analise", "ERROR"):  # o detalhe fica só no log do servidor
                resposta = self.enviar(token, ("p.pdf", PDF_PAGO))
        resumo = resposta.json()["processos"][0]
        self.assertEqual(resumo["status"], "FALHOU")
        self.assertNotIn("segredo-interno", resposta.text)

    def test_apagar_durante_a_analise_nao_quebra(self):
        from backend.pipeline import processar_pdf as original
        from backend.receive.models import Processo
        token = self.login()
        fabrica = self.app.state.fabrica

        def apaga_e_le(caminho, *resto):
            with fabrica() as db:
                db.delete(db.query(Processo).one())
                db.commit()
            return original(caminho, *resto)

        with mock.patch("backend.pipeline.processar_pdf", apaga_e_le):
            self.assertEqual(self.enviar(token, ("p.pdf", PDF_PAGO)).status_code, 202)
        self.assertEqual(self.client.get("/api/processos", headers=self.cabecalho(token)).json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
