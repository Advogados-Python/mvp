"""Testes do pipeline. Rodar na raiz do projeto:  python -m unittest discover -s tests -t . -v

Os textos aqui são SINTÉTICOS (sem dados reais de clientes). Vários casos reproduzem
armadilhas que apareceram nos autos reais usados no desenvolvimento.
"""

import csv
import tempfile
import unittest
from pathlib import Path

import pymupdf

from app import (
    ErroPdfNaoEncontrado, Pagina, ResultadoProcesso, buscar_termos, classificar_fase,
    exportar_csv, extrair_metadados, identificar_tribunal, ler_pdf, processar_pdf, responder_divida_paga,
)


def fase_de(texto, tipo=None):
    return classificar_fase(buscar_termos([Pagina(numero=1, texto=texto, tipo_documento=tipo)]))


class TestClassificacao(unittest.TestCase):
    def test_extincao_por_pagamento_e_quitado(self):
        fase = fase_de("Diante do pagamento, JULGO EXTINTA a execução, nos termos do art. 924, II, do CPC.")
        self.assertEqual(fase, "QUITADO")
        self.assertEqual(responder_divida_paga(fase), "SIM")

    def test_nao_havendo_pendencias_continua_quitado(self):
        # "não" distante do termo não pode derrubar a evidência de pagamento
        self.assertEqual(fase_de("Não havendo outras pendências, julgo extinta a execução."), "QUITADO")

    def test_levantamento_realizado_e_quitado(self):
        self.assertEqual(fase_de("Certifico que o levantamento foi efetuado pela parte autora."), "QUITADO")

    def test_valores_depositados_e_provavel(self):
        fase = fase_de("Os valores foram depositados à disposição do exequente.")
        self.assertEqual(fase, "PAGAMENTO_DISPONIBILIZADO")
        self.assertEqual(responder_divida_paga(fase), "PROVAVEL")

    def test_aguarde_se_quitacao_nao_e_pago(self):
        # Trecho real de decisão do TJSP: "quitação" aqui é futuro.
        fase = fase_de("Assim, expeça-se ofício requisitório. Aguarde-se sua quitação, consignando-se que o crédito será pago.")
        self.assertEqual(fase, "REQUISICAO")
        self.assertEqual(responder_divida_paga(fase), "NAO")

    def test_texto_padrao_futuro_do_jef_e_hipotetico(self):
        # Texto-padrão real dos JEFs: sem o filtro, viraria falso "pagamento disponibilizado".
        texto = ("Após o pagamento, a parte exequente será intimada para o levantamento dos valores, "
                 "diretamente na agência bancária, sem expedição de alvará.")
        evidencias = buscar_termos([Pagina(numero=1, texto=texto)])
        self.assertEqual(classificar_fase(evidencias), "SEM_INFORMACAO")
        self.assertTrue(evidencias and all(ev.hipotetico for ev in evidencias))

    def test_antes_da_expedicao_e_hipotetico(self):
        self.assertEqual(fase_de("Antes da expedição do ofício requisitório, apresente a procuração atualizada."), "SEM_INFORMACAO")

    def test_negacao_colada_no_termo_e_hipotetica(self):
        self.assertEqual(fase_de("Informa-se que ainda não foi efetuado o depósito efetuado pelo ente."), "SEM_INFORMACAO")

    def test_peca_da_parte_nao_decide_fase(self):
        texto = "JULGO EXTINTA a execução pelo pagamento, art. 924, II."
        self.assertEqual(fase_de(texto, tipo="Petição intercorrente"), "SEM_INFORMACAO")
        self.assertEqual(fase_de(texto, tipo="Manifestação"), "SEM_INFORMACAO")

    def test_peca_do_juizo_decide_fase(self):
        self.assertEqual(fase_de("JULGO EXTINTA a execução pelo pagamento.", tipo="Sentença Tipo A"), "QUITADO")

    def test_certifico_transito_com_nao_distante(self):
        texto = ("Aplica-se o CPC no que não conflitar com a Lei 10.259, de 12 de julho de 2001, tal como previsto "
                 "em seu artigo 1º, certifico o trânsito em julgado da sentença.")
        self.assertEqual(fase_de(texto), "TRANSITO_EM_JULGADO")

    def test_requisicao_numerada_trf1(self):
        self.assertEqual(fase_de("Requisição de Pagamento 2026.0000.000.000001"), "REQUISICAO")

    def test_fase_mais_alta_vence(self):
        paginas = [
            Pagina(numero=1, texto="Julgo procedente o pedido e condeno o INSS."),
            Pagina(numero=2, texto="Certidão de trânsito em julgado."),
            Pagina(numero=3, texto="Expeça-se ofício requisitório."),
        ]
        self.assertEqual(classificar_fase(buscar_termos(paginas)), "REQUISICAO")

    def test_sem_nada_e_sem_informacao(self):
        fase = fase_de("Texto qualquer sem nenhum termo relevante.")
        self.assertEqual(fase, "SEM_INFORMACAO")
        self.assertEqual(responder_divida_paga(fase), "SEM_INFORMACAO")

    def test_evidencia_guarda_pagina_e_trecho(self):
        ev = buscar_termos([Pagina(numero=1, texto="x"), Pagina(numero=7, texto="Expeça-se ofício requisitório.")])[0]
        self.assertEqual(ev.pagina, 7)
        self.assertIn("ofício requisitório", ev.trecho)


class TestMetadados(unittest.TestCase):
    CAPA_PJE = (
        "Número: 1234567-89.2025.4.01.3500\n"
        "Classe: PROCEDIMENTO DO JUIZADO ESPECIAL CÍVEL\n"
        "Órgão julgador: 13ª Vara Federal de Juizado Especial Cível da SJGO\n"
        "Valor da causa: R$ 36.471,14\n"
        "FULANO DE TAL (AUTOR)   BELTRANO SILVA (ADVOGADO)\n"
        "INSTITUTO NACIONAL DO SEGURO SOCIAL - INSS (REU)\n"
        "Advogado inscrito na OAB/GO nº 12.345 e também OAB: 678901/SP e OAB SP - 678901.\n"
    )

    def test_identificar_tribunal(self):
        self.assertEqual(identificar_tribunal("0000001-23.2020.8.26.0100"), "TJSP")
        self.assertEqual(identificar_tribunal("1000001-23.2025.4.01.3500"), "TRF1")
        self.assertEqual(identificar_tribunal("5012345-67.2024.8.09.0051"), "TJGO")
        self.assertEqual(identificar_tribunal("lixo"), "desconhecido")

    def test_capa_pje(self):
        meta = extrair_metadados([Pagina(numero=1, texto=self.CAPA_PJE)])
        self.assertEqual(meta["numero_processo"], "1234567-89.2025.4.01.3500")
        self.assertEqual(meta["classe"], "PROCEDIMENTO DO JUIZADO ESPECIAL CÍVEL")
        self.assertEqual(meta["valor_causa"], "R$ 36.471,14")
        self.assertEqual(meta["advogados"], ["BELTRANO SILVA"])
        papeis = {(p["nome"], p["papel"]) for p in meta["partes"]}
        self.assertIn(("FULANO DE TAL", "AUTOR"), papeis)
        self.assertIn(("INSTITUTO NACIONAL DO SEGURO SOCIAL - INSS", "RÉU"), papeis)

    def test_oab_tres_formatos_normalizados(self):
        oabs = extrair_metadados([Pagina(numero=1, texto=self.CAPA_PJE)])["oabs"]
        self.assertIn("OAB/GO 12345 (1x)", oabs)
        self.assertIn("OAB/SP 678901 (2x)", oabs)  # "678901/SP" e "SP - 678901" viram a mesma OAB

    def test_juiz_pje_e_quem_assina_a_sentenca(self):
        paginas = [
            Pagina(numero=1, texto="x", tipo_documento="Ato ordinatório", assinante="SERVIDOR DA SILVA"),
            Pagina(numero=2, texto="x", tipo_documento="Sentença Tipo A", assinante="MARIA JUIZA EXEMPLO"),
        ]
        self.assertEqual(extrair_metadados(paginas)["juiz"], "MARIA JUIZA EXEMPLO")

    def test_juiz_esaj(self):
        texto = "Juiz(a) de Direito: Dr(a). JOSE JUIZ EXEMPLO\n\nDocumento assinado"
        self.assertEqual(extrair_metadados([Pagina(numero=1, texto=texto)])["juiz"], "JOSE JUIZ EXEMPLO")

    def test_numero_sem_capa_usa_o_mais_repetido(self):
        texto = "Proc. 0000001-23.2020.8.26.0100\n" * 5 + "ver também 1111111-11.2020.8.26.0100"
        self.assertEqual(extrair_metadados([Pagina(numero=1, texto=texto)])["numero_processo"], "0000001-23.2020.8.26.0100")


class TestPdfEExportacao(unittest.TestCase):
    def test_pdf_inexistente(self):
        with self.assertRaises(ErroPdfNaoEncontrado):
            ler_pdf("nao_existe.pdf")

    def test_pipeline_ponta_a_ponta_com_pdf_gerado(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "processo.pdf"
            doc = pymupdf.open()
            doc.new_page().insert_text((72, 72), "Numero: 1234567-89.2025.4.01.3500")
            doc.new_page().insert_text((72, 72), "Certifico o transito em julgado. Expeça-se ofício requisitório.")
            doc.new_page()  # página em branco = "scan" sem texto
            doc.new_page().insert_text((72, 72), "Julgo extinta a execução pelo pagamento.")
            doc.save(caminho)
            doc.close()

            r = processar_pdf(caminho)
            self.assertEqual(r.total_paginas, 4)
            self.assertEqual(r.paginas_sem_texto, 1)
            self.assertEqual(r.fase, "QUITADO")
            self.assertEqual(r.divida_paga, "SIM")
            self.assertEqual(r.evidencia_principal().pagina, 4)
            self.assertTrue(any("sem texto" in aviso and "3" in aviso for aviso in r.avisos))

    def test_csv_neutraliza_formula(self):
        r = ResultadoProcesso(arquivo="a.pdf", juiz='=HYPERLINK("http://mal.example")')
        with tempfile.TemporaryDirectory() as pasta:
            destino = exportar_csv([r], pasta)
            with destino.open(encoding="utf-8-sig", newline="") as f:
                linha = next(csv.DictReader(f, delimiter=";"))
        self.assertTrue(linha["juiz"].startswith("'="))


if __name__ == "__main__":
    unittest.main()
