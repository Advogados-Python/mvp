from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..usuarios.schemas import Senha, UsuarioSaida


class AlterarSenha(BaseModel):
    senha_atual: str = Field(max_length=128)
    nova_senha: Senha


class TokenSaida(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expira_em: datetime
    usuario: UsuarioSaida
