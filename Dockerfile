FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv pip install --system --no-cache .

# --- Runtime ---
FROM python:3.12-slim

ARG UID=1000
ARG GID=1000

RUN groupadd -g ${GID} clawshield && \
    useradd -u ${UID} -g ${GID} -s /bin/sh -m clawshield

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY static/ ./static/

# Create workspace and audit dirs
RUN mkdir -p /app/workspace /app/audit && \
    chown -R clawshield:clawshield /app

USER clawshield

EXPOSE 8000

CMD ["uvicorn", "clawshield.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
