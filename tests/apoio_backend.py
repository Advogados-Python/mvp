"""Apoio dos testes do backend: a API de verdade (banco, fila, rotas) sobre SQLite numa pasta temporária.

Para rodar a mesma suíte num Postgres de verdade:
    RIBEIRO_TESTE_BANCO_URL=postgresql://usuario:senha@localhost:5432/teste python -m unittest discover -s tests -t .
(as tabelas do banco informado são APAGADAS e recriadas a cada teste: use um banco só para testes)
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from backend.main import criar_app
from backend import db as banco
from backend.config import Configuracoes

URL_BANCO_TESTE = os.getenv("RIBEIRO_TESTE_BANCO_URL")
SENHA = "senha-de-teste-123"
ADMIN = "admin@teste.com"


def gerar_pdf(*textos_por_pagina, **criptografia) -> bytes:
    doc = pymupdf.open()
    for texto in textos_por_pagina:
        pagina = doc.new_page()
        if texto:
            pagina.insert_text((72, 72), texto)
    conteudo = doc.tobytes(**criptografia)
    doc.close()
    return conteudo


PDF_PAGO = gerar_pdf("Numero: 1234567-89.2025.4.01.3500", "Julgo extinta a execução pelo pagamento.")
PDF_REQUISICAO = gerar_pdf("Numero: 1234567-89.2025.4.01.3500", "Expeça-se ofício requisitório.")
PDF_PROTEGIDO = gerar_pdf("segredo", encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")


def configuracao(pasta: Path, **mudancas) -> Configuracoes:
    padrao = dict(
        pasta_dados=pasta, banco_url=URL_BANCO_TESTE, jwt_segredo="s" * 48, fila_sincrona=True,
        admin_email=ADMIN, admin_senha=SENHA, login_max_tentativas=3,
    )
    return Configuracoes(_env_file=None, **{**padrao, **mudancas})


class BaseApi(unittest.TestCase):
    """Sobe a API a cada teste. Por padrão a análise é síncrona (dentro da requisição); veja test_fila.py."""

    fila_sincrona = True

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        self.app = criar_app(configuracao(self.pasta, fila_sincrona=self.fila_sincrona))
        if URL_BANCO_TESTE:  # banco compartilhado: começa limpo
            banco.Base.metadata.drop_all(self.app.state.motor)
        self.client = TestClient(self.app)
        self.client.__enter__()  # roda o lifespan (create_all, administrador inicial, recuperação da fila)
        self.addCleanup(self.client.__exit__, None, None, None)

    # ---- atalhos
    def login(self, email=ADMIN, senha=SENHA, cliente=None) -> str:
        resposta = (cliente or self.client).post("/api/auth/login", data={"username": email, "password": senha})
        self.assertEqual(resposta.status_code, 200, resposta.text)
        return resposta.json()["access_token"]

    @staticmethod
    def cabecalho(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def criar_usuario(self, email, nome="Fulano", admin=False, token_admin=None) -> str:
        """Cria pelo endpoint de administração e devolve o token de login do novo usuário."""
        token_admin = token_admin or self.login()
        resposta = self.client.post(
            "/api/usuarios", headers=self.cabecalho(token_admin),
            json={"email": email, "nome": nome, "senha": SENHA, "admin": admin},
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return self.login(email)

    def enviar(self, token, *arquivos):
        """arquivos: tuplas (nome, bytes)."""
        return self.client.post(
            "/api/processos", headers=self.cabecalho(token),
            files=[("arquivos", (nome, conteudo, "application/pdf")) for nome, conteudo in arquivos],
        )

    def esperar(self, token, processo_id, status="CONCLUIDO", limite=15.0, cliente=None) -> dict:
        """Consulta até o processo chegar ao status (para a fila de threads de verdade)."""
        cliente = cliente or self.client
        fim = time.monotonic() + limite
        detalhe = {}
        while time.monotonic() < fim:
            detalhe = cliente.get(f"/api/processos/{processo_id}", headers=self.cabecalho(token)).json()
            if detalhe.get("status") == status:
                return detalhe
            time.sleep(0.05)
        self.fail(f"processo não chegou a {status} em {limite}s (último: {detalhe.get('status')})")
