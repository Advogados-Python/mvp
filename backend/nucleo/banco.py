"""Conexão com o banco (SQLAlchemy 2). SQLite por padrão; Postgres em produção."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class DataHoraUTC(TypeDecorator):
    """DateTime que sempre entra e sai em UTC com fuso, igual em qualquer banco. O SQLite devolve datas sem fuso
    (o navegador leria '2026-11-18T19:11:00' como horário local) e o Postgres devolve no fuso da sessão."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, valor, dialeto):
        if valor is not None and valor.tzinfo is not None:
            return valor.astimezone(timezone.utc)
        return valor

    def process_result_value(self, valor, dialeto):
        if valor is None:
            return None
        if valor.tzinfo is None:  # SQLite devolve sem fuso (o que gravamos era UTC)
            return valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc)  # Postgres devolve no fuso da sessão: normaliza para UTC


def agora() -> datetime:
    return datetime.now(timezone.utc)


def criar_motor(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)

    argumentos = {}
    if url in ("sqlite://", "sqlite:///:memory:"):  # em memória: todas as threads precisam da MESMA conexão
        argumentos["poolclass"] = StaticPool
    # check_same_thread=False: a análise roda em threads próprias, cada uma com a sua Session
    motor = create_engine(url, connect_args={"check_same_thread": False}, **argumentos)

    @event.listens_for(motor, "connect")
    def _pragmas(conexao, _registro):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")  # espera o lock em vez de falhar na hora
        cursor.execute("PRAGMA journal_mode=WAL")    # leitura não bloqueia a escrita da análise
        cursor.close()

    return motor


def criar_fabrica_sessoes(motor: Engine) -> sessionmaker:
    return sessionmaker(bind=motor, expire_on_commit=False)
