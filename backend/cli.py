"""Gerência de usuários pela linha de comando (não precisa da API no ar).

    python -m backend.cli criar-usuario --email ana@exemplo.com --nome "Ana" --admin
    python -m backend.cli redefinir-senha --email ana@exemplo.com
    python -m backend.cli listar

A senha é pedida no terminal (não aparece na tela nem no histórico do shell).
"""

import argparse
import getpass
import sys

from pydantic import ValidationError
from sqlalchemy import select

from .autenticacao.funcoes import gerar_hash
from .nucleo import banco
from .nucleo.config import obter_configuracoes
from .nucleo.validacao import resumir_erros
from .processos import modelos as _modelos_processos  # noqa: F401  (a FK de processos precisa da tabela no metadata)
from .usuarios.erros import ErroEmailJaCadastrado
from .usuarios.funcoes import buscar_por_email, criar_usuario
from .usuarios.modelos import Usuario
from .usuarios.schemas import SENHA_MAXIMA, SENHA_MINIMA, UsuarioCriar


def _pedir_senha() -> str:
    """Pergunta até a senha servir. Nunca imprime o que foi digitado (nem em mensagem de erro)."""
    while True:
        senha = getpass.getpass(f"Senha (mínimo {SENHA_MINIMA} caracteres): ")
        if len(senha) < SENHA_MINIMA:
            print(f"A senha tem {len(senha)} caracteres; o mínimo é {SENHA_MINIMA}. Tente de novo.")
        elif len(senha) > SENHA_MAXIMA:
            print(f"A senha passa de {SENHA_MAXIMA} caracteres. Tente de novo.")
        elif senha != getpass.getpass("Repita a senha: "):
            print("As senhas não conferem. Tente de novo.")
        else:
            return senha


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    criar = sub.add_parser("criar-usuario")
    criar.add_argument("--email", required=True)
    criar.add_argument("--nome", required=True)
    criar.add_argument("--admin", action="store_true")
    redefinir = sub.add_parser("redefinir-senha")
    redefinir.add_argument("--email", required=True)
    sub.add_parser("listar")
    args = parser.parse_args(argv)

    config = obter_configuracoes()
    config.pasta_dados.mkdir(parents=True, exist_ok=True)
    motor = banco.criar_motor(config.url_do_banco)
    banco.Base.metadata.create_all(motor)
    with banco.criar_fabrica_sessoes(motor)() as db:
        if args.comando == "listar":
            for u in db.scalars(select(Usuario).order_by(Usuario.id)):
                print(f"{u.id:>3}  {u.email:<35} {u.nome:<25} {'admin' if u.admin else '     '} {'ativo' if u.ativo else 'DESATIVADO'}")
            return 0

        if args.comando == "criar-usuario":
            try:
                dados = UsuarioCriar(email=args.email, nome=args.nome, senha=_pedir_senha(), admin=args.admin)
                criar_usuario(db, dados)
            except ValidationError as erro:
                sys.exit(f"Dados inválidos: {resumir_erros(erro.errors())}")
            except ErroEmailJaCadastrado:
                sys.exit("Já existe um usuário com esse e-mail.")
            print(f"Usuário criado: {dados.email}{' (admin)' if dados.admin else ''}")
            return 0

        usuario = buscar_por_email(db, args.email)
        if usuario is None:
            sys.exit("Usuário não encontrado.")
        try:
            nova = UsuarioCriar(email=usuario.email, nome=usuario.nome, senha=_pedir_senha()).senha
        except ValidationError as erro:
            sys.exit(f"Dados inválidos: {resumir_erros(erro.errors())}")
        usuario.senha_hash = gerar_hash(nova)
        db.commit()
        print("Senha redefinida. Os logins antigos desse usuário deixam de valer.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
