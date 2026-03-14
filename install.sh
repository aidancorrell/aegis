#!/usr/bin/env bash
# Aegis bootstrap — curl -fsSL https://aegis.dev/install | bash
set -euo pipefail

AEGIS_DIR="${AEGIS_DIR:-$HOME/aegis}"
PORT="${AEGIS_PORT:-8000}"

echo "🛡  Aegis Installer"
echo "========================"
echo ""

# Check dependencies
for dep in docker curl; do
  if ! command -v "$dep" &>/dev/null; then
    echo "❌ Required: $dep not found. Please install it first."
    exit 1
  fi
done

if ! docker compose version &>/dev/null 2>&1; then
  echo "❌ Docker Compose v2 required. Please install docker-compose-plugin."
  exit 1
fi

echo "✓ Dependencies OK"

# Create working directory
mkdir -p "$AEGIS_DIR"
cd "$AEGIS_DIR"

# Write docker-compose.yml
cat > docker-compose.yml << 'COMPOSE'
services:
  aegis:
    image: ghcr.io/aegis/aegis:latest
    ports:
      - "8000:8000"
    env_file: aegis.env
    volumes:
      - ./agent_config.json:/app/agent_config.json:ro
      - agent-workspace:/app/workspace
      - agent-audit:/app/audit
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=32M
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    mem_limit: 256m

volumes:
  agent-workspace:
  agent-audit:
COMPOSE

# Write default env
cat > aegis.env << 'ENV'
AEGIS_MODE=builtin
AEGIS_BLOCK_INJECTIONS=false
ENV

# Write default agent config (user will fill in API key via wizard)
cat > agent_config.json << 'AGENTCONFIG'
{
  "provider": "gemini",
  "api_key": "",
  "model": "gemini-2.5-flash",
  "system_prompt": "You are a helpful assistant with access to the web.",
  "tools": ["web_fetch"],
  "allowed_commands": [],
  "workspace_path": "/app/workspace"
}
AGENTCONFIG

echo ""
echo "📁 Aegis directory: $AEGIS_DIR"
echo ""

# Start the container
echo "🚀 Starting Aegis..."
docker compose pull --quiet 2>/dev/null || true
docker compose up -d

echo ""
echo "✓ Aegis is running!"
echo ""
echo "  Dashboard:   http://localhost:${PORT}"
echo "  Setup Wizard: http://localhost:${PORT}/wizard-page"
echo ""
echo "Open the wizard to configure your API keys and agent settings."
echo ""

# Open browser if possible
if command -v open &>/dev/null; then
  open "http://localhost:${PORT}/wizard-page"
elif command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:${PORT}/wizard-page"
fi
