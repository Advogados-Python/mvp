from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..nucleo.dependencias import Sessao
from ..usuarios.modelos import Usuario
from .constantes import TIPO_ACESSO, TIPO_PDF
from .funcoes import decodificar, erro_401, token_vale_para

# auto_error=False: quem responde 401 somos nós, com a mensagem em português e o cabeçalho WWW-Authenticate.
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _usuario_do_token(request: Request, db: Session, token: str, tipo: str) -> tuple:
    dados = decodificar(token, request.app.state.segredo, tipo)
    try:
        usuario = db.get(Usuario, int(dados["sub"]))
    except ValueError:
        usuario = None
    if not token_vale_para(usuario, dados):  # inexistente, desativado ou senha trocada depois do login
        raise erro_401()
    return usuario, dados


def usuario_atual(request: Request, db: Sessao, token: Annotated[Optional[str], Depends(esquema_oauth2)]) -> Usuario:
    if not token:
        raise erro_401("Faça login para continuar.")
    return _usuario_do_token(request, db, token, TIPO_ACESSO)[0]


def usuario_do_pdf(
    request: Request,
    db: Sessao,
    processo_id: str,
    token: Annotated[Optional[str], Depends(esquema_oauth2)],
    assinatura: Annotated[Optional[str], Query(description="Link assinado devolvido por POST /pdf-link")] = None,
) -> Usuario:
    """O PDF abre numa nova aba, que não envia o cabeçalho Authorization: aceita o login normal OU um link
    assinado de vida curta que vale só para este processo."""
    if assinatura:
        usuario, dados = _usuario_do_token(request, db, assinatura, TIPO_PDF)
        if dados.get("pid") != processo_id:
            raise erro_401("Link do PDF inválido.")
        return usuario
    return usuario_atual(request, db, token)


def admin_atual(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    if not usuario.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas administradores podem fazer isso.")
    return usuario


UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]
Administrador = Annotated[Usuario, Depends(admin_atual)]
