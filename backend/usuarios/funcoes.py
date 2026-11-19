import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..autenticacao.funcoes import gerar_hash
from ..nucleo.config import Configuracoes
from .erros import ErroEmailJaCadastrado
from .modelos import Usuario
from .schemas import UsuarioCriar

registro = logging.getLogger("ribeiro.usuarios")


def buscar_por_email(db: Session, email: str) -> Optional[Usuario]:
    return db.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))


def criar_usuario(db: Session, dados: UsuarioCriar) -> Usuario:
    """Grava o usuário já com a senha em hash. Levanta ErroEmailJaCadastrado se o e-mail existir."""
    usuario = Usuario(email=dados.email, nome=dados.nome, senha_hash=gerar_hash(dados.senha), admin=dados.admin)
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ErroEmailJaCadastrado(dados.email) from None
    return usuario


def garantir_administrador_inicial(fabrica: sessionmaker, config: Configuracoes) -> None:
    """Primeira subida (banco sem usuários): cria o admin a partir de RIBEIRO_ADMIN_EMAIL/RIBEIRO_ADMIN_SENHA."""
    with fabrica() as db:
        if db.scalar(select(func.count()).select_from(Usuario)):
            return
        if not (config.admin_email and config.admin_senha):
            registro.warning(
                "Nenhum usuário cadastrado. Crie o primeiro: python -m backend.cli criar-usuario --admin "
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
