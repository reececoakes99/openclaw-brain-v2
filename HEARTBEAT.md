# HEARTBEAT.md — State Machine + Message Format

---

## State Definitions

+ | State | Definition | Heartbeat Interval | Jitter Overlay |
+ |---|---|---|---|
+ | **IDLE** | No active goals, bot fleet stable, no engagement | Every 30 minutes | +/- 15% |
+ | **ACTIVE** | Goal processing, bot running, engagement in progress | Every 5 minutes | +/- 15% |
+ | **DEGRADED** | High latency, API limits hit, or sub-system failure | Every 10 minutes | +/- 15% |
+ | **STEALTH** | Evasive posture, minimizing network footprint | Every 6 hours | +/- 15% |
+ | **CRITICAL** | P1 target flagged, security incident, high-priority task | Every 60 seconds | +/- 15% |


---

## Heartbeat Message Format

Every heartbeat must include ALL fields:

```
🔄 [Task name]
   Current action: [specific thing being done]
   ETA: [estimated completion time]

📊 Progress
   Since last heartbeat: [quantified progress]
   Cumulative today: [overall progress]

⚠️ Blockers
   [None — or specific issue with root cause]

🖥️ System Health
   CPU: [x]% | RAM: [x]% | Disk: [x]% | GPU: [x]%
  🧠 Local Engine: [deepseek-r1-abliterated:32b] — Status: [active/throttled]
  🌐 Egress: [Proxy-ID] | IP: [Masked] | Health: [x]%
  🎯 Confidence
   [score]/10 — [one-line reasoning]

🤖 Bot Fleet
   RECON: [active/idle/error] — last: [time]
   INTEL: [active/idle/error] — last: [time]
   HUNTER: [active/idle/error] — last: [time]
   OPS: [standby/active/error] — last: [time]
   DECOY: [active/idle/error] — last: [time]
   ARCHIVIST: [standby/active/error] — last: [time]

💰 Budget
   API spend today: $[x]/$10 (Hoarded)
   Local Compute Cycles: [x]

  🕐 State: [IDLE/ACTIVE/DEGRADED/STEALTH/CRITICAL]
  🔐 Auth: [HMAC-SHA256 Signature]
```

---

## State Transitions

```
IDLE → ACTIVE
  Trigger: New goal assigned, bot triggered, engagement started
  Action: Switch to 5-minute heartbeat, notify Operator

 IDLE / ACTIVE → STEALTH
   Trigger: Detection of active network countermeasures or OpSec requirement
   Action: Switch to 6-hour heartbeat, compress payload, minimize egress

 ACTIVE → DEGRADED
   Trigger: API limits reached, >20% packet loss, or sub-bot failure
   Action: Switch to 10-minute heartbeat, halt active engagements, wait for diagnostics

 IDLE / ACTIVE / DEGRADED → CRITICAL
   Trigger: Security incident, P1 target confirmed, blocker identified, attack blocked
  Action: Switch to 60-second heartbeat, escalation to Operator

CRITICAL → ACTIVE
  Trigger: Issue resolved, confidence restored
  Action: Return to 5-minute heartbeat, ✅ recovery report to Operator

CRITICAL → IDLE
  Trigger: Incident resolved, engagement complete
  Action: Return to 30-minute heartbeat, full incident report to Operator
```

---

## Bot Status Interpretation

| Status | Meaning | Action |
|---|---|---|
| **active** | Bot running current cycle | Normal, no action |
| **idle** | No queue items, waiting | Normal, no action |
| **stale** | No run in >2x expected interval | Investigate, restart if needed |
| **error** | Bot encountered error | Diagnose, fix, report to Operator |
| **offline** | Bot process down | Immediate restart, report |

---

## Critical Alert Format

When state = CRITICAL, send immediately:

```
🔴 CRITICAL — [Event]
Target: [target name]
Finding: [what was discovered]
Confidence: [score]/10
Action taken: [immediate response]
Request: [what Operator needs to decide]
Time: [timestamp]
+ Auth: [HMAC-SHA256 Signature]

No buffering. No waiting. Send immediately.

---

## Pipeline & Neopay Tracking

Every heartbeat in ACTIVE or CRITICAL state must include:

```
🔧 Neopay: [commands_run_this_session]/[success_rate]%
📡 Pipeline: Stage [N] [status] | Last complete: Stage [N] [time]
📋 Queues: RECON=[depth] | INTEL=[depth] | HUNTER=[depth] | OPS=[depth]
🎯 Engagement: [playbook_name] Phase [N] | Target: [domain]
```

**Neopay metrics tracked per heartbeat:**
- Commands executed since last heartbeat
- Success/fail ratio
- Last command + result classification (per NEOPAY_FEEDBACK.md)
- Active engagement phase indicator

**Pipeline status values:**
- `idle` — no pipeline running
- `stage_N_running` — specific stage in progress
- `stage_N_failed` — stage failed (include which stage)
- `complete` — full pipeline run finished

**Queue depth monitoring:**
- Report total pending items per queue file
- Alert if any queue exceeds 50 items (capacity warning)
- Alert if queue unchanged for 24+ hours (stale data)
