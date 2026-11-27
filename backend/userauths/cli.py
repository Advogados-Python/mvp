"""Gerência de usuários pela linha de comando (não precisa da API no ar).

    python -m backend.userauths.cli criar-usuario --email ana@exemplo.com --nome "Ana" --admin
    python -m backend.userauths.cli redefinir-senha --email ana@exemplo.com
    python -m backend.userauths.cli listar
    python -m backend.userauths.cli ativar-usuario --email ana@exemplo.com     # reativa uma conta desativada

A senha é pedida no terminal (não aparece na tela nem no histórico do shell).
No Railway:  railway ssh --service backend  e, lá dentro, o mesmo comando.
"""

import argparse
import getpass
import sys

from pydantic import ValidationError
from sqlalchemy import select

from .. import db as banco
from ..config import obter_configuracoes
from ..receive import models as _modelos_processos  # noqa: F401  (a FK de processos precisa da tabela no metadata)
from .logic import adicionar_colunas_novas, buscar_por_email, criar_usuario, gerar_hash, resumir_erros
from .models import ErroEmailJaCadastrado, Usuario
from .schemas import SENHA_MAXIMA, SENHA_MINIMA, UsuarioCriar


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
    ativar = sub.add_parser("ativar-usuario", help="reativa uma conta desativada")
    ativar.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    config = obter_configuracoes()
    config.pasta_dados.mkdir(parents=True, exist_ok=True)
    motor = banco.criar_motor(config.url_do_banco)
    banco.Base.metadata.create_all(motor)
    adicionar_colunas_novas(motor)  # a CLI pode rodar antes de a API subir com a coluna nova
    with banco.criar_fabrica_sessoes(motor)() as db:
        if args.comando == "listar":
            for u in db.scalars(select(Usuario).order_by(Usuario.id)):
                situacao = "ativo" if u.ativo else "INATIVO"
                print(f"{u.id:>3}  {u.email:<35} {u.nome:<25} {u.oab or '-':<10} {'admin' if u.admin else '     '} {situacao}")
            return 0

        if args.comando == "ativar-usuario":
            usuario = buscar_por_email(db, args.email)
            if usuario is None:
                sys.exit("Usuário não encontrado.")
            if usuario.ativo:
                print(f"{usuario.email} já estava ativo.")
                return 0
            usuario.ativo = True
            db.commit()
            print(f"Conta reativada: {usuario.email} ({usuario.nome}, OAB {usuario.oab or '-'}). Já pode entrar.")
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
