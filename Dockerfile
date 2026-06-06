# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12

# ---------- builder ----------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---------- runtime ----------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLASK_CONFIG=production \
    PORT=8000

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        tini \
        curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1000 servicedesk \
 && useradd  --system --uid 1000 --gid servicedesk --home /app --shell /sbin/nologin servicedesk \
 && mkdir -p /app /app/instance /app/uploads \
 && chown -R servicedesk:servicedesk /app

COPY --from=builder /install /usr/local
WORKDIR /app

COPY --chown=servicedesk:servicedesk . /app

USER servicedesk

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker/entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]

# Allow `flask db ...` and other CLI commands to work inside the image.
ENV FLASK_APP=cli.py
