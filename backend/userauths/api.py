from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from ..config import Config
from ..db import Sessao
from .deps import Administrador, UsuarioLogado
from .logic import buscar_por_email, conferir_senha, criar_token_acesso, criar_usuario, gerar_hash
from .models import ErroEmailJaCadastrado, Usuario
from .schemas import AlterarSenha, TokenSaida, UsuarioAtualizar, UsuarioCriar, UsuarioSaida

auth_router = APIRouter(prefix="/api/auth", tags=["autenticação"])


@auth_router.post("/login", response_model=TokenSaida, summary="Entrar (formulário OAuth2: username = e-mail)")
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


@auth_router.get("/eu", response_model=UsuarioSaida, summary="Quem está logado")
def eu(usuario: UsuarioLogado):
    return usuario


@auth_router.post("/senha", status_code=status.HTTP_204_NO_CONTENT, summary="Trocar a própria senha (derruba os outros logins)")
def alterar_senha(dados: AlterarSenha, usuario: UsuarioLogado, db: Sessao):
    if not conferir_senha(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A senha atual não confere.")
    usuario.senha_hash = gerar_hash(dados.nova_senha)
    db.commit()


users_router = APIRouter(prefix="/api/usuarios", tags=["usuários (administrador)"])


@users_router.get("", response_model=list[UsuarioSaida], summary="Lista os usuários")
def listar(_admin: Administrador, db: Sessao):
    return db.scalars(select(Usuario).order_by(Usuario.nome)).all()


@users_router.post("", response_model=UsuarioSaida, status_code=status.HTTP_201_CREATED, summary="Cria um usuário")
def criar(dados: UsuarioCriar, _admin: Administrador, db: Sessao):
    try:
        return criar_usuario(db, dados)
    except ErroEmailJaCadastrado:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um usuário com esse e-mail.") from None


@users_router.patch("/{usuario_id}", response_model=UsuarioSaida, summary="Edita, ativa/desativa ou redefine a senha")
def atualizar(usuario_id: int, dados: UsuarioAtualizar, admin: Administrador, db: Sessao):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    if usuario.id == admin.id and (dados.ativo is False or dados.admin is False):
        # senão o último administrador poderia se trancar para fora
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Você não pode desativar nem rebaixar a si mesmo.")
    if dados.nome is not None:
        usuario.nome = dados.nome
    if dados.ativo is not None:
        usuario.ativo = dados.ativo
    if dados.admin is not None:
        usuario.admin = dados.admin
    if dados.nova_senha is not None:
        usuario.senha_hash = gerar_hash(dados.nova_senha)  # derruba os logins antigos desse usuário
    db.commit()
    return usuario
