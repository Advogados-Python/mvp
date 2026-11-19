from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from ..nucleo.dependencias import Config, Sessao
from ..usuarios.funcoes import buscar_por_email
from ..usuarios.schemas import UsuarioSaida
from .dependencias import UsuarioLogado
from .funcoes import conferir_senha, criar_token_acesso, gerar_hash
from .schemas import AlterarSenha, TokenSaida

roteador = APIRouter(prefix="/api/auth", tags=["autenticação"])


@roteador.post("/login", response_model=TokenSaida, summary="Entrar (formulário OAuth2: username = e-mail)")
def login(request: Request, formulario: Annotated[OAuth2PasswordRequestForm, Depends()], db: Sessao, config: Config):
    email = formulario.username.strip().lower()
    limitador = request.app.state.limitador
    chave = f"{request.client.host if request.client else '?'}|{email}"

    espera = limitador.segundos_de_bloqueio(chave)
    if espera:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Muitas tentativas. Tente de novo em {max(1, round(espera / 60))} min.",
            headers={"Retry-After": str(espera)},
        )

    usuario = buscar_por_email(db, email)
    senha_ok = conferir_senha(formulario.password, usuario.senha_hash if usuario else None)
    if not (usuario and senha_ok and usuario.ativo):
        limitador.registrar_falha(chave)
        # mesma mensagem para e-mail inexistente, senha errada e conta desativada: não ajuda quem está tentando adivinhar
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos.", headers={"WWW-Authenticate": "Bearer"})

    limitador.limpar(chave)
    token, expira = criar_token_acesso(usuario, request.app.state.segredo, config.token_minutos)
    return TokenSaida(access_token=token, expira_em=expira, usuario=UsuarioSaida.model_validate(usuario))


@roteador.get("/eu", response_model=UsuarioSaida, summary="Quem está logado")
def eu(usuario: UsuarioLogado):
    return usuario


@roteador.post("/senha", status_code=status.HTTP_204_NO_CONTENT, summary="Trocar a própria senha (derruba os outros logins)")
def alterar_senha(dados: AlterarSenha, usuario: UsuarioLogado, db: Sessao):
    if not conferir_senha(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A senha atual não confere.")
    usuario.senha_hash = gerar_hash(dados.nova_senha)
    db.commit()
