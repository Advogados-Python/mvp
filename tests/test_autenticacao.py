"""autenticacao/: login, tokens, trocar a senha e o limite de tentativas."""

import time
import unittest

import jwt

from backend.autenticacao import funcoes
from backend.autenticacao.classes import LimitadorLogin
from backend.usuarios.modelos import Usuario
from tests.apoio_backend import ADMIN, SENHA, BaseApi


class TestLogin(BaseApi):
    def test_login_devolve_token_e_usuario_sem_hash(self):
        resposta = self.client.post("/api/auth/login", data={"username": ADMIN, "password": SENHA})
        corpo = resposta.json()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(corpo["token_type"], "bearer")
        self.assertEqual(corpo["usuario"]["email"], ADMIN)
        self.assertTrue(corpo["usuario"]["admin"])
        self.assertNotIn("hash", str(corpo).lower())

    def test_email_e_case_insensitive(self):
        self.assertTrue(self.login("ADMIN@Teste.COM"))

    def test_senha_errada_e_email_inexistente_dao_a_mesma_resposta(self):
        errada = self.client.post("/api/auth/login", data={"username": ADMIN, "password": "errada-errada"})
        inexistente = self.client.post("/api/auth/login", data={"username": "ninguem@teste.com", "password": SENHA})
        self.assertEqual((errada.status_code, inexistente.status_code), (401, 401))
        self.assertEqual(errada.json(), inexistente.json())

    def test_conta_desativada_nao_entra(self):
        admin = self.login()
        self.criar_usuario("inativo@teste.com", token_admin=admin)
        alvo = next(u["id"] for u in self.client.get("/api/usuarios", headers=self.cabecalho(admin)).json() if u["email"] == "inativo@teste.com")
        self.client.patch(f"/api/usuarios/{alvo}", headers=self.cabecalho(admin), json={"ativo": False})
        resposta = self.client.post("/api/auth/login", data={"username": "inativo@teste.com", "password": SENHA})
        self.assertEqual(resposta.status_code, 401)

    def test_bloqueia_apos_tres_falhas_mesmo_com_a_senha_certa(self):
        for _ in range(3):
            self.client.post("/api/auth/login", data={"username": ADMIN, "password": "errada-errada"})
        resposta = self.client.post("/api/auth/login", data={"username": ADMIN, "password": SENHA})
        self.assertEqual(resposta.status_code, 429)
        self.assertIn("Retry-After", resposta.headers)

    def test_login_certo_zera_o_contador(self):
        for _ in range(2):
            self.client.post("/api/auth/login", data={"username": ADMIN, "password": "errada-errada"})
        self.login()
        for _ in range(2):
            self.client.post("/api/auth/login", data={"username": ADMIN, "password": "errada-errada"})
        self.assertEqual(self.client.post("/api/auth/login", data={"username": ADMIN, "password": SENHA}).status_code, 200)


class TestToken(BaseApi):
    def _usuario(self):
        with self.app.state.fabrica() as db:
            return db.query(Usuario).first()

    def test_rotas_protegidas_exigem_login(self):
        for metodo, caminho in (("get", "/api/auth/eu"), ("get", "/api/processos"), ("post", "/api/processos"),
                                ("get", "/api/usuarios"), ("get", "/api/processos/" + "0" * 32)):
            resposta = getattr(self.client, metodo)(caminho)
            self.assertEqual(resposta.status_code, 401, caminho)
            self.assertEqual(resposta.headers["www-authenticate"], "Bearer")

    def test_eu_com_token(self):
        self.assertEqual(self.client.get("/api/auth/eu", headers=self.cabecalho(self.login())).json()["email"], ADMIN)

    def test_token_adulterado_ou_de_outro_segredo_e_recusado(self):
        token = self.login()
        de_outro_segredo = jwt.encode({"sub": "1", "tipo": "acesso"}, "outro" * 10, algorithm="HS256")
        for ruim in (token[:-3] + "abc", "lixo", de_outro_segredo):
            self.assertEqual(self.client.get("/api/auth/eu", headers=self.cabecalho(ruim)).status_code, 401)

    def test_token_expirado_e_recusado(self):
        expirado, _ = funcoes.criar_token_acesso(self._usuario(), self.app.state.segredo, -1)
        self.assertEqual(self.client.get("/api/auth/eu", headers=self.cabecalho(expirado)).status_code, 401)

    def test_token_de_pdf_nao_serve_como_login(self):
        link, _ = funcoes.criar_link_pdf(self._usuario(), "0" * 32, self.app.state.segredo, 60)
        self.assertEqual(self.client.get("/api/auth/eu", headers=self.cabecalho(link)).status_code, 401)

    def test_trocar_a_senha_derruba_o_login_antigo(self):
        antigo = self.login()
        resposta = self.client.post("/api/auth/senha", headers=self.cabecalho(antigo),
                                    json={"senha_atual": SENHA, "nova_senha": "outra-senha-forte-1"})
        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/eu", headers=self.cabecalho(antigo)).status_code, 401)
        self.assertTrue(self.login(senha="outra-senha-forte-1"))

    def test_trocar_a_senha_exige_a_senha_atual(self):
        resposta = self.client.post("/api/auth/senha", headers=self.cabecalho(self.login()),
                                    json={"senha_atual": "nao-e-essa", "nova_senha": "outra-senha-forte-1"})
        self.assertEqual(resposta.status_code, 400)


class TestFuncoes(unittest.TestCase):
    def test_hash_confere_e_nao_guarda_a_senha(self):
        h = funcoes.gerar_hash("minha-senha-longa")
        self.assertTrue(funcoes.conferir_senha("minha-senha-longa", h))
        self.assertFalse(funcoes.conferir_senha("outra", h))
        self.assertNotIn("minha-senha", h)

    def test_hash_corrompido_nega_em_vez_de_quebrar(self):
        self.assertFalse(funcoes.conferir_senha("x", "isto-nao-e-um-hash"))
        self.assertFalse(funcoes.conferir_senha("x", None))


class TestLimitador(unittest.TestCase):
    def test_bloqueia_na_n_esima_falha_e_libera_apos_a_janela(self):
        limitador = LimitadorLogin(max_tentativas=2, janela_segundos=1)
        self.assertEqual(limitador.segundos_de_bloqueio("a"), 0)
        limitador.registrar_falha("a")
        self.assertEqual(limitador.segundos_de_bloqueio("a"), 0)
        limitador.registrar_falha("a")
        self.assertGreaterEqual(limitador.segundos_de_bloqueio("a"), 1)
        self.assertEqual(limitador.segundos_de_bloqueio("b"), 0)  # outra chave não é afetada
        time.sleep(1.1)
        self.assertEqual(limitador.segundos_de_bloqueio("a"), 0)

    def test_limpar_zera(self):
        limitador = LimitadorLogin(max_tentativas=1, janela_segundos=60)
        limitador.registrar_falha("a")
        limitador.limpar("a")
        self.assertEqual(limitador.segundos_de_bloqueio("a"), 0)


if __name__ == "__main__":
    unittest.main()
