FROM python:3.12-slim

# System deps for lxml (HTML parsing) and asyncpg (PostgreSQL)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Install CPU-only PyTorch first (saves ~1.5 GB vs default CUDA build)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

RUN mkdir -p logs && chown appuser:appuser logs

USER appuser

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]