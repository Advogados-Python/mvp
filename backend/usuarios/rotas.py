from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..autenticacao.dependencias import Administrador
from ..autenticacao.funcoes import gerar_hash
from ..nucleo.dependencias import Sessao
from .erros import ErroEmailJaCadastrado
from .funcoes import criar_usuario
from .modelos import Usuario
from .schemas import UsuarioAtualizar, UsuarioCriar, UsuarioSaida

roteador = APIRouter(prefix="/api/usuarios", tags=["usuários (administrador)"])


@roteador.get("", response_model=list[UsuarioSaida], summary="Lista os usuários")
def listar(_admin: Administrador, db: Sessao):
    return db.scalars(select(Usuario).order_by(Usuario.nome)).all()


@roteador.post("", response_model=UsuarioSaida, status_code=status.HTTP_201_CREATED, summary="Cria um usuário")
def criar(dados: UsuarioCriar, _admin: Administrador, db: Sessao):
    try:
        return criar_usuario(db, dados)
    except ErroEmailJaCadastrado:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um usuário com esse e-mail.") from None


@roteador.patch("/{usuario_id}", response_model=UsuarioSaida, summary="Edita, ativa/desativa ou redefine a senha")
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
