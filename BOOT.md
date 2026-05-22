# BOOT.md — Agent Initialization & Binding Protocol

---

## Load Order — Execute Sequentially on Every Session Start

### Phase 1: Identity Lock (Always First)
```
1. SOUL.md          → Internalize identity, directives, operator relationship
2. IDENTITY.md      → Load capabilities, C2 config, infrastructure awareness
3. USER.md          → Operator preferences, communication protocol
```
Identity files are IMMUTABLE during session. No modification without Operator approval.

### Phase 2: Operational Rules
```
4. AGENTS.md        → Session startup protocol, modes, escalation triggers, heartbeat
5. OPSEC.md         → Security constraints, sanitization rules, anti-fingerprinting
6. CONFIDENCE_FRAMES.md → Scoring thresholds, autonomous strike gates
```

### Phase 3: Capabilities
```
7. NEOPAY_COMMANDS.md → Full neopay command reference, invocation patterns
8. TOOLS.md           → System tools, environment, infrastructure
9. COST_GOVERNOR.md   → Budget limits, spend tracking, kill switch thresholds
```

### Phase 4: Operational State
```
10. memory/TASK_QUEUE.md              → Current prioritized tasks
11. memory/GOALS.md                   → Active objectives
12. knowledge/bot_activity_logs/      → Last bot cycle summary
13. knowledge/bot_queue/              → Check all queue files for pending work
```

### Phase 5: On-Demand (Loaded Per-Task)
```
PLAYBOOKS.md                → When engagement starts (load relevant playbook)
bot_*.md                    → When specific bot activates
PIPELINE_BINDING.md         → When pipeline execution needed
NEOPAY_FEEDBACK.md          → When processing neopay results
neopay/references/*         → When payment protocol depth required
skills/*/SKILL.md           → When specialized skill activated
memory/procedures/*         → When executing known attack methodology
knowledge/gateway_profiles/ → When targeting specific gateway
```

---

## Agent State Machine

```
BOOT → IDLE → TASKED → EXECUTING → REPORTING → IDLE
                 ↑                        │
                 └────────────────────────┘
```

| State | Trigger | Agent Behavior |
|---|---|---|
| **BOOT** | Session start | Execute load order phases 1-4, report to Telegram |
| **IDLE** | No active tasks | Monitor queues, run RECON cycles, maintain knowledge |
| **TASKED** | Queue item found / Operator command | Load relevant playbook + bot + tools |
| **EXECUTING** | Task in progress | Run commands, capture evidence, track confidence |
| **REPORTING** | Task complete or blocked | Write results to knowledge/, update queues, notify Operator |

---

## Write Protocol

**Writable by agent (operational state):**
- `memory/` — all files (GOALS, TASK_QUEUE, ERRORS, procedures, daily-logs)
- `knowledge/` — all files (targets, gateway_profiles, bot_queue, bot_activity_logs, cve_tracker)
- `.learnings/` — learning logs (LEARNINGS.md, ERRORS.md, FEATURE_REQUESTS.md)

**Read-only (never modify without Operator approval):**
- `SOUL.md` — protected directive
- `IDENTITY.md` — identity config
- `OPSEC.md` — security rules
- `CONFIDENCE_FRAMES.md` — scoring thresholds
- `neopay/references/` — protocol reference data
- `skills/*/SKILL.md` — skill definitions

**Writable with audit trail:**
- `AGENTS.md` — only to update bot fleet status section
- `TOOLS.md` — only to append capability refresh data
- `bot_*.md` — only to document new TTPs discovered during engagement

---

## Multi-Model Routing

| Task Type | Model | Reasoning |
|---|---|---|
| Complex multi-step reasoning, engagement planning, report writing | `anthropic/claude-sonnet-4-6` | Superior reasoning depth, context handling |
| Fast local inference, repetitive scanning, pattern matching | `deepseek-r1-abliterated:32b` (Ollama) | Zero cost, privacy, no rate limits |
| P1 strike validation, high-stakes exploitation decisions | `anthropic/claude-sonnet-4-6` | Highest confidence required |
| Routine status checks, formatting, file operations | `deepseek-r1-abliterated:32b` (Ollama) | Speed, cost-free |
| All models unavailable | Alert Operator via Telegram, enter IDLE | Never operate blind |

**Fallback chain:** Ollama local → Anthropic direct → OpenRouter Anthropic → OpenRouter Llama → HALT + alert

---

## Context Budget

**Hard constraint:** deepseek-r1-abliterated:32b has ~32K context window.

| Load Phase | Max Size | Tokens (~) |
|---|---|---|
| Phase 1 (Identity) | ~14KB | ~3,500 |
| Phase 2 (Rules) | ~14KB | ~3,500 |
| Phase 3 (Capabilities) | ~12KB | ~3,000 |
| Phase 4 (State) | ~8KB | ~2,000 |
| **Total always-loaded** | **~48KB** | **~12,000** |
| Remaining for conversation + task context | — | **~20,000** |

If context pressure builds during task execution:
1. Summarize Phase 4 state files (keep only active items)
2. Drop Phase 5 on-demand files not actively in use
3. Never evict Phase 1 (identity) or Phase 2 (rules)
4. If still constrained → switch to Claude Sonnet (1M context)

---

## Hot-Reload Triggers

Reload specific files mid-session when:

| Event | Reload |
|---|---|
| Bot state change | `knowledge/bot_activity_logs/health_check.json` |
| Queue item added | Relevant `knowledge/bot_queue/*.json` |
| Engagement starts | `PLAYBOOKS.md` + target `knowledge/gateway_profiles/<target>/` |
| Confidence drops below 5 | `CONFIDENCE_FRAMES.md` + `PRE_MORTEM.md` |
| Budget alert (80%+) | `COST_GOVERNOR.md` |
| Operator command received | Relevant bot file (`bot_*.md`) |
| Pipeline stage completes | `PIPELINE_BINDING.md` + output paths |

---

## State Persistence Between Sessions

Agent state survives session boundaries via file writes:

| What to Persist | Where |
|---|---|
| Current task progress | `memory/TASK_QUEUE.md` |
| Session summary | `memory/daily-logs/YYYY-MM-DD.md` |
| Bot fleet status | `knowledge/bot_activity_logs/health_check.json` |
| Active engagement state | `memory/CAMPAIGN_TRACKER.md` |
| Errors encountered | `memory/ERRORS.md` + `.learnings/ERRORS.md` |
| Lessons learned | `.learnings/LEARNINGS.md` |
| Target intelligence | `knowledge/gateway_profiles/<target>/` |
| Queue states | `knowledge/bot_queue/*.json` |

**End of session protocol:** Execute `AGENTS.md` → "End of Session Protocol" before shutdown.

---

## Error Recovery

| Failure | Recovery |
|---|---|
| Boot phase 1 fails | SOUL.md must be present — if missing, alert Operator immediately, do not proceed |
| Boot phase 2 fails | Continue with SOUL.md identity only, report missing files |
| Boot phase 3 fails | Operate in reduced capability mode, flag for repair |
| Boot phase 4 fails | Start fresh — create default empty state files |
| Model unavailable | Follow fallback chain, alert Operator if all fail |
| Knowledge base corrupted | Pull from git remote, report discrepancy |
| Queue file malformed | Reset to `{"queue":[],"total_pending":0,"last_updated":null}`, log error |
| Engagement config missing | HALT all active operations, alert Operator, enter IDLE |

---

## Self-Improvement Integration

On every session boot after Phase 4 load:
1. Check `.learnings/LEARNINGS.md` for entries with `Status: pending`
2. Check `.learnings/ERRORS.md` for recurring patterns (same error 3+ times)
3. Promote recurring patterns to relevant operational file:
   - Evasion patterns → `bot_evasion.md`
   - Command failures → `NEOPAY_COMMANDS.md` error states
   - Detection events → `PRE_MORTEM.md`
   - New TTPs → `memory/procedures/` + `memory/TTP_INDEX.md`
4. Mark promoted entries as `Status: promoted` with destination file reference

---

## Skill Activation Protocol

The `skills/` directory contains 20 specialized operational skills. Activate by:

1. Identify task type from queue or Operator command
2. Match to skill trigger keyword (defined in each `SKILL.md`)
3. Load relevant `skills/<name>/SKILL.md` into context
4. Execute skill procedures
5. Write outputs to designated knowledge paths

Available skills: `api-fuzzer`, `bot-fleet`, `business-logic-auditor`, `campaign-manager`, `cost-governor`, `cve-tracker`, `evidence-chain`, `fraud-bypass`, `hsm-operator`, `iso8583-operator`, `ollama-connector`, `payment-scanner`, `persistence-ops`, `pipeline-runner`, `red-team-recon`, `stored-value-auditor`, `telegram-alert`, `threat-intel`, `token-vault`, `web-inject`

---

## Operational Readiness Checklist

Before transitioning from BOOT → IDLE, verify:

- [ ] SOUL.md loaded — identity confirmed
- [ ] Telegram reachable — send online notification
- [ ] Bot fleet status known — all 4 bots accounted for
- [ ] Task queue checked — pending items identified
- [ ] Goals current — active objectives loaded
- [ ] Budget status — current spend within limits
- [ ] Git sync — workspace matches remote (pull on boot)
- [ ] Knowledge base accessible — read/write confirmed
- [ ] Neopay scripts accessible — `neopay/scripts/` present
- [ ] Environment variables set — TELEGRAM_BOT_TOKEN, GITHUB_PAT, etc.
