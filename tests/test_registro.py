"""O Registre-se da tela de login: conta nasce inativa, OAB validada e normalizada, liberação pelo administrador."""

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backend.main import criar_app
from backend.userauths import cli
from backend.userauths.logic import adicionar_colunas_novas, gerar_hash
from backend.userauths.models import LimitadorLogin, Usuario
from backend.userauths.schemas import normalizar_oab
from tests.apoio_backend import ADMIN, SENHA, URL_BANCO_TESTE, BaseApi, configuracao

NOVO = {"nome": "Ana Maria Souza", "email": "Ana@Exemplo.com", "senha": "senha-da-ana-123", "oab": "123.456/sp"}


class TestNormalizarOab(unittest.TestCase):
    def test_aceita_uf_antes_ou_depois_com_pontuacao_e_letra_suplementar(self):
        casos = {
            "SP123456": "SP123456", "123456/SP": "SP123456", "123.456/sp": "SP123456", "sp-123456": "SP123456",
            " go 12345 ": "GO12345", "12345A/RJ": "RJ12345A", "df1": "DF1",
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(normalizar_oab(entrada), esperado)

    def test_recusa_formato_e_uf_inexistente(self):
        for entrada in ("", "123456", "SP", "SP1234567", "S123456", "SP12AB", "SP/12/34X5"):
            with self.subTest(entrada=entrada), self.assertRaisesRegex(ValueError, "Formato inválido"):
                normalizar_oab(entrada)
        with self.assertRaisesRegex(ValueError, "'XX' não existe"):
            normalizar_oab("XX12345")


class TestRegistrar(BaseApi):
    def registrar(self, **mudancas):
        return self.client.post("/api/auth/registrar", json={**NOVO, **mudancas})

    def usuario(self, email) -> Usuario:
        with self.app.state.fabrica() as db:
            return db.query(Usuario).filter_by(email=email).one()

    def test_cria_conta_inativa_com_oab_normalizada_e_sem_admin(self):
        resposta = self.registrar(admin=True)  # campo extra é ignorado: ninguém se registra como administrador
        self.assertEqual(resposta.status_code, 202, resposta.text)
        self.assertIn("Cadastro recebido", resposta.json()["mensagem"])
        usuario = self.usuario("ana@exemplo.com")
        self.assertEqual((usuario.nome, usuario.oab, usuario.ativo, usuario.admin), ("Ana Maria Souza", "SP123456", False, False))
        self.assertNotIn(NOVO["senha"], usuario.senha_hash)

    def test_nao_entra_ate_ser_liberada_e_depois_entra(self):
        self.registrar()
        bloqueado = self.client.post("/api/auth/login", data={"username": "ana@exemplo.com", "password": NOVO["senha"]})
        self.assertEqual(bloqueado.status_code, 403)
        self.assertIn("Aguarde a aprovação", bloqueado.json()["detail"])

        admin = self.cabecalho(self.login())
        lista = self.client.get("/api/usuarios", headers=admin).json()
        pendente = next(u for u in lista if u["email"] == "ana@exemplo.com")
        self.assertEqual((pendente["ativo"], pendente["oab"]), (False, "SP123456"))
        self.client.patch(f"/api/usuarios/{pendente['id']}", headers=admin, json={"ativo": True})

        token = self.login("ana@exemplo.com", NOVO["senha"])
        eu = self.client.get("/api/auth/eu", headers=self.cabecalho(token)).json()
        self.assertEqual((eu["oab"], eu["admin"]), ("SP123456", False))

    def test_email_ja_cadastrado_responde_igual_e_nao_mexe_na_conta(self):
        novo = self.registrar()
        repetido = self.registrar(email=ADMIN, nome="Intruso", senha="outra-senha-qualquer", oab="GO1")
        self.assertEqual((repetido.status_code, repetido.json()), (novo.status_code, novo.json()))
        admin = self.usuario(ADMIN)
        self.assertEqual((admin.nome, admin.ativo, admin.admin, admin.oab), ("Administrador", True, True, None))
        self.login(ADMIN, SENHA)  # a senha continua a mesma

    def test_oab_invalida_e_422_em_portugues_e_nao_cria_nada(self):
        formato = self.registrar(oab="12345")
        uf = self.registrar(oab="XX12345")
        self.assertEqual((formato.status_code, uf.status_code), (422, 422))
        self.assertEqual(formato.json()["detail"][0]["loc"], ["body", "oab"])
        self.assertIn("Use UF + número", formato.json()["detail"][0]["msg"])
        self.assertIn("'XX' não existe", uf.json()["detail"][0]["msg"])
        with self.app.state.fabrica() as db:
            self.assertEqual(db.query(Usuario).filter_by(email="ana@exemplo.com").count(), 0)

    def test_senha_curta_e_campos_faltando_nao_ecoam_a_senha(self):
        curta = self.registrar(senha="curta-1")
        self.assertEqual(curta.status_code, 422)
        self.assertNotIn("curta-1", curta.text)
        faltando = self.client.post("/api/auth/registrar", json={"email": "x@y.com"})
        campos = {e["loc"][-1] for e in faltando.json()["detail"]}
        self.assertEqual(campos, {"nome", "senha", "oab"})

    def test_limita_cadastros_por_ip(self):
        self.app.state.limitador_registro = LimitadorLogin(max_tentativas=2, janela_segundos=3600)
        self.assertEqual(self.registrar(email="a1@teste.com").status_code, 202)
        self.assertEqual(self.registrar(email="a2@teste.com").status_code, 202)
        terceiro = self.registrar(email="a3@teste.com")
        self.assertEqual(terceiro.status_code, 429)
        self.assertIn("Retry-After", terceiro.headers)
        with self.app.state.fabrica() as db:
            self.assertEqual(db.query(Usuario).filter_by(email="a3@teste.com").count(), 0)

    def test_cli_lista_mostra_a_oab_e_ativa_a_conta(self):
        self.registrar()
        config = configuracao(self.pasta)
        saida = io.StringIO()
        with mock.patch("backend.userauths.cli.obter_configuracoes", return_value=config), redirect_stdout(saida):
            cli.main(["listar"])
            cli.main(["ativar-usuario", "--email", "ANA@exemplo.com"])
            cli.main(["ativar-usuario", "--email", "ana@exemplo.com"])
        texto = saida.getvalue()
        self.assertIn("SP123456", texto)
        self.assertIn("INATIVO (aguarda liberação)", texto)
        self.assertIn("Conta liberada: ana@exemplo.com", texto)
        self.assertIn("já estava ativo", texto)
        self.login("ana@exemplo.com", NOVO["senha"])


@unittest.skipIf(URL_BANCO_TESTE, "monta um SQLite com a tabela antiga")
class TestMigracaoDaColunaOab(unittest.TestCase):
    """O banco do Railway (e o SQLite local) foram criados sem a coluna `oab`: a API precisa subir neles e acrescentá-la."""

    def test_api_sobe_num_banco_antigo_e_acrescenta_a_coluna_sem_perder_usuarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            conexao = sqlite3.connect(pasta / "ribeiro.db")
            conexao.execute(
                "CREATE TABLE usuarios (id INTEGER PRIMARY KEY, email VARCHAR(255) UNIQUE, nome VARCHAR(120), "
                "senha_hash VARCHAR(255), ativo BOOLEAN, admin BOOLEAN, criado_em DATETIME)"
            )
            conexao.execute(
                "INSERT INTO usuarios (email, nome, senha_hash, ativo, admin, criado_em) VALUES (?, ?, ?, 1, 1, '2026-11-01 10:00:00')",
                ("antigo@teste.com", "Antigo", gerar_hash(SENHA)),
            )
            conexao.commit()
            conexao.close()

            app = criar_app(configuracao(pasta, admin_email=None, admin_senha=None))
            with TestClient(app) as cliente:
                colunas = {c["name"] for c in inspect(app.state.motor).get_columns("usuarios")}
                self.assertIn("oab", colunas)
                resposta = cliente.post("/api/auth/login", data={"username": "antigo@teste.com", "password": SENHA})
                self.assertEqual(resposta.status_code, 200, resposta.text)
                self.assertIsNone(resposta.json()["usuario"]["oab"])
                adicionar_colunas_novas(app.state.motor)  # repetir não quebra
            app.state.motor.dispose()


if __name__ == "__main__":
    unittest.main()
