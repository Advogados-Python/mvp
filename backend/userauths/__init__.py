"""Usuários e login: quem entra no sistema e o que cada pessoa pode ver.

    models.py    a tabela `usuarios`, o limitador de tentativas de login e o erro de e-mail repetido
    schemas.py   os formatos da API (usuário, senha, token)
    logic.py     senhas (Argon2), tokens JWT, link assinado do PDF, criar usuário, administrador inicial, erros de validação
    deps.py      as dependências do FastAPI: quem está logado, administrador, quem pede o PDF
    api.py       /api/auth (login, eu, senha) e /api/usuarios (administrador)
    cli.py       gerência de usuários pela linha de comando: python -m backend.userauths.cli
"""
