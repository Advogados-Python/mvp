"""A lógica de usuários e login: senhas, tokens, usuários e as mensagens de erro de validação (que nunca ecoam a senha)."""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pwdlib import PasswordHash
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..config import Configuracoes
from .models import ErroEmailJaCadastrado, Usuario
from .schemas import UsuarioCriar

ALGORITMO = "HS256"
TIPO_ACESSO = "acesso"  # token de login
TIPO_PDF = "pdf"        # link assinado de vida curta, válido só para um PDF

registro = logging.getLogger("ribeiro.usuarios")


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


def buscar_por_email(db: Session, email: str) -> Optional[Usuario]:
    return db.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))


def criar_usuario(db: Session, dados: UsuarioCriar, *, ativo: bool = True, oab: Optional[str] = None) -> Usuario:
    """Grava o usuário já com a senha em hash. Levanta ErroEmailJaCadastrado se o e-mail existir.
    O hash é calculado antes de saber se o e-mail existe: o Registre-se responde no mesmo tempo nos dois casos."""
    usuario = Usuario(
        email=dados.email, nome=dados.nome, senha_hash=gerar_hash(dados.senha), admin=dados.admin, ativo=ativo, oab=oab
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ErroEmailJaCadastrado(dados.email) from None
    return usuario


def adicionar_colunas_novas(motor: Engine) -> None:
    """O create_all cria tabela que falta, mas não acrescenta coluna em tabela que já existe. Bancos criados antes do
    Registre-se (o do Railway, o SQLite local) ganham aqui a coluna `oab`. Roda na subida e é segura para repetir."""
    colunas = {coluna["name"] for coluna in inspect(motor).get_columns("usuarios")}
    if "oab" not in colunas:
        with motor.begin() as conexao:
            conexao.execute(text("ALTER TABLE usuarios ADD COLUMN oab VARCHAR(12)"))
        registro.info("Coluna usuarios.oab adicionada.")


def garantir_administrador_inicial(fabrica: sessionmaker, config: Configuracoes) -> None:
    """Primeira subida (banco sem usuários): cria o admin a partir de RIBEIRO_ADMIN_EMAIL/RIBEIRO_ADMIN_SENHA."""
    with fabrica() as db:
        if db.scalar(select(func.count()).select_from(Usuario)):
            return
        if not (config.admin_email and config.admin_senha):
            registro.warning(
                "Nenhum usuário cadastrado. Crie o primeiro: python -m backend.userauths.cli criar-usuario --admin "
                "(ou defina RIBEIRO_ADMIN_EMAIL e RIBEIRO_ADMIN_SENHA)."
            )
            return
        db.add(
            Usuario(
                email=config.admin_email.strip().lower(),
                nome=config.admin_nome,
                senha_hash=gerar_hash(config.admin_senha),
                admin=True,
            )
        )
        db.commit()
        registro.info("Administrador inicial criado: %s", config.admin_email)


def traduzir_erro(erro: dict) -> dict:
    """Devolve só {type, loc, msg}: sem `input`, `ctx` nem `url`."""
    tipo, ctx = erro.get("type", ""), erro.get("ctx") or {}
    if tipo == "string_too_short":
        msg = f"Precisa ter pelo menos {ctx.get('min_length')} caracteres."
    elif tipo == "string_too_long":
        msg = f"Pode ter no máximo {ctx.get('max_length')} caracteres."
    elif tipo == "missing":
        msg = "Campo obrigatório."
    elif tipo == "string_pattern_mismatch":
        msg = "Formato inválido."
    else:
        msg = erro.get("msg", "Valor inválido.")
    return {"type": tipo, "loc": list(erro.get("loc", ())), "msg": msg}


def traduzir_erros(erros) -> list:
    return [traduzir_erro(erro) for erro in erros]


def resumir_erros(erros) -> str:
    """Uma linha legível, para o terminal: 'senha: Precisa ter pelo menos 10 caracteres.'"""
    return "; ".join(f"{'.'.join(str(parte) for parte in e['loc'])}: {e['msg']}" for e in traduzir_erros(erros))


async def tratar_erro_de_validacao(_requisicao: Request, erro: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": traduzir_erros(erro.errors())})
