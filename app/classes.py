"""Classes para manipulação e gerenciamento de Users dentro de LearnLanguages"""

# Imports.
from .erros import *
from . import constantes as const

# 9) Implementar a classe abstrata Usuario: -----------------------------------------------------------------------------------
from abc import ABCMeta, abstractmethod # Classe de base abstrata.

class Usuario(metaclass=ABCMeta):
    def __init__(self, nome, email, senha):
        self.nome = nome
        self.email = email
        self.senha = senha

        
    @property   # Máximo 50 caracteres.
    def nome(self):
        return self._nome
    
    @nome.setter  
    def nome(self, nome):
        if len(nome) > const.MAX_NOME:
            raise ErroNomeInvalido(f"O nome deve ter no máximo {const.MAX_NOME} caracteres")
        else:
             self._nome = nome

    @property  # Máximo 50 caracteres.
    def email(self):
        return self._email
    
    @email.setter  
    def email(self, email):
        if len(email) > const.MAX_EMAIL:
             raise ErroEmailInvalido(f"O e-mail deve ter no máximo {const.MAX_EMAIL} caracteres")
        else:
             self._email = email


    @property  # Máximo 10 caracteres.
    def paisOrigem(self):
        return self._paisOrigem
    
    @paisOrigem.setter 
    def paisOrigem(self, paisOrigem):
        if len(paisOrigem) > const.MAX_PAISORIGEM:
             raise ErroPaisDeOrigemInvalido(f"O país de origem deve ter no máximo {const.MAX_PAISORIGEM} caracteres")
        else:
             self._paisOrigem = paisOrigem


    @property  # Máximo 10 caracteres.
    def paisAtual(self):
        return self._paisAtual
    
    @paisAtual.setter 
    def paisAtual(self, paisAtual):
        if len(paisAtual) > const.MAX_PAISATUAL:
             raise ErroPaisAtualInvalido(f"O país de atual deve ter no máximo {const.MAX_PAISATUAL} caracteres")
        else:
            self._paisAtual = paisAtual

    @property
    def idiomas(self):
        return self._idiomas.copy()

    @idiomas.setter
    def idiomas(self, i_list):
        if all(isinstance(i, Idioma) for i in i_list):
            self._idiomas = i_list
        else:
            raise ErroIdiomaInvalido(f"O nome do idioma não pode exceder {const.MAX_IDIOMA} caracteres.")

    def adicionar_idioma(self, idioma):
        if isinstance(idioma, Idioma):
            self._idiomas.append(idioma)
        else:
            raise ErroIdiomaInvalido(f"O nome do idioma não pode exceder {const.MAX_IDIOMA} caracteres.")

        
    @property  # Uma Lista [] de objetos horario que mostra os horários do usuário.
    def horarios(self):
         return self._horarios
    
    @horarios.setter
    def horarios(self, h_list):
        if all(isinstance(h, Horario) for h in h_list):
            self._horarios = h_list


    @property  # Objeto do tipo carteira necessário para efetuar ou receber pagamentos das aulas.
    def carteira(self):
         return self._carteira

    @carteira.setter 
    def carteira(self, carteira):
        self._carteira = carteira

# b) Métodos: 
        
# i) imprimirRelatorio: Método abstrato que deve ser implementado pelas classes que herdam a classe Usuario.
# imprimir um relatório completo sobre as atividades do usuário.
        
    @abstractmethod
    def imprimirRelatorio(self):
        """ Método abstrato que deve ser implementado nas subclasses """
        pass
       
# 10) Implemente a classe Estudante como uma subclasse de Usuario:
     
