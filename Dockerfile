# API (FastAPI) + leitor de processos. Build a partir da RAIZ do projeto:
#   docker build -t ribeiro-api .
# Em produção use Postgres (DATABASE_URL) e monte um volume em /data (é onde ficam os PDFs enviados).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Dependências primeiro: a camada fica em cache enquanto o requirements.txt não mudar.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ backend/

# Usuário sem privilégios; /data é a pasta de dados (PDFs, e o SQLite se não houver Postgres).
RUN useradd --system --uid 1001 --home-dir /srv ribeiro && mkdir -p /data && chown ribeiro:ribeiro /data
USER ribeiro

ENV RIBEIRO_AMBIENTE=producao \
    RIBEIRO_PASTA_DADOS=/data \
    PORT=8000
# Sem a instrução VOLUME: o Railway recusa o build com ela ("use Railway Volumes"). O volume é montado de fora:
# no docker-compose (dados:/data) e no Railway (volume do serviço em /data, com RAILWAY_RUN_UID=0, pois ele monta como root).
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/saude' % os.environ.get('PORT', '8000'), timeout=4)"

# UM worker: a fila de análises vive na memória do processo (veja backend/pipeline.py).
# --timeout-graceful-shutdown: abas acompanhando uma análise mantêm uma conexão SSE aberta; sem o limite, um deploy esperaria por elas.
# Atrás de proxy (Railway), defina FORWARDED_ALLOW_IPS=* para o limite de tentativas de login enxergar o IP real.
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-graceful-shutdown 10"]
