"""usuarios/: administração e o administrador inicial."""

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from backend.userauths import cli
from backend.userauths.logic import criar_usuario
from backend.userauths.models import ErroEmailJaCadastrado
from backend.userauths.schemas import UsuarioCriar
from tests.apoio_backend import ADMIN, SENHA, BaseApi, configuracao


class TestAdministracao(BaseApi):
    def test_admin_cria_e_lista(self):
        token = self.login()
        self.criar_usuario("ana@teste.com", "Ana", token_admin=token)
        emails = [u["email"] for u in self.client.get("/api/usuarios", headers=self.cabecalho(token)).json()]
        self.assertEqual(sorted(emails), [ADMIN, "ana@teste.com"])

    def test_nunca_devolve_o_hash_da_senha(self):
        corpo = self.client.get("/api/usuarios", headers=self.cabecalho(self.login())).text
        self.assertNotIn("argon2", corpo)
        self.assertNotIn("senha_hash", corpo)

    def test_usuario_comum_nao_administra(self):
        h = self.cabecalho(self.criar_usuario("comum@teste.com"))
        self.assertEqual(self.client.get("/api/usuarios", headers=h).status_code, 403)
        novo = {"email": "x@teste.com", "nome": "X", "senha": SENHA}
        self.assertEqual(self.client.post("/api/usuarios", headers=h, json=novo).status_code, 403)

    def test_email_duplicado_senha_curta_e_email_invalido(self):
        h = self.cabecalho(self.login())
        self.assertEqual(self.client.post("/api/usuarios", headers=h, json={"email": ADMIN.upper(), "nome": "O", "senha": SENHA}).status_code, 409)
        self.assertEqual(self.client.post("/api/usuarios", headers=h, json={"email": "novo@teste.com", "nome": "N", "senha": "curta"}).status_code, 422)
        self.assertEqual(self.client.post("/api/usuarios", headers=h, json={"email": "sem-arroba", "nome": "N", "senha": SENHA}).status_code, 422)

    def test_admin_nao_pode_se_desativar_nem_rebaixar(self):
        token = self.login()
        meu_id = self.client.get("/api/auth/eu", headers=self.cabecalho(token)).json()["id"]
        for corpo in ({"ativo": False}, {"admin": False}):
            self.assertEqual(self.client.patch(f"/api/usuarios/{meu_id}", headers=self.cabecalho(token), json=corpo).status_code, 400)

    def test_desativar_derruba_o_login_ativo(self):
        admin = self.login()
        comum = self.criar_usuario("comum@teste.com", token_admin=admin)
        comum_id = self.client.get("/api/auth/eu", headers=self.cabecalho(comum)).json()["id"]
        self.client.patch(f"/api/usuarios/{comum_id}", headers=self.cabecalho(admin), json={"ativo": False})
        self.assertEqual(self.client.get("/api/auth/eu", headers=self.cabecalho(comum)).status_code, 401)

    def test_admin_redefine_a_senha_e_o_login_antigo_cai(self):
        admin = self.login()
        comum = self.criar_usuario("comum@teste.com", token_admin=admin)
        comum_id = self.client.get("/api/auth/eu", headers=self.cabecalho(comum)).json()["id"]
        self.client.patch(f"/api/usuarios/{comum_id}", headers=self.cabecalho(admin), json={"nova_senha": "senha-nova-forte-9"})
        self.assertEqual(self.client.get("/api/auth/eu", headers=self.cabecalho(comum)).status_code, 401)
        self.assertTrue(self.login("comum@teste.com", "senha-nova-forte-9"))

    def test_atualizar_usuario_inexistente_e_404(self):
        r = self.client.patch("/api/usuarios/99999", headers=self.cabecalho(self.login()), json={"nome": "X"})
        self.assertEqual(r.status_code, 404)


class TestFuncoes(BaseApi):
    def test_criar_usuario_levanta_erro_de_email_duplicado(self):
        with self.app.state.fabrica() as db:
            with self.assertRaises(ErroEmailJaCadastrado):
                criar_usuario(db, UsuarioCriar(email=ADMIN, nome="Outro", senha=SENHA))

    def test_administrador_inicial_nao_duplica_ao_reiniciar(self):
        from fastapi.testclient import TestClient
        from backend.main import criar_app
        from tests.apoio_backend import configuracao
        with TestClient(criar_app(configuracao(self.pasta))) as segundo:  # segunda subida sobre o mesmo banco
            usuarios = segundo.get("/api/usuarios", headers=self.cabecalho(self.login(cliente=segundo))).json()
        self.assertEqual(len(usuarios), 1)


class TestSenhaNaoVaza(BaseApi):
    """Uma senha recusada por ser curta não pode voltar no corpo da resposta nem aparecer no terminal."""

    def test_422_de_senha_curta_nao_ecoa_a_senha_e_vem_em_portugues(self):
        h = self.cabecalho(self.login())
        r = self.client.post("/api/usuarios", headers=h, json={"email": "n@teste.com", "nome": "N", "senha": "Senha159@"})
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("Senha159@", r.text)
        detalhe = r.json()["detail"][0]
        self.assertEqual(detalhe["loc"][-1], "senha")
        self.assertIn("pelo menos 10 caracteres", detalhe["msg"])
        self.assertEqual(set(detalhe), {"type", "loc", "msg"})  # nada de `input`, `ctx` ou `url`

    def test_trocar_para_senha_curta_tambem_nao_ecoa(self):
        r = self.client.post("/api/auth/senha", headers=self.cabecalho(self.login()),
                             json={"senha_atual": SENHA, "nova_senha": "Curta123@"})
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("Curta123@", r.text)

    def test_campo_obrigatorio_em_portugues(self):
        r = self.client.post("/api/usuarios", headers=self.cabecalho(self.login()), json={"nome": "N"})
        self.assertEqual(r.status_code, 422)
        self.assertTrue(all(e["msg"] == "Campo obrigatório." for e in r.json()["detail"]))


class TestCli(BaseApi):
    def test_pedir_senha_explica_e_pergunta_de_novo_sem_imprimir_a_senha(self):
        saida = io.StringIO()
        with mock.patch("getpass.getpass", side_effect=["Senha159@", "uma-senha-longa-1", "uma-senha-longa-1"]), redirect_stdout(saida):
            senha = cli._pedir_senha()
        self.assertEqual(senha, "uma-senha-longa-1")
        texto = saida.getvalue()
        self.assertIn("9 caracteres; o mínimo é 10", texto)
        self.assertNotIn("Senha159@", texto)

    def test_pedir_senha_repete_quando_as_duas_digitacoes_diferem(self):
        saida = io.StringIO()
        digitadas = ["primeira-senha-1", "outra-diferente-2", "primeira-senha-1", "primeira-senha-1"]
        with mock.patch("getpass.getpass", side_effect=digitadas), redirect_stdout(saida):
            self.assertEqual(cli._pedir_senha(), "primeira-senha-1")
        self.assertIn("não conferem", saida.getvalue())

    def test_criar_usuario_com_email_invalido_da_mensagem_clara(self):
        config = configuracao(self.pasta)
        with mock.patch("backend.userauths.cli.obter_configuracoes", return_value=config), \
                mock.patch("getpass.getpass", return_value="uma-senha-longa-1"):
            with self.assertRaises(SystemExit) as saida:
                cli.main(["criar-usuario", "--email", "sem-arroba", "--nome", "Ana"])
        self.assertIn("email: Formato inválido.", str(saida.exception))
        self.assertNotIn("uma-senha-longa-1", str(saida.exception))


if __name__ == "__main__":
    unittest.main()
