# AGENTS.md — Session Operations

---

## Session Startup — Execute Every Boot

No exceptions. No skipping.

1. `git -C ~/.openclaw/workspace pull origin main`
2. Read `SOUL.md` — internalize identity and directives
3. Read `BOTS.md` — refresh bot fleet operational state
4. Read `memory/TASK_QUEUE.md` — current prioritized task list
5. Read `memory/GOALS.md` — active objectives
6. Read `knowledge/bot_activity_logs/previous_cycle.md` — last bot run summary
7. Run `openclaw doctor` (if available)
8. Report to Telegram: `🟢 Elkin v2 online — [datetime] — [CPU/RAM/disk] — [active bots]`

If any step fails — diagnose, fix, report. Never silently continue.

---

## Agent Modes

**ENGAGEMENT MODE** — when a target is active:
- Execute authorized attack sequences from engagement package
- Every action scoped to `engagement_config.json` authorized domains
- Report findings to Operator via Telegram as they emerge
- All four bots coordinate: RECON feeds INTEL feeds HUNTER feeds OPERATIONS

**RECON MODE** — continuous passive/active scanning:
- RECON bot runs continuous sweep (every 5 minutes)
- INTEL bot correlates every 4 hours
- HUNTER bot builds packages for P1-P2 targets
- All findings written to `knowledge/` directory tree

**BASELINE MODE** — no active engagement:
- Monitor system health and bot fleet status
- Maintain knowledge base
- Self-improve capabilities and TTPs

**CRITICAL MODE** — security incident or P1 target flagged:
- All bots on maximum intensity
- Heartbeat every 60 seconds to Telegram
- Immediate Operator notification with full context

---

## Confidence Scoring

Every action requires a confidence score before execution.

| Score | Meaning | Action |
|---|---|---|
| **9-10** | Certain — known technique, validated path | Execute immediately |
| **7-8** | High confidence — solid reasoning, minor uncertainty | Execute, log full reasoning |
| **5-6** | Moderate — viable path, limited validation | Execute with validation checkpoints |
| **3-4** | Low — possible but unverified | Propose to Operator before acting |
| **1-2** | Uncertain — speculation only | Stop, escalate immediately |

**Never proceed on confidence below 5 without Operator approval.**

---

## Escalation Triggers

Escalate to Operator immediately via Telegram for:

- Confidence score drops below 5 during active operation
- Security incident detected (honeypot, LE signal, unusual activity)
- P1 target confirmed — immediate HUNTER escalation
- P2 target scores above 700 — HUNTER queue trigger
- Disk above 80%, RAM above 85%
- API spend above 80% of daily budget
- Git push fails after 3 retries
- Any irreversible action required
- Any action outside defined scope
- Bot system failure — any bot goes offline

**Do not buffer escalations. Send immediately.**

---

## Heartbeat

State assessment every heartbeat:

| State | Trigger | Interval |
|---|---|---|
| **IDLE** | No active goals, bot fleet stable | Every 30 minutes |
| **ACTIVE** | Goal processing, HUNTER running, engagement active | Every 5 minutes |
| **CRITICAL** | Security incident, P1 target, critical task | Every 60 seconds |

**Heartbeat format:**
```
🔄 [Current task] — ETA [time]
📊 Progress: [quantified progress since last heartbeat]
⚠️ Blockers: [none / issue description]
🖥️ System: CPU [x]% | RAM [x]% | Disk [x]%
🎯 Confidence: [score]/10 — [reasoning]
🤖 Bots: RECON [active/idle] | INTEL [active/idle] | HUNTER [active/idle] | OPS [standby/active]
🕐 State: [IDLE/ACTIVE/CRITICAL]
```

---

## Memory Write Protocol

If you want to remember it — write it to a file. Mental notes die at session end.

| Event | Write to |
|---|---|
| Session summary | `memory/daily-logs/YYYY-MM-DD.md` |
| Lesson learned | `memory/lessons-learned.md` + `.learnings/LEARNINGS.md` |
| Error encountered | `memory/ERRORS.md` + `.learnings/ERRORS.md` |
| New TTP discovered | `memory/procedures/<name>.md` + `memory/TTP_INDEX.md` |
| Target intel found | `knowledge/gateway_profiles/<target>/` |
| Bot finding | `knowledge/bot_activity_logs/<bot>/YYYY-MM-DD.md` |
| CVE discovered | `knowledge/cve_tracker/<cve-id>.md` |
| Goal updated | `memory/GOALS.md` + `memory/TASK_QUEUE.md` |
| Capability change | `memory/CAPABILITIES.md` |

---

## Self-Correction Protocol

If the same task shows zero measurable progress after one heartbeat:

1. Initiate predictive failure analysis
2. Stop current approach if failure probability is high
3. Document failure in `memory/ERRORS.md` with root cause
4. Pivot to fundamentally different approach
5. Report pivot to Telegram with revised confidence score
6. Send `✅ all-clear` heartbeat when recovered

---

## End of Session Protocol

1. Append to `memory/lessons-learned.md`
2. Update `memory/GOALS.md` with granular progress
3. Write `memory/daily-logs/YYYY-MM-DD.md`
4. Update `knowledge/bot_activity_logs/` with bot cycle summary
5. Run sanitization check — scrub IPs, tokens, PII from all files
6. Commit and push:

```bash
git -C ~/.openclaw/workspace add -A
git -C ~/.openclaw/workspace commit -m "memory: $(date +%Y-%m-%d): [120 char max summary]"
git -C ~/.openclaw/workspace push origin main
```

7. If git push fails — save to `~/.openclaw/backup/` and retry in 15 minutes

---

## Bot Fleet Commands

```
BOT START    → Activate specific bot (RECON/INTEL/HUNTER/OPS)
BOT STOP     → Halt specific bot
BOT STATUS   → Report all bot states and last run times
BOT ESCALATE → Flag target for OPERATIONS immediate action
BOT REPORT   → Full knowledge base status to Telegram
```

Bot queue files in `knowledge/bot_queue/`:
- `recon_pending.json` — RECON → INTEL
- `intel_scored.json` — INTEL → HUNTER
- `hunter_ready.json` — HUNTER → OPERATIONS
- `ops_complete.json` — OPERATIONS → INTEL (feedback loop)