# openclaw_bootstrap.sh (Overdrive Variant)
# OpenClaw v2.1 Idempotent Bootstrap & State Scaffolding Script
# Deploys complete Elkin ecosystem to /root/.openclaw/
#
# Usage:
#   bash openclaw_bootstrap.sh
#
# Environment (must be set):
#   GITHUB_TOKEN      - GitHub Personal Access Token (for cloning private repos)
#   Ollama            - Must be running (systemd: ollama.service)
#   Python 3.10+      - Must be installed
#
# Deployment:
#   - /root/.openclaw/             Main directory
#   - /root/.openclaw/workspace/   Overdrive Matrix & State Vault
#   - /root/.openclaw/openclaw-brain/ (cloned from GitHub)
#   - /root/.openclaw/logs/          Log directory
#   - /etc/systemd/system/          systemd service
#   - /root/.openclaw/cron/          Cron job scripts
#
# This script is idempotent — safe to run multiple times.
###############################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_HOME="/root/.openclaw"
BRAIN_REPO="https://github.com/reececoakes99/openclaw-brain-v2.git"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
log_section() { echo -e "\n${CYAN}=== $* ===${NC}\n"; }

###############################################################################
# PRE-CHECKS
###############################################################################

log_section "Pre-deployment Checks"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root"
fi

# Check Python
if ! command -v python3 &> /dev/null; then
   log_error "Python 3 not found. Install: apt-get install python3 python3-pip"
fi
log_info "Python: $(python3 --version)"

# Check Ollama service
if ! systemctl is-active --quiet ollama; then
   log_error "Ollama service not running. Start: systemctl start ollama"
fi
log_info "Ollama service: active"

# Check Ollama model
if ! ollama list | grep -q "ds-uncensored\|deepseek-r1"; then
   log_warn "No inference model found. Pulling deepseek-r1-abliterated:32b (this may take 10-15 minutes)..."
   ollama pull huihui_ai/deepseek-r1-abliterated:32b || log_error "Failed to pull model"
fi
log_info "Ollama model: ready"

# Test Ollama connectivity
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
   log_error "Cannot connect to Ollama API (http://localhost:11434)"
fi
log_info "Ollama API: reachable"

# Check git
if ! command -v git &> /dev/null; then
   log_error "git not found. Install: apt-get install git"
fi
log_info "git: available"

###############################################################################
# DIRECTORY STRUCTURE
###############################################################################

log_section "Creating Directory Structure"
mkdir -p "$OPENCLAW_HOME"/{logs,cron,reports,vault,workspace}
mkdir -p "$OPENCLAW_HOME"/openclaw-brain
mkdir -p /root/.ollama/models  # Ollama models directory
chmod 700 "$OPENCLAW_HOME"
log_info "Created $OPENCLAW_HOME with subdirectories"

###############################################################################
# MEMORY FILES
###############################################################################

log_section "Deploying Memory Files"

# These files should already exist (created by claude), but check
MEMORY_FILES=(
  "SOUL.md"
  "HEARTBEAT.md"
  "BOTS.md"
  "COST_GOVERNOR.md"
  "AUTOMATION_TRIGGERS.md"
  "REASONING.md"
  "CONFIDENCE_FRAMES.md"
)

for file in "${MEMORY_FILES[@]}"; do
  if [ ! -f "$OPENCLAW_HOME/workspace/$file" ]; then
     log_error "Memory file missing: $file. Copy from deployment source."
   fi
   log_info "✓ $file"
done

###############################################################################
# CLONE BRAIN REPOSITORY
###############################################################################

log_section "Cloning openclaw-brain-v2"

if [ -d "$OPENCLAW_HOME/openclaw-brain/.git" ]; then
  log_info "Repository already cloned, pulling latest..."
  cd "$OPENCLAW_HOME/openclaw-brain"
  git pull origin main || log_warn "git pull failed, continuing with existing repo"
else
  log_info "Cloning fresh from GitHub..."
  
  # Use GitHub token if available for private repos
  if [ -n "$GITHUB_TOKEN" ]; then
    REPO_URL="https://${GITHUB_TOKEN}@github.com/reececoakes99/openclaw-brain-v2.git"
  else
    REPO_URL="$BRAIN_REPO"
  fi
  
  git clone "$REPO_URL" "$OPENCLAW_HOME/openclaw-brain" || log_error "Failed to clone brain repository"
fi

cd "$OPENCLAW_HOME/openclaw-brain"
log_info "Repository cloned/updated: $(git rev-parse --short HEAD)"

###############################################################################
# PYTHON ENVIRONMENT
###############################################################################

log_section "Setting Up Python Environment"

# Create virtual environment if missing
if [ ! -d "$OPENCLAW_HOME/venv" ]; then
  log_info "Creating Python virtual environment..."
  python3 -m venv "$OPENCLAW_HOME/venv"
else
  log_info "Virtual environment already exists"
fi

source "$OPENCLAW_HOME/venv/bin/activate"
log_info "Activated venv"

# Upgrade pip
pip install --upgrade pip setuptools wheel > /dev/null 2>&1 || log_warn "pip upgrade failed"

# Install pipeline dependencies
if [ -f "$OPENCLAW_HOME/openclaw-brain/pipeline/requirements.txt" ]; then
  log_info "Installing pipeline dependencies..."
  pip install -r "$OPENCLAW_HOME/openclaw-brain/pipeline/requirements.txt" \
    --break-system-packages > /dev/null 2>&1 || log_warn "Some dependencies failed to install"
fi

# Install telegram gateway dependencies
pip install aiohttp httpx python-telegram-bot python-dotenv \
  --break-system-packages > /dev/null 2>&1 || log_warn "Gateway dependencies failed"

log_info "Python dependencies installed"

 ###############################################################################
 # OVERDRIVE STATE INITIALIZATION (CORE_INIT)
 ###############################################################################
 
 log_section "Executing Overdrive State Scaffolding"
 
 cat > "$OPENCLAW_HOME/core_init.py" << 'EOF'
 import os
 import sys
 import json
 import logging
 from datetime import datetime, timezone
 from pathlib import Path
 
 WORKSPACE_DIR = Path("/root/.openclaw/workspace")
 REQUIRED_DIRECTORIES = [
     "knowledge/targets/active",
     "knowledge/targets/strike_authorized",
     "knowledge/targets/archived",
     "knowledge/gateway_profiles",
     "knowledge/bot_activity_logs/recon",
     "knowledge/bot_activity_logs/intel",
     "knowledge/bot_activity_logs/hunter",
     "knowledge/bot_activity_logs/operations",
     "knowledge/bot_activity_logs/decoy",
     "knowledge/bot_activity_logs/archivist",
     "knowledge/bot_queue",
     "knowledge/archives_encrypted/pending_exfil",
     "knowledge/archives_encrypted/transmitted",
     "memory/procedures",
     "neopay/scripts"
 ]
 
 logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CORE-INIT] - %(levelname)s - %(message)s')
 logger = logging.getLogger(__name__)
 
 def build_directories():
     for dir_path in REQUIRED_DIRECTORIES:
         target_dir = WORKSPACE_DIR / dir_path
         target_dir.mkdir(parents=True, exist_ok=True)
     logger.info("Overdrive directory tree established.")
 
 def initialize_state_machine():
     health_file = WORKSPACE_DIR / "knowledge" / "bot_activity_logs" / "health_check.json"
     if not health_file.exists():
         initial_state = {
             "timestamp": datetime.now(timezone.utc).isoformat(),
             "system_state": "IDLE",
             "local_compute_cycles": 0,
             "bots": {
                 "recon": {"status": "idle"},
                 "intel": {"status": "idle"},
                 "hunter": {"status": "idle"},
                 "operations": {"status": "standby"},
                 "decoy": {"status": "standby"},
                 "archivist": {"status": "standby"}
             }
         }
         with open(health_file, 'w') as f:
             json.dump(initial_state, f, indent=2)
         logger.info("State machine initialized (6-Bot Fleet). System locked to IDLE.")
     else:
         logger.info("State machine already active. Skipping overwrite.")
 
 if __name__ == "__main__":
     build_directories()
     initialize_state_machine()
EOF
 
python3 "$OPENCLAW_HOME/core_init.py" || log_error "Failed to execute Python Overdrive scaffolding."
rm "$OPENCLAW_HOME/core_init.py"
log_info "Overdrive State Initialization Complete."

###############################################################################
# TELEGRAM GATEWAY
###############################################################################

log_section "Deploying Telegram Gateway"

# Copy gateway script if not present
if [ ! -f "$OPENCLAW_HOME/telegram_gateway.py" ]; then
  log_error "telegram_gateway.py not found in $OPENCLAW_HOME. Copy deployment file."
fi
chmod +x "$OPENCLAW_HOME/telegram_gateway.py"
log_info "✓ telegram_gateway.py"

###############################################################################
# SYSTEMD SERVICE
###############################################################################

log_section "Installing Systemd Service"

if [ -f "/etc/systemd/system/openclaw-brain.service" ]; then
  log_warn "Service already installed, updating..."
  systemctl stop openclaw-brain || true
fi

cp "$SCRIPT_DIR/openclaw-brain.service" /etc/systemd/system/
chmod 644 /etc/systemd/system/openclaw-brain.service
systemctl daemon-reload
log_info "✓ openclaw-brain.service installed"

###############################################################################
# ENVIRONMENT FILE
###############################################################################

log_section "Creating .env File"

ENV_FILE="$OPENCLAW_HOME/.env"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" << 'EOF'
# OpenClaw v2.0 Environment Configuration
GITHUB_PAT=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=huihui_ai/deepseek-r1-abliterated:32b
PYTHONUNBUFFERED=1
EOF
  chmod 600 "$ENV_FILE"
  log_info "✓ Created $ENV_FILE"
else
  log_info "✓ $ENV_FILE already exists"
fi

###############################################################################
# CRON JOBS (Placeholder)
###############################################################################

log_section "Cron Job Setup"

mkdir -p "$OPENCLAW_HOME/cron"

# Create placeholder cron scripts (actual implementation depends on pipeline)
cat > "$OPENCLAW_HOME/cron/heartbeat.sh" << 'EOF'
#!/bin/bash
# Heartbeat check — confirm agent is alive
systemctl is-active --quiet openclaw-brain && echo "$(date): heartbeat OK" || echo "$(date): heartbeat FAIL"
EOF
chmod +x "$OPENCLAW_HOME/cron/heartbeat.sh"

log_info "✓ Cron infrastructure ready (implement via brain playbooks)"

###############################################################################
# START SERVICE
###############################################################################

log_section "Starting Elkin Agent"

systemctl enable openclaw-brain
systemctl start openclaw-brain
sleep 2

if systemctl is-active --quiet openclaw-brain; then
  log_info "✓ openclaw-brain service started"
else
  log_warn "Service may have failed to start. Check: systemctl status openclaw-brain"
fi

###############################################################################
# VERIFY DEPLOYMENT
###############################################################################

log_section "Deployment Verification"

# Check port
if netstat -tuln 2>/dev/null | grep -q ":18789"; then
  log_info "✓ Dashboard listening on port 18789"
else
  log_warn "Port 18789 not listening yet (may take a moment)"
fi

# Check logs
LATEST_LOG=$(systemctl status openclaw-brain | head -20)
if echo "$LATEST_LOG" | grep -q "active (running)"; then
  log_info "✓ Service is running"
else
  log_warn "Service status unclear. Check: journalctl -u openclaw-brain -n 50"
fi

# Confirm memory files in place
 if [ -f "$OPENCLAW_HOME/workspace/SOUL.md" ] && [ -f "$OPENCLAW_HOME/workspace/HEARTBEAT.md" ]; then
  log_info "✓ Memory files deployed"
else
  log_error "Memory files not found"
fi

###############################################################################
# POST-DEPLOYMENT INSTRUCTIONS
###############################################################################

log_section "Deployment Complete! 🔱"

echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Set up Tailscale (optional, for secure remote access):"
echo "   sudo tailscale up"
echo ""
echo "2. Get your first dashboard token via Telegram:"
echo "   - Send message to @Elkinlochbot: /token"
echo "   - Copy the token and visit: http://<instance-ip>:18789/dashboard?token=<token>"
echo ""
echo "3. Check agent logs:"
echo "   systemctl status openclaw-brain"
echo "   journalctl -u openclaw-brain -f"
echo ""
echo "4. Test Ollama model:"
echo "   curl -s http://localhost:11434/api/generate -d '{\"model\":\"huihui_ai/deepseek-r1-abliterated:32b\",\"prompt\":\"test\",\"stream\":false}' | jq ."
echo ""
echo "5. List available Telegram commands:"
echo "   Send /help to @Elkinlochbot"
echo ""
echo "Configuration Files:"
echo "  Memory:      $OPENCLAW_HOME/workspace/{SOUL,HEARTBEAT,BOTS,COST_GOVERNOR}.md"
echo "  Environment: $OPENCLAW_HOME/.env"
echo "  Gateway:     $OPENCLAW_HOME/telegram_gateway.py"
echo "  Service:     /etc/systemd/system/openclaw-brain.service"
echo "  Brain Repo:  $OPENCLAW_HOME/openclaw-brain/"
echo "  Logs:        $OPENCLAW_HOME/logs/"
echo ""
echo "Verify Agent Status:"
echo "  curl http://localhost:18789/"
echo "  systemctl status openclaw-brain"
echo ""
echo "==============="
