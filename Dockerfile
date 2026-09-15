FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fabrique/ ./fabrique/

RUN useradd --create-home --uid 1000 fabrique
USER fabrique

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/sante')"

CMD ["uvicorn", "fabrique.api:app", "--host", "0.0.0.0", "--port", "8000"]
