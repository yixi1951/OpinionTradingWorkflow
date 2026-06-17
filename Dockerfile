FROM python:3.11-slim

WORKDIR /app

# install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# Create log and data directories
RUN mkdir -p /app/data/logs /app/data/raw /app/data/reports /app/data/memory

# Expose pipeline (no web) + WS proxy (health)
EXPOSE 8501
EXPOSE 18790

# Health check for the WS proxy — /health returns 200 if running
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; r=urllib.request.urlopen('http://localhost:18790/health'); assert r.status == 200, f'health check failed: {r.status}'" || exit 1

CMD ["python", "run_pipeline.py"]
