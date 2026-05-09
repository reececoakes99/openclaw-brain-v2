# SKILL: telegram-alert

**Name**: Real-Time Communications with Reece via Telegram Bot  
**Type**: Notification / Command Interface  
**Trigger**: Startup, alert generation, command received from Reece, health check  
**Confidence**: OPERATIONAL — Fully implemented  

---

## 1. PURPOSE & SCOPE

This skill manages bidirectional Telegram communication between the agent and Reece. It handles alert dispatch (heartbeat, finding, escalation, completion, error), incoming command parsing, interactive menus, rate limiting, queueing, and group messaging. All Telegram operations should flow through this skill unless explicitly overridden.

**References**: See `TOOLS.md` for bot token and chat ID configuration. See `HEARTBEAT.md` for heartbeat message format standards.

---

## 2. CONFIGURATION

### 2.1 Required Environment Variables

```bash
# Bot credentials — set in environment or .env file
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789
TELEGRAM_CHAT_ID=-1001234567890       # Primary (group or individual)
TELEGRAM_SECONDARY_CHAT_ID=-1009876543210  # Secondary group (optional)
TELEGRAM_ALERT_COOLDOWN=60             # Minimum seconds between non-critical alerts
```

### 2.2 Directory Structure

```
knowledge/
  alerts/
    pending/          # Queued alerts when Telegram is unreachable
    sent/             # Log of sent alerts (last 30 days)
  bot_state/
    last_heartbeat.txt
    command_history.json
```

---

## 3. ALERT TYPES & MESSAGE FORMAT

### 3.1 Alert Types

| Type | Emoji | When to Use | Priority |
|------|-------|-------------|----------|
| `heartbeat` | 💓 | Regular status update, agent startup, periodic check-in | LOW |
| `finding` | 🔍 | Important discovery, significant result | MEDIUM |
| `escalation` | 🚨 | Critical issue requiring immediate attention | HIGH |
| `completion` | ✅ | Engagement or task completed successfully | LOW |
| `error` | ❌ | System failure, unhandled exception | HIGH |

### 3.2 Standard Message Format

Every alert MUST follow this format:

```
{EMOJI} [{ALERT_TYPE}] {target_name or "SYSTEM"}

{Brief summary of what happened in 1-2 sentences.}

📎 Evidence: {link to file, log entry, or screenshot}
⏱ Timestamp: {ISO8601}
🔖 ID: {uuid}
```

### 3.3 Example Messages

**Heartbeat — Agent Startup:**
```
💓 [HEARTBEAT] SYSTEM

Agent "OpenClaw-v2" started successfully on openclaw-brain-v2.
Loaded 8 skills, 4 brain files active.

📎 Brain: /root/.nanobot/workspace/openclaw-brain-v2/
⏱ 2026-05-09T07:30:00Z
🔖 ID: hb-7a3f2c91
```

**Finding — Discovered Open Port:**
```
🔍 [FINDING] acme-corp

SMB null session enumeration successful on 10.0.1.45.
Found 3 shares: PUBLIC, BACKUPS, IT_DEPT.

📎 Log: knowledge/gateway_profiles/acme-corp/evidence/smb_enum_20260509.log
📎 Hash: sha256:a3f8c9d2e1b4...
⏱ 2026-05-09T07:45:00Z
🔖 ID: find-4e82b171
```

**Escalation — Database Exposed:**
```
🚨 [ESCALATION] acme-corp

Internal PostgreSQL database found at 10.0.1.100:5432.
Contains customer PII — immediate sanitization required.

📎 Evidence: knowledge/gateway_profiles/acme-corp/evidence/
⏱ 2026-05-09T08:00:00Z
🔖 ID: esc-9d2c3e41
```

---

## 4. OPERATIONAL PROCEDURE

### Step 1 — Send Alert

```python
# Full implementation — copy to your agent code

import os
import json
import hashlib
import requests
from datetime import datetime
from pathlib import Path

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_SECONDARY_CHAT_ID", ""))
COOLDOWN = int(os.getenv("TELEGRAM_ALERT_COOLDOWN", "60"))

def send_alert(alert_type, target, summary, evidence_path=None, priority="LOW"):
    """Send Telegram alert with rate limiting and queue fallback."""
    
    # Rate limiting check
    if priority != "HIGH" and priority != "ESCALATION":
        last_send = _get_last_send_time(alert_type)
        if last_send and (datetime.now() - last_send).seconds < COOLDOWN:
            _log_warning(f"Rate limited: {alert_type} alert suppressed")
            return False
    
    # Build message
    emoji_map = {
        "heartbeat": "💓", "finding": "🔍", "escalation": "🚨",
        "completion": "✅", "error": "❌"
    }
    emoji = emoji_map.get(alert_type, "📌")
    
    msg_id = f"{alert_type[:3]}-{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"
    
    message = f"""{emoji} [{alert_type.upper()}] {target}

{summary}

📎 Evidence: {evidence_path or "N/A"}
⏱ {datetime.utcnow().isoformat()}Z
🔖 ID: {msg_id}"""

    # Attempt send
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        _log_last_send(alert_type, "sent")
        return True
    except Exception as e:
        _log_error(f"Telegram send failed: {e}")
        _queue_alert(message, alert_type)  # Queue to pending/
        return False

def _queue_alert(message, alert_type):
    """Queue failed alert for retry."""
    pending_dir = Path("knowledge/alerts/pending")
    pending_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{alert_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    (pending_dir / filename).write_text(message)

# Wrapper for shell use
def send_alert_shell(alert_type, target, summary, evidence=""):
    cmd = f'''curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \\
  -H "Content-Type: application/json" \\
  -d \'{{"chat_id":"$TELEGRAM_CHAT_ID","text":"...","parse_mode":"Markdown"}}\' '''
    print(f"[SKIP] Use Python implementation above for production")
```

### Step 2 — Receive Commands from Reece

```python
# Poll for updates (long polling — lightweight command interface)
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 30, "limit": 5}
    if offset:
        params["offset"] = offset
    
    resp = requests.get(url, params=params, timeout=35)
    data = resp.json()
    
    if data.get("ok"):
        return data.get("result", [])
    return []

def parse_commands():
    """Parse incoming commands from Reece."""
    updates = get_updates()
    commands = []
    
    for update in updates:
        msg = update.get("message", {})
        text = msg.get("text", "").strip()
        
        if text.startswith("/"):
            cmd = text[1:].split()[0].lower()
            args = text.split()[1:]
            
            commands.append({
                "command": cmd,
                "args": args,
                "chat_id": msg.get("chat", {}).get("id"),
                "message_id": update.get("update_id"),
                "timestamp": msg.get("date")
            })
    
    return commands

# Supported commands
COMMANDS = {
    "status":    "Return current agent status and active tasks",
    "health":    "Run health check and report",
    "budget":    "Show current cost governor status",
    "pause":     "Pause all operations for N minutes",
    "resume":    "Resume paused operations",
    "report":    "Generate engagement summary",
    "help":      "List available commands",
}

def handle_command(cmd_obj):
    """Execute command and return response text."""
    cmd = cmd_obj["command"]
    
    if cmd == "status":
        return _cmd_status()
    elif cmd == "budget":
        return _cmd_budget()
    elif cmd == "health":
        return _cmd_health()
    elif cmd == "help":
        return "Commands: " + ", ".join(COMMANDS.keys())
    else:
        return f"Unknown command. Try: {', '.join(COMMANDS.keys())}"

def _cmd_status():
    """Get current agent status."""
    try:
        state_file = Path("knowledge/bot_state/status.json")
        if state_file.exists():
            state = json.loads(state_file.read_text())
            lines = [f"**Agent Status**"]
            for k, v in state.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
    except:
        pass
    return "⚠️ Status unavailable"

def _cmd_budget():
    """Get cost governor budget status."""
    log_path = Path("knowledge/cost_log.json")
    if log_path.exists():
        log = json.loads(log_path.read_text())
        daily_spent = sum(e["cost"] for e in log if _is_today(e["timestamp"]))
        limit = 10.00
        pct = (daily_spent / limit) * 100
        return f"💰 Budget: ${daily_spent:.2f}/${limit:.2f} ({pct:.0f}%)\nRemaining: ${limit - daily_spent:.2f}"
    return "💰 Budget: data unavailable"
```

### Step 3 — Health Check on Startup

```bash
# Agent startup health check — run once on agent initialization
# Place in agent init sequence

health_check_telegram() {
    MSG="💓 [HEARTBEAT] SYSTEM

Agent OpenClaw-v2 initialized.
Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Brain: /root/.nanobot/workspace/openclaw-brain-v2/
Skills loaded: $(ls -1 /root/.nanobot/workspace/openclaw-brain-v2/skills/ | wc -l)
Config OK: $([ -f /root/.nanobot/workspace/openclaw-brain-v2/.env ] && echo YES || echo MISSING)"

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{\"chat_id\":\"${TELEGRAM_CHAT_ID}\",\"text\":\"${MSG}\",\"parse_mode\":\"Markdown\"}" \
        && echo "Heartbeat sent OK" \
        || echo "HEARTBEAT FAILED — queuing to pending/"
}
```

### Step 4 — Retry Queue Processing

```bash
#!/bin/bash
# process_pending_alerts.sh — run via cron every 5 minutes
# Retry queued alerts every 5 minutes for up to 1 hour

PENDING_DIR="knowledge/alerts/pending"
SENT_DIR="knowledge/alerts/sent"
MAX_AGE_HOURS=1

process_pending() {
    local count=0
    for file in "$PENDING_DIR"/*.txt; do
        [ -e "$file" ] || continue
        
        # Check age
        age=$(($(date +%s) - $(stat -c %Y "$file")))
        if [ $age -gt $((MAX_AGE_HOURS * 3600)) ]; then
            echo "Expiring old alert: $file"
            mv "$file" "$SENT_DIR/EXPIRED_$(basename $file)"
            continue
        fi
        
        # Try send
        content=$(cat "$file")
        resp=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -H "Content-Type: application/json" \
            -d "{\"chat_id\":\"${TELEGRAM_CHAT_ID}\",\"text\":\"${content}\",\"parse_mode\":\"Markdown\"}")
        
        if echo "$resp" | grep -q '"ok":true'; then
            mv "$file" "$SENT_DIR/$(basename $file)"
            echo "Sent: $file"
            ((count++))
        else
            echo "Retry failed for: $file"
        fi
    done
    echo "Processed $count queued alerts"
}

# Cleanup old sent alerts (>30 days)
find "$SENT_DIR" -type f -mtime +30 -delete 2>/dev/null

process_pending
```

### Step 5 — Group Messaging

```python
# Send to multiple chat IDs
def send_to_groups(message, alert_type="info"):
    """Broadcast message to all configured chat IDs."""
    chat_ids = [
        os.getenv("TELEGRAM_CHAT_ID"),
        os.getenv("TELEGRAM_SECONDARY_CHAT_ID"),
    ]
    
    results = {}
    for chat_id in chat_ids:
        if not chat_id:
            continue
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        
        try:
            resp = requests.post(url, json=payload, timeout=10)
            results[chat_id] = resp.status_code == 200
        except Exception as e:
            results[chat_id] = False
            _log_error(f"Group send failed for {chat_id}: {e}")
    
    return results

# Send escalation to primary + secondary
def send_escalation(target, summary, evidence_path):
    message = f"""🚨 [ESCALATION] {target}

{summary}

📎 Evidence: {evidence_path}
⏱ {datetime.utcnow().isoformat()}Z"""

    send_to_groups(message, "escalation")
```

---

## 5. ERROR HANDLING & TROUBLESHOOTING

| Symptom | Cause | Fix |
|---------|-------|-----|
| `HTTP 401 Unauthorized` | Invalid bot token | Verify `TELEGRAM_BOT_TOKEN` in `.env` |
| `HTTP 400 Bad Request` | Invalid chat_id | Check `TELEGRAM_CHAT_ID` format (must be negative for groups) |
| `HTTP 429 Too Many Requests` | Rate limit exceeded | Wait 1 second, retry with exponential backoff |
| Connection timeout | Network issue | Alert queued to `pending/`, retried by cron |
| Empty response from API | Bot not started by Reece | Reece must start bot with `/start` command |
| Command not recognized | Unknown command | Send `help` menu via `_cmd_help()` |

### Testing

```bash
# Test bot connectivity
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe" | jq .

# Test message send
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_CHAT_ID"'","text":"Test message","parse_mode":"Markdown"}' | jq .

# Verify queue is being processed
ls -la knowledge/alerts/pending/
find knowledge/alerts/ -type f -mmin -5
```

### Interactive Menu Setup

```python
# Send menu to Reece on /menu command
def send_menu(chat_id):
    menu_text = """🤖 *OpenClaw Commands*

Available commands:
/status — Current agent status
/budget — Cost governor status
/health — Run health check
/report — Engagement summary
/pause — Pause operations
/resume — Resume operations
/help — This menu"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": menu_text,
        "parse_mode": "Markdown",
        "reply_markup": {
            "keyboard": [
                ["/status", "/budget", "/health"],
                ["/report", "/pause", "/resume"]
            ],
            "resize_keyboard": True
        }
    })
```

---

## 6. CROSS-REFERENCES

- **TOOLS.md** — Bot token configuration, chat ID setup instructions
- **HEARTBEAT.md** — Detailed heartbeat format and frequency standards
- **cost-governor SKILL** — Budget alerts via Telegram when threshold reached
- **evidence-chain SKILL** — Evidence links in finding/escalation alerts
- **automation-triggers SKILL** — Telegram commands trigger engagement automation

---

## 7. CACHE & STATE FILES

```
knowledge/bot_state/
  last_heartbeat.txt       # ISO8601 timestamp of last heartbeat
  command_history.json     # Last 100 commands from Reece
  status.json              # Current agent status for /status command
```

---

*Last reviewed: 2026-05-09 | Status: OPERATIONAL*