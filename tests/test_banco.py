"""O banco: cada fase de leitura tem a sua tabela, ligada ao processo (documento). A análise grava nelas, refazer a análise regrava,
apagar o processo leva as linhas junto, e o resultado que antes ficava numa coluna JSON é migrado para elas."""

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock

from sqlalchemy import func, select, text, update

from backend import db as banco
from backend.finalize.logic import migrar_resultados_antigos, para_detalhe
from backend.pipeline import processar_pdf
from backend.receive.models import Processo
from tests.apoio_backend import PDF_PAGO, PDF_PROTEGIDO, PDF_REQUISICAO, BaseApi, gerar_pdf

# tabela -> a fase (pasta) dona dela
TABELAS = {"leituras": "extract", "identificacoes": "identify", "evidencias": "search", "conclusoes": "validate", "resultados": "finalize"}


class TestTabelasDasFases(BaseApi):
    def tabela(self, nome):
        return banco.Base.metadata.tables[nome]

    def contar(self, nome, processo_id) -> int:
        tabela = self.tabela(nome)
        with self.app.state.fabrica() as db:
            return db.scalar(select(func.count()).select_from(tabela).where(tabela.c.processo_id == processo_id))

    def contagens(self, processo_id) -> dict:
        return {nome: self.contar(nome, processo_id) for nome in TABELAS}

    def enviar_um(self, token, nome, pdf) -> str:
        return self.enviar(token, (nome, pdf)).json()["processos"][0]["id"]

    def get(self, token, caminho):
        return self.client.get(caminho, headers=self.cabecalho(token))

    # ---- o desenho
    def test_cada_fase_tem_a_sua_tabela_ligada_ao_processo(self):
        for nome, fase in TABELAS.items():
            with self.subTest(tabela=nome):
                chaves = {fk.target_fullname: fk.ondelete for fk in self.tabela(nome).foreign_keys}
                self.assertEqual(chaves.get("processos.id"), "CASCADE")  # apagar o processo apaga a linha da fase
                classes = [m.class_ for m in banco.Base.registry.mappers if m.local_table.name == nome]
                self.assertEqual([c.__module__ for c in classes], [f"backend.{fase}.models"])  # a classe mora no models.py da fase

    def test_o_processo_nao_guarda_mais_o_resultado_dentro_dele(self):
        colunas = set(self.tabela("processos").columns.keys())
        self.assertEqual(colunas, {"id", "dono_id", "arquivo", "sha256", "tamanho_bytes", "status", "erro", "criado_em", "iniciado_em", "concluido_em"})

    # ---- a análise grava
    def test_a_analise_grava_cada_fase_na_sua_tabela(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_REQUISICAO)
        self.assertEqual(self.contagens(id_), {nome: 1 for nome in TABELAS})
        with self.app.state.fabrica() as db:
            processo = db.get(Processo, id_)
            self.assertEqual((processo.leitura.total_paginas, processo.leitura.paginas_sem_texto), (2, 0))
            self.assertEqual((processo.identificacao.numero_processo, processo.identificacao.tribunal), ("1234567-89.2025.4.01.3500", "TRF1"))
            (evidencia,) = processo.evidencias
            self.assertEqual((evidencia.fase, evidencia.termo, evidencia.pagina, evidencia.conta), ("REQUISICAO", "oficio_requisitorio", 2, True))
            self.assertEqual((processo.conclusao.fase, processo.conclusao.divida_paga), ("REQUISICAO", "NAO"))
            self.assertEqual((processo.resultado.total_evidencias, processo.resultado.evidencias_que_contam), (1, 1))
            self.assertEqual(processo.resultado.evidencia_principal_id, evidencia.id)  # o fechamento aponta a evidência principal

    def test_a_api_le_das_tabelas(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_REQUISICAO)
        novo = "0000000-00.2000.1.00.0000"
        identificacoes, conclusoes = self.tabela("identificacoes"), self.tabela("conclusoes")
        with self.app.state.fabrica() as db:
            db.execute(update(identificacoes).where(identificacoes.c.processo_id == id_).values(numero_processo=novo))
            db.execute(update(conclusoes).where(conclusoes.c.processo_id == id_).values(fase="QUITADO", divida_paga="SIM"))
            db.commit()
        for caminho in (f"/api/processos/{id_}", f"/api/processos/{id_}/identify", f"/api/processos/{id_}/finalize"):
            self.assertEqual(self.get(token, caminho).json()["numero_processo"], novo, caminho)
        self.assertEqual(self.get(token, f"/api/processos/{id_}").json()["divida_paga"], "SIM")
        self.assertEqual(self.get(token, f"/api/processos/{id_}/validate").json()["fase"], "QUITADO")
        self.assertEqual(self.get(token, "/api/processos").json()["processos"][0]["numero_processo"], novo)

    def test_dois_processos_nao_misturam_as_linhas(self):
        token = self.login()
        a = self.enviar_um(token, "a.pdf", PDF_PAGO)
        b = self.enviar_um(token, "b.pdf", PDF_REQUISICAO)
        self.assertEqual(self.contagens(a), {nome: 1 for nome in TABELAS})
        self.assertEqual(self.get(token, f"/api/processos/{a}/validate").json()["fase"], "QUITADO")
        self.assertEqual(self.get(token, f"/api/processos/{b}/validate").json()["fase"], "REQUISICAO")
        self.assertEqual({e["fase"] for e in self.get(token, f"/api/processos/{b}").json()["evidencias"]}, {"REQUISICAO"})

    # ---- refazer, falhar, apagar
    def test_refazer_a_analise_regrava_sem_duplicar(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_REQUISICAO)
        antes = self.get(token, f"/api/processos/{id_}").json()
        self.assertEqual(self.client.post(f"/api/processos/{id_}/reanalisar", headers=self.cabecalho(token)).status_code, 202)
        self.assertEqual(self.contagens(id_), {nome: 1 for nome in TABELAS})
        depois = self.get(token, f"/api/processos/{id_}").json()
        self.assertEqual({k: v for k, v in depois.items() if k != "concluido_em"}, {k: v for k, v in antes.items() if k != "concluido_em"})

    def test_voltar_para_a_fila_apaga_as_linhas_das_fases(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_REQUISICAO)
        with mock.patch.object(self.app.state.fila, "enfileirar", lambda _id: None):  # fica na fila, sem analisar
            resumo = self.client.post(f"/api/processos/{id_}/reanalisar", headers=self.cabecalho(token)).json()
        self.assertEqual(resumo["status"], "PENDENTE")
        self.assertEqual(self.contagens(id_), {nome: 0 for nome in TABELAS})
        self.assertIsNone(resumo["fase"])
        self.assertEqual(self.get(token, f"/api/processos/{id_}/extract").status_code, 409)

    def test_analise_que_falha_nao_deixa_linhas(self):
        token = self.login()
        id_ = self.enviar_um(token, "protegido.pdf", PDF_PROTEGIDO)
        self.assertEqual(self.get(token, f"/api/processos/{id_}").json()["status"], "FALHOU")
        self.assertEqual(self.contagens(id_), {nome: 0 for nome in TABELAS})

    def test_apagar_o_processo_leva_as_linhas_das_fases_junto(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_REQUISICAO)
        self.assertEqual(self.client.delete(f"/api/processos/{id_}", headers=self.cabecalho(token)).status_code, 204)
        self.assertEqual(self.contagens(id_), {nome: 0 for nome in TABELAS})

    def test_fase_sem_linha_gravada_responde_409_e_nao_500(self):
        token = self.login()
        id_ = self.enviar_um(token, "p.pdf", PDF_REQUISICAO)
        conclusoes = self.tabela("conclusoes")
        with self.app.state.fabrica() as db:
            db.execute(conclusoes.delete().where(conclusoes.c.processo_id == id_))
            db.commit()
        resposta = self.get(token, f"/api/processos/{id_}/validate")
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("Refaça a análise", resposta.json()["detail"])
        self.assertEqual(self.get(token, f"/api/processos/{id_}").status_code, 200)  # o detalhe continua abrindo


class TestMigracaoDaColunaJson(unittest.TestCase):
    """Banco antigo: o resultado inteiro ficava na coluna JSON `processos.resultado` (e em quatro colunas copiadas)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        self.motor = banco.criar_motor(f"sqlite:///{self.pasta / 'antigo.db'}")
        self.addCleanup(self.motor.dispose)
        self.fabrica = banco.criar_fabrica_sessoes(self.motor)
        import backend.main  # noqa: F401  (registra todas as tabelas)
        banco.Base.metadata.create_all(self.motor)
        with self.motor.begin() as con:  # volta ao desenho antigo: as colunas de resultado dentro de `processos`
            for coluna in ("numero_processo VARCHAR(40)", "tribunal VARCHAR(20)", "fase VARCHAR(40)", "divida_paga VARCHAR(20)", "resultado JSON"):
                con.execute(text(f"ALTER TABLE processos ADD COLUMN {coluna}"))
            con.execute(text("INSERT INTO usuarios (id, email, nome, senha_hash, ativo, admin, criado_em) VALUES (1, 'a@a.com', 'A', 'x', 1, 0, '2026-01-01')"))

    def resultado_antigo(self) -> tuple:
        """O ResultadoProcesso de um PDF de verdade, no formato em que o código antigo o gravava no JSON."""
        caminho = self.pasta / "p.pdf"
        caminho.write_bytes(gerar_pdf("Numero: 1234567-89.2025.4.01.3500\nExequente: MARIA DA SILVA,", "Certifico o transito em julgado. Expeça-se ofício requisitório."))
        resultado = processar_pdf(caminho)
        dados = resultado.para_dict()
        dados.pop("arquivo")
        principal = resultado.evidencia_principal()
        dados["evidencias"] = [{**asdict(ev), "conta": ev.conta} for ev in resultado.evidencias]
        dados["evidencia_principal"] = {**asdict(principal), "conta": True} if principal else None
        return resultado, dados

    def inserir(self, id_, status, resultado_json):
        with self.motor.begin() as con:
            con.execute(
                text("INSERT INTO processos (id, dono_id, arquivo, sha256, tamanho_bytes, status, criado_em, resultado) "
                     "VALUES (:id, 1, :arquivo, :sha, 10, :status, '2026-01-01', :resultado)"),
                {"id": id_, "arquivo": f"{id_}.pdf", "sha": id_, "status": status, "resultado": resultado_json},
            )

    def test_migra_o_resultado_para_as_tabelas_das_fases(self):
        resultado, dados = self.resultado_antigo()
        self.inserir("a" * 32, "CONCLUIDO", json.dumps(dados))
        self.inserir("b" * 32, "FALHOU", "null")   # o JSON null que o código antigo gravava quando a análise falhava
        self.inserir("c" * 32, "PENDENTE", None)

        self.assertEqual(migrar_resultados_antigos(self.motor, self.fabrica), 1)

        with self.fabrica() as db:
            concluido = db.get(Processo, "a" * 32)
            detalhe = para_detalhe(concluido)
            self.assertEqual((detalhe.numero_processo, detalhe.tribunal, detalhe.fase, detalhe.divida_paga), (dados["numero_processo"], dados["tribunal"], dados["fase"], dados["divida_paga"]))
            self.assertEqual(detalhe.total_paginas, dados["total_paginas"])
            self.assertEqual([p.model_dump() for p in detalhe.partes], dados["partes"])
            self.assertEqual((detalhe.advogados, detalhe.oabs, detalhe.juiz, detalhe.avisos), (dados["advogados"], dados["oabs"], dados["juiz"], dados["avisos"]))
            self.assertEqual(detalhe.fase_descricao, dados["fase_descricao"])
            self.assertEqual([e.model_dump() for e in detalhe.evidencias], dados["evidencias"])  # mesma lista, na mesma ordem
            self.assertEqual(detalhe.evidencia_principal.model_dump(), dados["evidencia_principal"])
            self.assertEqual((detalhe.total_evidencias, detalhe.evidencias_que_contam), (len(dados["evidencias"]), sum(e["conta"] for e in dados["evidencias"])))
            for id_ in ("b" * 32, "c" * 32):  # sem resultado: nada a migrar
                self.assertIsNone(db.get(Processo, id_).leitura)

    def test_e_segura_para_repetir_e_nao_apaga_a_coluna_antiga(self):
        _, dados = self.resultado_antigo()
        self.inserir("a" * 32, "CONCLUIDO", json.dumps(dados))
        self.assertEqual(migrar_resultados_antigos(self.motor, self.fabrica), 1)
        self.assertEqual(migrar_resultados_antigos(self.motor, self.fabrica), 0)  # já migrado
        with self.motor.connect() as con:
            self.assertEqual(json.loads(con.execute(text("SELECT resultado FROM processos WHERE id = :i"), {"i": "a" * 32}).scalar()), dados)
            self.assertEqual(con.execute(text("SELECT count(*) FROM evidencias")).scalar(), len(dados["evidencias"]))

    def test_banco_novo_nao_tem_o_que_migrar(self):
        motor = banco.criar_motor(f"sqlite:///{self.pasta / 'novo.db'}")
        self.addCleanup(motor.dispose)
        banco.Base.metadata.create_all(motor)
        self.assertEqual(migrar_resultados_antigos(motor, banco.criar_fabrica_sessoes(motor)), 0)


if __name__ == "__main__":
    unittest.main()
