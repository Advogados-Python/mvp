import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash

from ..usuarios.modelos import Usuario
from .constantes import ALGORITMO, TIPO_ACESSO, TIPO_PDF

_hash = PasswordHash.recommended()  # Argon2id
# Hash de mentira: login com e-mail inexistente gasta o mesmo tempo que um com senha errada,
# senão o tempo de resposta revelaria quais e-mails têm conta.
_HASH_FALSO = _hash.hash("senha-que-nao-existe")


def gerar_hash(senha: str) -> str:
    return _hash.hash(senha)


def conferir_senha(senha: str, senha_hash: Optional[str]) -> bool:
    if senha_hash is None:
        _hash.verify(senha, _HASH_FALSO)
        return False
    try:
        return _hash.verify(senha, senha_hash)
    except Exception:  # hash corrompido/formato desconhecido: nega em vez de derrubar o login
        return False


def versao_da_senha(usuario: Usuario) -> str:
    """Vai dentro do token. Trocar a senha muda este valor e derruba os logins antigos."""
    return hashlib.sha256(usuario.senha_hash.encode()).hexdigest()[:12]


def erro_401(detalhe: str = "Sessão inválida ou expirada. Entre de novo.") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detalhe, headers={"WWW-Authenticate": "Bearer"})


def _codificar(dados: dict, segredo: str, validade: timedelta) -> tuple:
    agora = datetime.now(timezone.utc)
    expira = agora + validade
    token = jwt.encode({**dados, "iat": agora, "exp": expira}, segredo, algorithm=ALGORITMO)
    return token, expira


def criar_token_acesso(usuario: Usuario, segredo: str, minutos: int) -> tuple:
    return _codificar(
        {"sub": str(usuario.id), "tipo": TIPO_ACESSO, "sv": versao_da_senha(usuario)}, segredo, timedelta(minutes=minutos)
    )


def criar_link_pdf(usuario: Usuario, processo_id: str, segredo: str, segundos: int) -> tuple:
    """Token de vida curta, válido só para ESTE PDF. Vai na URL porque uma nova aba não envia o cabeçalho Authorization."""
    return _codificar(
        {"sub": str(usuario.id), "tipo": TIPO_PDF, "pid": processo_id, "sv": versao_da_senha(usuario)},
        segredo,
        timedelta(seconds=segundos),
    )


def decodificar(token: str, segredo: str, tipo: str) -> dict:
    """Valida assinatura, validade e tipo. Um token de PDF não serve como login, e vice-versa."""
    try:
        dados = jwt.decode(token, segredo, algorithms=[ALGORITMO], options={"require": ["exp", "sub", "tipo"]})
    except jwt.InvalidTokenError:
        raise erro_401() from None
    if dados.get("tipo") != tipo:
        raise erro_401()
    return dados


def token_vale_para(usuario: Optional[Usuario], dados: dict) -> bool:
    return bool(usuario and usuario.ativo and usuario.senha_hash and dados.get("sv") == versao_da_senha(usuario))
