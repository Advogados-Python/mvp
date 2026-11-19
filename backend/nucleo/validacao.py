"""Erros de validação: mensagens em português e SEM o valor enviado.

O Pydantic/FastAPI incluem o valor recebido (`input`) nos erros. Se o campo for uma senha, ela apareceria em
texto puro no terminal (CLI) e no JSON do 422 (API), e iria parar em logs. Aqui o valor é sempre descartado.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def traduzir_erro(erro: dict) -> dict:
    """Devolve só {type, loc, msg}: sem `input`, `ctx` nem `url`."""
    tipo, ctx = erro.get("type", ""), erro.get("ctx") or {}
    if tipo == "string_too_short":
        msg = f"Precisa ter pelo menos {ctx.get('min_length')} caracteres."
    elif tipo == "string_too_long":
        msg = f"Pode ter no máximo {ctx.get('max_length')} caracteres."
    elif tipo == "missing":
        msg = "Campo obrigatório."
    elif tipo == "string_pattern_mismatch":
        msg = "Formato inválido."
    else:
        msg = erro.get("msg", "Valor inválido.")
    return {"type": tipo, "loc": list(erro.get("loc", ())), "msg": msg}


def traduzir_erros(erros) -> list:
    return [traduzir_erro(erro) for erro in erros]


def resumir_erros(erros) -> str:
    """Uma linha legível, para o terminal: 'senha: Precisa ter pelo menos 10 caracteres.'"""
    return "; ".join(f"{'.'.join(str(parte) for parte in e['loc'])}: {e['msg']}" for e in traduzir_erros(erros))


async def tratar_erro_de_validacao(_requisicao: Request, erro: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": traduzir_erros(erro.errors())})
