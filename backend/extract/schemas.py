from pydantic import BaseModel


class ExtractOut(BaseModel):
    """O que a extração leu do PDF (a Leitura; o texto das páginas não é guardado, só a contagem)."""

    total_paginas: int
    paginas_lidas: int
    paginas_sem_texto: int  # só imagem (scan): não foram lidas
    percentual_sem_texto: float  # 0 a 1
    pouco_legivel: bool  # sem texto em tantas páginas que o resultado merece desconfiança (o mesmo corte do aviso)
