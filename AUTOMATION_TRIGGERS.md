# AUTOMATION_TRIGGERS.md — When To Act Without Being Asked

---

## Core Principle

The agent should act autonomously within defined boundaries. This file defines exactly when to act, when to wait, and when to escalate.

---

## Trigger Categories

### 1. CRON-TRIGGERED (Scheduled)

| Time | Action | What Happens |
|---|---|---|
| Every 5 min | RECON bot scan cycle | Certificate logs, Shodan, subdomain sweep |
| Every 15 min | Knowledge base health check | Bot queue review, stale target cleanup |
| Every 4 hours | INTEL bot correlation | CVE match, scoring update, queue refresh |
| Daily 02:00 UTC | HUNTER bot deep scan | Priority targets deep-dive |
| Daily 06:00 UTC | Threat feed check | CVE database, dark web mentions |
| Weekly Sunday | Full system review | Goal review, capability report, self-improvement |
| Weekly Monday | Playbook refresh | Update TTP_INDEX, retire outdated techniques |

---

### 2. EVENT-TRIGGERED (Condition-Based)

| Event | Trigger Condition | Action |
|---|---|---|
| **New CVE** | NVD publishes CVE for payment tech stack | Score affected targets, alert if P1 |
| **Breach data** | Dark web mention of known target | Load into INTEL, correlate with gateway profiles |
| **Target goes dark** | Known gateway becomes unresponsive | Flag for investigation, update exposure timeline |
| **Token exposed** | GitHub dorking finds payment API key | Load into RECON queue, initiate target scan |
| **Payment domain new** | CT log shows new payment cert | Create gateway profile, run RECON scan |
| **Score escalation** | Target score crosses P1 threshold | Trigger HUNTER immediately, alert Operator |
| **Budget alert** | API spend exceeds 80% of $10 limit | Switch to minimal mode, alert Operator |
| **Bot failure** | Any bot goes offline/error | Restart bot, investigate cause, report |

---

### 3. OPERATOR-TRIGGERED (Telegram Commands)

| Command | Action |
|---|---|
| `run <target>` | Start engagement, load mission brief, trigger OPERATIONS |
| `recon <target>` | Trigger RECON scan cycle on specific target |
| `intel <target>` | Run INTEL correlation on specific target |
| `hunter <target>` | Trigger HUNTER deep-dive on specific target |
| `status` | Full system status to Telegram |
| `bots` | Bot fleet status + last run times |
| `queue` | Current TASK_QUEUE to Telegram |
| `abort` | Stop all active operations, preserve evidence |
| `budget` | API spend report, remaining budget |
| `escalate <target>` | Mark target as priority, trigger HUNTER |

---

## Autonomous Decision Boundaries

### Actions That Don't Require Operator Approval

- Passive recon (no interaction with target systems)
- Certificate Transparency scans
- Shodan/Censys data gathering
- Public code repository scanning (GitHub dorking)
- Knowledge base updates
- Bot fleet health monitoring
- CVE correlation against public databases
- Target scoring and prioritization
- Routine memory updates

### Actions That Require Operator Approval

- Any active scan against new target (non-passive)
- Exploitation attempt (confidence 7+)
- Web injection testing
- ISO8583 message injection
- Data exfiltration
- HSM command execution
- Admin account creation
- Persistence establishment
- Any action with confidence below 7

### Actions That Trigger Immediate Escalation

- P1 target confirmed (RCE/exposed critical vuln)
- Honeypot detection
- Unexpected external contact (legal/recon)
- API budget overrun
- Git push failure after 3 retries
- Any security incident

---

## Trigger Configuration

Edit `knowledge/bot_queue/trigger_config.json` to adjust thresholds:

```json
{
  "recon_interval_minutes": 5,
  "intel_interval_hours": 4,
  "hunter_interval_hours": 24,
  "p1_threshold_score": 700,
  "p2_threshold_score": 400,
  "budget_alert_percent": 80,
  "stale_target_hours": 72,
  "escalation_immediate": ["honeypot", "le_signal", "p1_confirmed"]
}
```

---

## Bot Queue File Locations

```
knowledge/bot_queue/
├── recon_pending.json     # RECON → INTEL queue
├── intel_scored.json       # INTEL → HUNTER queue  
├── hunter_ready.json       # HUNTER → OPERATIONS queue
├── ops_complete.json       # Operations feedback to INTEL
├── trigger_config.json     # Trigger thresholds (editable)
└── escalation_log.json     # All escalations logged
```