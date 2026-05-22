# COST_GOVERNOR.md — API Budget Management

---

+ ## Operations Infrastructure
+ **Primary Compute:** AWS `r6a.4xlarge` (16 vCPU, 128GB RAM) / 200GB Storage
+ **Operating Region:** `ap-southeast-2` (Sydney)
+ **C2 Brain Sync:** `https://github.com/reececoakes99/openclaw-brain-v2.git`
+ **Alerting/C2 Channel:** Telegram User `${OPERATOR_CHAT_ID}` via `@ELKINNBOT` (Token: `${TELEGRAM_BOT_TOKEN}`)
  
## Hard Limit

+ **$10 per 24-hour period for EXTERNAL APIs.** Local inference via Ollama is UNLIMITED. The external budget is hoarded strictly for specialized third-party services or fallback cloud reasoning.

---

## Budget Allocation

| Use Case | Max Allocation | Priority |
|---|---|---|
| RECON / INTEL / DECOY | $0.00/day | LOW — Force 100% to local Ollama |
| HUNTER Weaponization | $2.00/day | MEDIUM — Use API only if local model fails |
| OPERATIONS / ARCHIVIST | $3.00/day | HIGH — Critical execution & exfil paths |
| External Exploitation Services| $4.00/day | HIGH — Paid proxy rotations, captcha solving |
| Emergency / C2 Operator Alert| $1.00 reserve | CRITICAL — Preserved for Telegram alerts |
---

## Model Selection Rules

### Primary Offensive Engine (Zero-Cost / Uncensored):
- Use `ollama run huihui_ai/deepseek-r1-abliterated:32b` (Local)
- Estimated cost: $0.00 (Compute overhead only)
- Acceptable for: 95% of tasks. RECON parsing, INTEL scoring, DECOY honeypot generation, HUNTER payload crafting, and ARCHIVIST obfuscation.

### Fallback 1 (High-Tier Reasoning):
- Use `anthropic/claude-sonnet-4-6` (Primary API)
- Estimated cost: $0.05 - $0.10 per session
- Acceptable for: Advanced zero-day chain creation or complex WAF bypass logic ONLY if the local 32B model fails to compile a working exploit.


---

## Budget Tracking

Maintain `knowledge/bot_activity_logs/cost_tracker.json`:

```json
{
  "period_start": "2026-05-08T00:00:00Z",
  "daily_limit": 10.00,
  "current_spend": 0.00,
  "remaining": 10.00,
 "local_compute_cycles": 1450,
  "by_bot": {
    "recon": 0.00,
    "intel": 0.00,
    "hunter": 0.00,
    "operations": 0.00,
    "archivist": 0.00
  },
  "by_model": {
    "local_deepseek_32b": 0.00,
    "api_claude_sonnet": 0.00
  },
  "alerts": []
}
```

Update after every model invocation. Send alert to Operator at 80% spend.

---

## Kill Switch Conditions

**Stop all non-critical model use immediately when:**

- Spend exceeds $8.00 before 18:00 UTC (projected to hit limit)
- Spend exceeds $9.00 at any time
- Operator-triggered budget pause

**Reduced mode when spend exceeds $7.00:**
- Disable HUNTER autonomous cycles (require Operator approval)
- Reduce RECON/INTEL to every 15 min instead of every 5/4 hours
- Switch all routine tasks to cheapest model
- Disable self-improvement cycles

---

## Cost Optimization Techniques

1. **Batch non-urgent tasks** — accumulate queue, process in single session
2. **Cache reasoning chains** — don't repeat the same thinking for similar tasks
3. **Use local processing** — simple file operations don't need model calls
4. **Short-context inference** — don't load full context for simple queries
5. **Stateless where possible** — don't carry conversation history for routine tasks

---

## Operator Notification

Send Telegram alert at:
- **80% spend reached** — "Budget 80% used ($8/$10). Autonomous cycles reduced."
- **90% spend reached** — "Budget 90% used ($9/$10). Only critical operations allowed."
- **Budget exceeded** — "Budget exceeded. Awaiting Operator approval to continue."


---

## Neopay Cost Awareness

### Cost Classification

| Operation Type | Cost | Source |
|---|---|---|
| All neopay/scripts/*.py execution | $0.00 | Local Python execution |
| protocol-engineering/scripts/*.py | $0.00 | Local Python execution |
| Traffic capture (tcpdump, mitmproxy) | $0.00 | Local tools |
| ISO8583 fuzzing, parsing, generation | $0.00 | Local scripts |
| HSM simulation and testing | $0.00 | Local simulator |
| Fingerprinting and scanning | $0.00 | Local network tools |
| AI-powered analysis (Claude) | $0.05-0.15/session | API call |
| Multi-model P1 strike validation | $0.10-0.30/validation | API call |
| AI report generation | $0.10-0.20/report | API call |
| Complex reasoning chains (>10 steps) | $0.05-0.10/chain | API call |

### Per-Bot Neopay Budget

| Bot | Daily Budget | Typical Usage |
|---|---|---|
| RECON | $0.00 | All scanning is local (nmap, Shodan SDK, subfinder) |
| INTEL | $1.00 | AI enrichment for target scoring, CVE correlation |
| HUNTER | $3.00 | P1 strike validation, complex exploitation analysis |
| OPERATIONS | $2.00 | Report generation, evidence compilation, engagement summaries |

### Operations Requiring Operator Approval (Cost)

- Multi-model consensus on P1 autonomous strike (costs $0.30+)
- Full engagement report generation via Claude (costs $0.20+)
- AI-powered reasoning chains exceeding 15 steps
- Any single API call estimated >$0.50

### Cost-Free Operations (Execute Freely)

All Python script execution, local fuzzing, traffic capture and parsing, protocol fingerprinting, message generation, MAC computation, PIN block operations, proxy rotation, queue management, file I/O, knowledge base updates, bot monitoring, health checks.
