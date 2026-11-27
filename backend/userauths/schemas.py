import re
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints
from pydantic_core import PydanticCustomError

Email = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
]
SENHA_MINIMA = 10   # para mudar a regra de tamanho, é só aqui
SENHA_MAXIMA = 128
Senha = Annotated[str, StringConstraints(min_length=SENHA_MINIMA, max_length=SENHA_MAXIMA)]
Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

UFS_VALIDAS = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
})
_OAB_UF_ANTES = re.compile(r"^([A-Z]{2})(\d{1,6}[A-Z]?)$")   # SP123456 (aceita a letra suplementar no fim: SP12345A)
_OAB_UF_DEPOIS = re.compile(r"^(\d{1,6}[A-Z]?)([A-Z]{2})$")  # 123456/SP


def normalizar_oab(texto: str) -> str:
    """'123.456/sp', 'SP 123456' e 'sp-123456' viram 'SP123456'. O frontend repete esta regra (frontend/src/lib/oab.ts).
    Confere só o formato e a UF: não consulta o Cadastro Nacional da OAB."""
    limpo = re.sub(r"[.\-/\s]", "", texto.strip().upper())
    if casou := _OAB_UF_ANTES.match(limpo):
        uf, numero = casou.groups()
    elif casou := _OAB_UF_DEPOIS.match(limpo):
        numero, uf = casou.groups()
    else:
        raise PydanticCustomError("oab_invalida", "Formato inválido. Use UF + número (ex.: GO12345 ou 12345/GO).")
    if uf not in UFS_VALIDAS:
        raise PydanticCustomError("oab_uf_invalida", "A sigla de estado '{uf}' não existe.", {"uf": uf})
    return f"{uf}{numero}"


Oab = Annotated[str, StringConstraints(max_length=20), AfterValidator(normalizar_oab)]


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    nome: str
    admin: bool
    ativo: bool
    oab: Optional[str] = None
    criado_em: datetime


class UsuarioCriar(BaseModel):
    email: Email
    nome: Nome
    senha: Senha
    admin: bool = False


class UsuarioRegistrar(BaseModel):
    """O "Registre-se" da tela de login. A confirmação da senha fica no formulário: a API recebe a senha uma vez só."""

    nome: Nome
    email: Email
    senha: Senha
    oab: Oab


class UsuarioAtualizar(BaseModel):
    nome: Optional[Nome] = None
    ativo: Optional[bool] = None
    admin: Optional[bool] = None
    nova_senha: Optional[Senha] = None


class AlterarSenha(BaseModel):
    senha_atual: str = Field(max_length=128)
    nova_senha: Senha


class TokenSaida(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expira_em: datetime
    usuario: UsuarioSaida
