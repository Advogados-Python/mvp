"""nucleo/ e a escada de fases (GET /api/fases). Os módulos de cada fase estão em test_fases.py."""

import os
import unittest
from pathlib import Path
from unittest import mock

from backend.main import criar_app
from backend.config import Configuracoes
from tests.apoio_backend import ADMIN, BaseApi, configuracao


class TestSaudeEFases(BaseApi):
    def test_saude_confere_o_banco(self):
        self.assertEqual(self.client.get("/api/saude").json(), {"status": "ok"})

    def test_fases_sao_publicas_e_trazem_a_escada(self):
        corpo = self.client.get("/api/fases").json()
        codigos = [f["codigo"] for f in corpo["fases"]]
        self.assertEqual(codigos[0], "SEM_INFORMACAO")
        self.assertEqual(codigos[-1], "QUITADO")
        self.assertTrue(all(f["rotulo"] and f["descricao"] for f in corpo["fases"]))
        self.assertEqual({d["valor"] for d in corpo["divida_paga"]}, {"SIM", "PROVAVEL", "NAO", "SEM_INFORMACAO"})

    def test_cors_libera_so_a_origem_do_frontend(self):
        permitido = self.client.get("/api/saude", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(permitido.headers.get("access-control-allow-origin"), "http://localhost:3000")
        negado = self.client.get("/api/saude", headers={"Origin": "http://site-mal.example"})
        self.assertNotIn("access-control-allow-origin", negado.headers)


class TestConfiguracao(BaseApi):
    def test_producao_exige_segredo_forte(self):
        with self.assertRaises(RuntimeError):
            criar_app(configuracao(self.pasta, ambiente="producao", jwt_segredo=None))
        with self.assertRaises(RuntimeError):
            criar_app(configuracao(self.pasta, ambiente="producao", jwt_segredo="curto"))

    def test_url_do_banco_do_railway_vira_driver_psycopg(self):
        self.assertEqual(
            Configuracoes(_env_file=None, banco_url="postgresql://u:p@h:5432/d").url_do_banco,
            "postgresql+psycopg://u:p@h:5432/d",
        )
        self.assertTrue(Configuracoes(_env_file=None, banco_url="postgres://u:p@h/d").url_do_banco.startswith("postgresql+psycopg://"))

    def test_sem_url_usa_sqlite_na_pasta_de_dados(self):
        config = Configuracoes(_env_file=None, banco_url=None, pasta_dados=self.pasta)
        self.assertEqual(config.url_do_banco, f"sqlite:///{self.pasta / 'ribeiro.db'}")


class TestVariaveisDeAmbiente(unittest.TestCase):
    """Cada variável documentada no README/.env.example precisa realmente mudar a configuração (um nome errado seria ignorado em silêncio)."""

    def carregar(self, **ambiente) -> Configuracoes:
        with mock.patch.dict(os.environ, ambiente, clear=True):
            return Configuracoes(_env_file=None)

    def test_variaveis_documentadas_surtem_efeito(self):
        c = self.carregar(
            RIBEIRO_AMBIENTE="producao", RIBEIRO_JWT_SEGREDO="x" * 40, RIBEIRO_PASTA_DADOS="/dados",
            RIBEIRO_TOKEN_MINUTOS="30", RIBEIRO_LINK_PDF_SEGUNDOS="45",
            RIBEIRO_LOGIN_MAX_TENTATIVAS="9", RIBEIRO_LOGIN_JANELA_SEGUNDOS="60",
            RIBEIRO_ADMIN_EMAIL="a@b.com", RIBEIRO_ADMIN_SENHA="senha-longa-123", RIBEIRO_ADMIN_NOME="Chefe",
            RIBEIRO_CORS_ORIGINS="https://app.exemplo.com, https://outro.exemplo.com",
            RIBEIRO_MAX_PDF_MB="50", RIBEIRO_MAX_ARQUIVOS_POR_ENVIO="5", RIBEIRO_WORKERS_ANALISE="4",
            RIBEIRO_FILA_SINCRONA="true",
        )
        self.assertTrue(c.producao)
        self.assertEqual(c.segredo_jwt(), "x" * 40)
        self.assertEqual(c.pasta_dados, Path("/dados"))
        self.assertEqual((c.token_minutos, c.link_pdf_segundos), (30, 45))
        self.assertEqual((c.login_max_tentativas, c.login_janela_segundos), (9, 60))
        self.assertEqual((c.admin_email, c.admin_senha, c.admin_nome), ("a@b.com", "senha-longa-123", "Chefe"))
        self.assertEqual(c.origens_cors, ["https://app.exemplo.com", "https://outro.exemplo.com"])
        self.assertEqual((c.max_pdf_bytes, c.max_arquivos_por_envio, c.workers_analise), (50 * 1024 * 1024, 5, 4))
        self.assertTrue(c.fila_sincrona)

    def test_url_do_banco_aceita_os_dois_nomes(self):
        self.assertEqual(self.carregar(DATABASE_URL="postgresql://u:p@h/d").url_do_banco, "postgresql+psycopg://u:p@h/d")
        self.assertEqual(self.carregar(RIBEIRO_BANCO_URL="postgres://u:p@h/d").url_do_banco, "postgresql+psycopg://u:p@h/d")

    def test_padroes_seguros(self):
        c = self.carregar()
        self.assertFalse(c.producao)
        self.assertEqual(c.origens_cors, ["http://localhost:3000", "http://127.0.0.1:3000"])  # só o frontend local
        self.assertFalse(c.fila_sincrona)


if __name__ == "__main__":
    unittest.main()
