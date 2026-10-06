"""Modulo que implementa todas as classes de erro!"""

#Class Usuario
class ErroNomeInvalido(Exception):
    """Não é permitido nome maior que 50 caracteres"""
    def __init__(self, mensagem):
        self.__msg=mensagem
    def __str__(self):
        return "ErroNomeInvalido (" + self.__msg +")"
    
class ErroEmailInvalido(Exception):
    """Não é permitido e-mail maior que 50 caracteres"""
    def __init__(self, mensagem):
        self.__msg=mensagem
    def __str__(self):
        return "ErroEmailInvalido (" + self.__msg +")"
    
class ErroPaisDeOrigemInvalido(Exception):
    """Não é permitido país de origem maior que 10 caracteres"""
    def __init__(self, mensagem):
        self.__msg=mensagem
    def __str__(self):
        return "ErroPaisDeOrigemInvalido (" + self.__msg +")"
    