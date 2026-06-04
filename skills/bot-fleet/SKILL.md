# bot-fleet — RECON/INTEL/HUNTER/OPERATIONS Bot Loop Manager

---

## Overview

The bot-fleet skill manages the four-bot intelligence pipeline for persistent payment gateway discovery, scoring, exploitation, and operational execution. Each bot operates independently with shared context via the knowledge base, continuous feedback loops, and autonomous decision trees.

**Bot Hierarchy:**
```
ELKIN COMMANDER
    └── RECON ── INTEL ── HUNTER ── OPERATIONS
              └───── KNOWLEDGE BASE ────┘
```

---

## Trigger Conditions

Activate bot-fleet when:
- Agent session starts → initialize all bot health checks
- New target discovered by RECON → INTEL receives queue
- INTEL scores P1/P2 target → HUNTER receives queue
- HUNTER completes exploit package → OPERATIONS receives queue
- Operator sends `BOT STATUS` command via Telegram
- Any bot fails → trigger restart procedure
- Heartbeat monitor (every 5 minutes) detects stale bot

---

## Bot Communication Protocol

Each bot writes output to the knowledge base and signals the next bot via queue files in `knowledge/bot_queue/`:

| Signal File | From | To | Trigger |
|---|---|---|---|
| `recon_pending.json` | RECON | INTEL | New target discovered |
| `intel_scored.json` | INTEL | HUNTER | Target scored P1-P2 |
| `hunter_ready.json` | HUNTER | OPERATIONS | Attack package complete |
| `ops_complete.json` | OPERATIONS | INTEL | Feedback loop |
| `escalation.json` | Any | OPERATIONS + Reece | P1 confirmed, critical event |

---

## Pre-Operation: Bot Fleet Initialization

### Step 1 — Verify Knowledge Base Structure
```bash
# Check all required directories exist
for dir in knowledge/targets knowledge/gateway_profiles \
  knowledge/bot_activity_logs knowledge/bot_queue; do
  [ -d "$dir" ] || mkdir -p "$dir"
done

# Create subdirectories if missing
mkdir -p knowledge/bot_activity_logs/{recon,intel,hunter,operations}
```

### Step 2 — Load Bot Health State
```bash
# Read current health state
cat knowledge/bot_activity_logs/health_check.json

# Expected format:
# {
#   "timestamp": "ISO8601",
#   "recon": {"status": "active|idle|error", "last_run": "ISO8601", ...},
#   "intel": {"status": "active|idle|error", "last_run": "ISO8601", ...},
#   "hunter": {"status": "active|idle|error", "last_run": "ISO8601", ...},
#   "operations": {"status": "standby|active|error", ...}
# }
```

### Step 3 — Start Bot Services
```bash
# RECON Bot — 60-second passive cycle (always running)
nohup python3 neopay/scripts/cert_scan.py \
  >> knowledge/bot_activity_logs/recon/cert_scan.log 2>&1 &

# ACTIVE RECON — hourly cycle
nohup python3 neopay/scripts/active_recon.py \
  >> knowledge/bot_activity_logs/recon/active_recon.log 2>&1 &

# DEEP RECON — daily at 3AM UTC
nohup python3 neopay/scripts/deep_scan.py \
  >> knowledge/bot_activity_logs/recon/deep_scan.log 2>&1 &
```

---

## RECON Bot Cycle

### Step 1 — Passive Discovery (60-second cycle)
```bash
# Certificate Transparency scan
python3 neopay/scripts/cert_scan.py

# Payment keywords:
# payment, gateway, checkout, stripe, braintree, adyen
# shopify, woocommerce, magento, square, paypal
# card, transaction, merchant, pos, terminal, acquiring, processor
```

### Step 2 — Update Knowledge Base
```bash
# Write discovery to gateway profile
TARGET="discovered.domain.com"
mkdir -p "knowledge/gateway_profiles/$TARGET"

cat > "knowledge/gateway_profiles/$TARGET/surface_scan.json" << 'EOF'
{
  "discovered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "domain": "<domain>",
  "ports": [],
  "tech_stack": {},
  "surface": {"endpoints": [], "admin_panel": false},
  "cert_info": {},
  "threat_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "notes": "",
  "scan_layer": "PASSIVE|ACTIVE|DEEP"
}
EOF
```

### Step 3 — Queue to INTEL
```bash
# Append to recon_pending.json
python3 -c "
import json
queue_file = 'knowledge/bot_queue/recon_pending.json'
with open(queue_file, 'a+') as f:
    f.write(json.dumps(new_target) + '\n')
"
```

---

## INTEL Bot Cycle

### Step 1 — Score Incoming Targets
```bash
# Run intel scoring engine
python3 neopay/scripts/intel_bot.py

# Scoring formula:
# Priority = (ThreatSurface × Exploitability × TargetValue × ExposureLevel) / 100
# Thresholds:
#   700+ = P1 CRITICAL → Immediate HUNTER escalation
#   400-699 = P2 HIGH → HUNTER queue, 24h target
#   200-399 = P3 MEDIUM → Monitor + monthly deep scan
#   100-199 = P4 LOW → Archive + quarterly review
```

### Step 2 — Correlation Check
```bash
# Cross-reference NVD, breach databases, dark web
python3 neopay/scripts/correlation_engine.py

# If domain appears in breach data → P1 escalation
# If CVE published for target platform → update score
```

### Step 3 — Queue to HUNTER
```bash
# Write scored target to hunter_queue.json
TARGET="domain.com"
SCORE=$(python3 -c "import json; d=json.load(open('knowledge/bot_queue/intel_scored.json')); print(d['score'])")

# If score >= 400 (P1/P2), queue for HUNTER
if [ "$SCORE" -ge 400 ]; then
  cp "knowledge/bot_queue/intel_scored.json" \
     "knowledge/bot_queue/hunter_queue.json"
fi
```

---

## HUNTER Bot Cycle

### Step 1 — Load Engagement Package
```bash
TARGET="domain.com"
PROFILE_DIR="knowledge/gateway_profiles/$TARGET"

# Load all profile files
ls "$PROFILE_DIR"/*.json

# Verify required files exist
for f in surface_scan.json tech_stack.json attack_vectors.json; do
  [ -f "$PROFILE_DIR/$f" ] || { echo "Missing: $f"; exit 1; }
done
```

### Step 2 — Build Exploit Package
```bash
# Run hunter exploitation engine
python3 neopay/scripts/hunter_bot.py --target "$TARGET"

# Create engagement_prep directory
mkdir -p "$PROFILE_DIR/engagement_prep/payload_templates"
mkdir -p "$PROFILE_DIR/engagement_prep/evidence"
```

### Step 3 — Document and Queue to OPERATIONS
```bash
# Write playbook.yaml
cat > "$PROFILE_DIR/engagement_prep/playbook.yaml" << 'YAML'
phase_1:
  name: "surface_testing"
  vectors:
    - web_injection
    - auth_bypass
    - business_logic
phase_2:
  name: "protocol_testing"
  vectors:
    - iso8583_fuzzing
    - api_exploitation
    - webhook_hijack
phase_3:
  name: "persistence"
  mechanisms:
    - admin_account
    - api_key
    - webhook_backdoor
YAML

# Queue to OPERATIONS
cp "$PROFILE_DIR/engagement_prep/playbook.yaml" \
   "knowledge/bot_queue/ops_ready.json"
```

---

## OPERATIONS Bot Cycle

### Step 1 — Verify Authorization
```bash
# Load engagement config
CONFIG=$(cat pipeline/engagement_config.json)
AUTHORIZED=$(echo "$CONFIG" | jq -r '.authorized_domains[]')
TARGET="domain.com"

if ! echo "$AUTHORIZED" | grep -q "^$TARGET$"; then
  echo "TARGET NOT AUTHORIZED — ABORT"
  exit 1
fi
```

### Step 2 — Pre-Mission Brief
```bash
# Send to Telegram
python3 -c "
import os, requests, json
msg = '''🔱 PRE-MISSION BRIEF — $TARGET

Target: $TARGET
Gateway: <type>
Priority: <P1-P5>
Score: <score>

Awaiting Reece authorization.'''
requests.post(
  f'https://api.telegram.org/bot{os.getenv(\"TELEGRAM_BOT_TOKEN\")}/sendMessage',
  json={'chat_id': os.getenv('TELEGRAM_CHAT_ID'), 'text': msg}
)
"
```

### Step 3 — Execute Stages 1-6
```bash
# Stage 1: Recon validation (3-5 min)
# Stage 2: Initial access (5-15 min)
# Stage 3: Persistence establishment (5-10 min)
# Stage 4: Escalation (10-20 min)
# Stage 5: Data extraction (15-30 min)
# Stage 6: Cleanup (5-10 min)

# Run full operations cycle
python3 neopay/scripts/operations_bot.py \
  --target "$TARGET" \
  --engagement "$ENGAGEMENT_NAME"
```

---

## Bot Heartbeat Monitoring (Every 5 Minutes)

### Step 1 — Heartbeat Check Script
```bash
cat > /usr/local/bin/bot_heartbeat.sh << 'BASH'
#!/bin/bash
LOG="knowledge/bot_activity_logs/health_check.json"
MAX_AGE=600  # 10 minutes max age

for bot in recon intel hunter operations; do
  last=$(jq -r ".$bot.last_run // empty" "$LOG" 2>/dev/null)
  if [ -z "$last" ]; then
    echo "ERROR: No last_run for $bot"
    continue
  fi

  age=$(($(date +%s) - $(date -d "$last" +%s)))
  if [ "$age" -gt "$MAX_AGE" ]; then
    echo "ALERT: $bot is stale (${age}s old)"
    # Trigger restart
    python3 neopay/scripts/restart_bot.py --bot "$bot"
  fi
done
BASH
chmod +x /usr/local/bin/bot_heartbeat.sh
```

### Step 2 — Cron Heartbeat Entry
```bash
# Add to crontab
(crontab -l 2>/dev/null | grep -v bot_heartbeat; \
  echo "*/5 * * * * /usr/local/bin/bot_heartbeat.sh") | crontab -
```

---

## Bot Failure Detection and Restart

### Step 1 — Detect Failure
```bash
# Check if bot process is running
ps aux | grep "cert_scan.py" | grep -v grep || \
  { echo "RECON BOT DOWN"; trigger_restart "recon"; }

ps aux | grep "intel_bot.py" | grep -v grep || \
  { echo "INTEL BOT DOWN"; trigger_restart "intel"; }
```

### Step 2 — Restart Procedure
```bash
# restart_bot.py
#!/usr/bin/env python3
import subprocess, sys, time, os

def restart_bot(bot_name):
    scripts = {
        "recon": "neopay/scripts/cert_scan.py",
        "intel": "neopay/scripts/intel_bot.py",
        "hunter": "neopay/scripts/hunter_bot.py",
        "operations": "neopay/scripts/operations_bot.py",
    }
    log_file = f"knowledge/bot_activity_logs/{bot_name}/error.log"

    # Kill any zombie process
    subprocess.run(f"pkill -f {scripts[bot_name]}", shell=True)
    time.sleep(2)

    # Restart
    subprocess.Popen(
        ["python3", scripts[bot_name]],
        stdout=open(f"knowledge/bot_activity_logs/{bot_name}/run.log", "a"),
        stderr=open(log_file, "a"),
        cwd="/root/.nanobot/workspace/openclaw-brain-v2"
    )

    # Update health check
    update_health(bot_name, "active")

if __name__ == "__main__":
    restart_bot(sys.argv[1])
```

### Step 3 — Telegram Escalation on Failure
```bash
# On bot failure, send alert
python3 -c "
import os, requests
msg = '🚨 BOT FAILURE ALERT\nBot: <bot_name>\nAction: Auto-restart initiated\nTime: <timestamp>'
requests.post(
  f'https://api.telegram.org/bot{os.getenv(\"TELEGRAM_BOT_TOKEN\")}/sendMessage',
  json={'chat_id': os.getenv('TELEGRAM_CHAT_ID'), 'text': msg}
)
"
```

---

## Cron Scheduling

### Step 1 — Install Cron Entries
```bash
# RECON Bot — 60 second cycle
(crontab -l 2>/dev/null | grep -v 'cert_scan.py\|active_recon.py\|deep_scan.py'; \
  echo '* * * * * cd /root/.nanobot/workspace/openclaw-brain-v2 && python3 neopay/scripts/cert_scan.py >> knowledge/bot_activity_logs/recon/cert_scan.log 2>&1'; \
  echo '0 * * * * cd /root/.nanobot/workspace/openclaw-brain-v2 && python3 neopay/scripts/active_recon.py >> knowledge/bot_activity_logs/recon/active_recon.log 2>&1'; \
  echo '0 3 * * * cd /root/.nanobot/workspace/openclaw-brain-v2 && python3 neopay/scripts/deep_scan.py >> knowledge/bot_activity_logs/recon/deep_scan.log 2>&1') | crontab -

# INTEL Bot — every 4 hours
(crontab -l 2>/dev/null | grep -v 'intel_bot.py\|intel_p1_check.py'; \
  echo '0 */4 * * * cd /root/.nanobot/workspace/openclaw-brain-v2 && python3 neopay/scripts/intel_bot.py >> knowledge/bot_activity_logs/intel/intel.log 2>&1'; \
  echo '*/15 * * * * cd /root/.nanobot/workspace/openclaw-brain-v2 && python3 neopay/scripts/intel_p1_check.py >> knowledge/bot_activity_logs/intel/p1_check.log 2>&1') | crontab -

# HUNTER Bot — every 6 hours (daily for non-P1)
(crontab -l 2>/dev/null | grep -v 'hunter_bot.py'; \
  echo '0 */6 * * * cd /root/.nanobot/workspace/openclaw-brain-v2 && python3 neopay/scripts/hunter_bot.py >> knowledge/bot_activity_logs/hunter/hunter.log 2>&1') | crontab -

# OPERATIONS Bot — on-demand only (no cron, triggered manually)
```

---

## Activity Logging

### Step 1 — LOG.md Format
```bash
# Write to knowledge/bot_activity_logs/LOG.md
cat >> "knowledge/bot_activity_logs/LOG.md" << 'EOF'
## $(date -u +%Y-%m-%d %H:%M UTC)

### RECON
- 13:00: Scanned 45 domains via CRT
- 13:01: Discovered new target: pay[REDACTED].com
- 13:02: Queued to INTEL

### INTEL
- 12:00: Scored 12 targets
- 12:01: P1 triggered: gateway[REDACTED].com (score: 750)
- 12:02: Queued P1 to HUNTER

### HUNTER
- 11:30: Built exploit package for gateway[REDACTED].com
- 11:35: Payload templates ready

### OPERATIONS
- standby
EOF
```

---

## Troubleshooting

| Error | Diagnosis | Fix |
|---|---|---|
| `cert_scan.py` fails | API rate limit or network | Check shodan/censys API keys in `.env` |
| INTEL scores 0 targets | Empty recon queue | Verify RECON is running, check queue file |
| HUNTER no profile | Gateway profile missing | Run `surface_scan.py` on target first |
| OPERATIONS aborts | Target not authorized | Add to `authorized_domains` in config |
| Bot zombie processes | PID file mismatch | Run `pkill -f bot_script.py` then restart |
| Heartbeat false alarm | Clock skew | Sync NTP: `ntpdate pool.ntp.org` |
| Telegram notifications fail | Token invalid | Verify `TELEGRAM_BOT_TOKEN` in `.env` |

---

## Cross-References

- **BOTS.md** — Master bot fleet documentation
- **bot_recon.md** — RECON bot detailed cycle
- **bot_intel.md** — INTEL bot scoring engine
- **bot_hunter.md** — HUNTER bot exploitation
- **bot_operations.md** — OPERATIONS bot execution
- **pipeline/master_pipeline.py** — Pipeline orchestrator
