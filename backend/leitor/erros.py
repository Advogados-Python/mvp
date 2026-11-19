"""Modulo que implementa todas as classes de erro!"""


class ErroRibeiro(Exception):
    """Base de todos os erros do projeto (permite um único `except ErroRibeiro` no main)."""
    def __init__(self, mensagem):
        self.__msg = mensagem

    def __str__(self):
        return f"{type(self).__name__} ({self.__msg})"


# Leitura de PDF
class ErroPdfNaoEncontrado(ErroRibeiro):
    """O caminho informado não existe ou não é um arquivo."""


class ErroPdfProtegido(ErroRibeiro):
    """O PDF está protegido por senha."""


class ErroLeituraPdf(ErroRibeiro):
    """O arquivo não pôde ser aberto como PDF (corrompido, formato inválido...)."""
