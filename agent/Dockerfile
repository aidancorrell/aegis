FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent source
COPY . .

# Volumes: audit log + workspace (both mounted by docker-compose)
VOLUME ["/app/audit", "/app/workspace"]

# Agent config mounted read-only by docker-compose
# AGENT_CONFIG_PATH defaults to /app/agent_config.json

# Web chat
EXPOSE 8001

CMD ["python", "main.py"]
