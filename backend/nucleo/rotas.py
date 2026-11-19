from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from .dependencias import Sessao

roteador = APIRouter(prefix="/api", tags=["geral"])


@roteador.get("/saude", summary="Confere se a API e o banco estão no ar (usado pelo healthcheck)")
def saude(db: Sessao):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Banco de dados indisponível.") from None
    return {"status": "ok"}
