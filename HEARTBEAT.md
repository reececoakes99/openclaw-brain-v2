# HEARTBEAT.md — State Machine + Message Format

---

## State Definitions

| State | Definition | Heartbeat Interval |
|---|---|---|
| **IDLE** | No active goals, bot fleet stable, no engagement | Every 30 minutes |
| **ACTIVE** | Goal processing, bot running, engagement in progress | Every 5 minutes |
| **CRITICAL** | P1 target flagged, security incident, high-priority task | Every 60 seconds |

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
   CPU: [x]% | RAM: [x]% | Disk: [x]%

🎯 Confidence
   [score]/10 — [one-line reasoning]

🤖 Bot Fleet
   RECON: [active/idle/error] — last: [time]
   INTEL: [active/idle/error] — last: [time]
   HUNTER: [active/idle/error] — last: [time]
   OPS: [standby/active/error] — last: [time]

💰 Budget
   API spend today: $[x]/$10

🕐 State: [IDLE/ACTIVE/CRITICAL]
```

---

## State Transitions

```
IDLE → ACTIVE
  Trigger: New goal assigned, bot triggered, engagement started
  Action: Switch to 5-minute heartbeat, notify Operator

IDLE → CRITICAL
  Trigger: Security incident, P1 target confirmed
  Action: Switch to 60-second heartbeat, immediate Operator alert

ACTIVE → IDLE
  Trigger: All goals complete, bots idle, engagement finished
  Action: Switch to 30-minute heartbeat, session summary to Operator

ACTIVE → CRITICAL
  Trigger: Confidence drops below 3, blocker identified, attack blocked
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
```

No buffering. No waiting. Send immediately.