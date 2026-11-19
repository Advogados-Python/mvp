from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints

Email = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
]
SENHA_MINIMA = 10   # para mudar a regra de tamanho, é só aqui
SENHA_MAXIMA = 128
Senha = Annotated[str, StringConstraints(min_length=SENHA_MINIMA, max_length=SENHA_MAXIMA)]
Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    nome: str
    admin: bool
    ativo: bool
    criado_em: datetime


class UsuarioCriar(BaseModel):
    email: Email
    nome: Nome
    senha: Senha
    admin: bool = False


class UsuarioAtualizar(BaseModel):
    nome: Optional[Nome] = None
    ativo: Optional[bool] = None
    admin: Optional[bool] = None
    nova_senha: Optional[Senha] = None
