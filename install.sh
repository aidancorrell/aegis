#!/usr/bin/env bash
# ClawShield bootstrap — curl -fsSL https://clawshield.dev/install | bash
set -euo pipefail

CLAWSHIELD_DIR="${CLAWSHIELD_DIR:-$HOME/clawshield}"
PORT="${CLAWSHIELD_PORT:-8000}"

echo "🛡  ClawShield Installer"
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
mkdir -p "$CLAWSHIELD_DIR"
cd "$CLAWSHIELD_DIR"

# Write docker-compose.yml
cat > docker-compose.yml << 'COMPOSE'
services:
  clawshield:
    image: ghcr.io/clawshield/clawshield:latest
    ports:
      - "8000:8000"
    env_file: clawshield.env
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
cat > clawshield.env << 'ENV'
CLAWSHIELD_MODE=builtin
CLAWSHIELD_BLOCK_INJECTIONS=false
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
echo "📁 ClawShield directory: $CLAWSHIELD_DIR"
echo ""

# Start the container
echo "🚀 Starting ClawShield..."
docker compose pull --quiet 2>/dev/null || true
docker compose up -d

echo ""
echo "✓ ClawShield is running!"
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
