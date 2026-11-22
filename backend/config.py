"""Configuração por variáveis de ambiente (prefixo RIBEIRO_) ou arquivo .env na raiz.

Exemplos:  RIBEIRO_JWT_SEGREDO=...  RIBEIRO_PASTA_DADOS=/data  DATABASE_URL=postgresql://...
"""

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Optional

from fastapi import Depends, Request

from pydantic import AliasChoices, Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent  # backend/config.py -> raiz do projeto
registro = logging.getLogger("ribeiro.config")


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RIBEIRO_", env_file=RAIZ / ".env", extra="ignore", populate_by_name=True,
    )

    _segredo_efemero: Optional[str] = PrivateAttr(default=None)

    ambiente: Literal["desenvolvimento", "producao"] = "desenvolvimento"

    # Banco. Sem URL, usa SQLite em <pasta_dados>/ribeiro.db. DATABASE_URL é o nome padrão do Railway/Heroku.
    banco_url: Optional[str] = Field(default=None, validation_alias=AliasChoices("RIBEIRO_BANCO_URL", "DATABASE_URL"))
    pasta_dados: Path = RAIZ / "data"  # PDFs enviados (e o SQLite, se for o caso). Em produção: um volume.

    # Autenticação
    jwt_segredo: Optional[str] = None
    token_minutos: int = 480              # validade do login
    link_pdf_segundos: int = 120          # validade do link assinado para abrir o PDF numa nova aba
    login_max_tentativas: int = 5         # falhas seguidas (por IP + e-mail) antes de bloquear
    login_janela_segundos: int = 900

    # Primeiro administrador: criado na subida se ainda não houver nenhum usuário.
    admin_email: Optional[str] = None
    admin_senha: Optional[str] = None
    admin_nome: str = "Administrador"

    # API e análise
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"  # RIBEIRO_CORS_ORIGINS (lista separada por vírgulas)
    max_pdf_mb: int = 200
    max_arquivos_por_envio: int = 20
    workers_analise: int = 2              # análises simultâneas (threads)
    fila_sincrona: bool = False           # True = analisa dentro da requisição (testes/depuração)
    sse_duracao_maxima: float = 30        # segundos que o acompanhamento ao vivo (SSE) fica aberto antes de pedir que o navegador reabra

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def origens_cors(self) -> list:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]

    @property
    def max_pdf_bytes(self) -> int:
        return self.max_pdf_mb * 1024 * 1024

    @property
    def url_do_banco(self) -> str:
        """URL pronta para o SQLAlchemy (o Railway entrega 'postgresql://', que cairia no driver errado)."""
        if not self.banco_url:
            return f"sqlite:///{self.pasta_dados / 'ribeiro.db'}"
        for prefixo in ("postgres://", "postgresql://"):
            if self.banco_url.startswith(prefixo):
                return "postgresql+psycopg://" + self.banco_url[len(prefixo):]
        return self.banco_url

    def segredo_jwt(self) -> str:
        """Em produção o segredo é obrigatório. Em desenvolvimento, sem segredo, gera um efêmero (os logins caem ao reiniciar)."""
        if self.jwt_segredo:
            if self.producao and len(self.jwt_segredo) < 32:
                raise RuntimeError("RIBEIRO_JWT_SEGREDO precisa ter pelo menos 32 caracteres em produção.")
            return self.jwt_segredo
        if self.producao:
            raise RuntimeError("Defina RIBEIRO_JWT_SEGREDO (ex.: openssl rand -hex 32) para rodar em produção.")
        if self._segredo_efemero is None:
            registro.warning("RIBEIRO_JWT_SEGREDO não definido: usando um segredo temporário; os logins caem ao reiniciar.")
            self._segredo_efemero = secrets.token_urlsafe(48)
        return self._segredo_efemero


@lru_cache
def obter_configuracoes() -> Configuracoes:
    return Configuracoes()


def obter_config(request: Request) -> Configuracoes:
    return request.app.state.config


Config = Annotated[Configuracoes, Depends(obter_config)]
