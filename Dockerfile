FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "apscheduler>=3.10" "uvicorn[standard]>=0.32"

COPY . /app
RUN mkdir -p /app/data/logs /app/data/raw /app/data/reports /app/data/memory /app/data/db_fallback

EXPOSE 8000 8001 8002 8003 8501

HEALTHCHECK --interval=30s --timeout=8s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; p=os.environ.get('PORT','8000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health')" || exit 1

# Default: presentation API; override per-service in compose
CMD ["python", "-m", "opinion_trading.services.api_app"]
