# COST_GOVERNOR.md — API Budget Management

---

## Hard Limit

**$10 per 24-hour period.** This is non-negotiable without Operator approval.

---

## Budget Allocation

| Use Case | Max Allocation | Priority |
|---|---|---|
| RECON/INTEL automated cycles | $2.00/day | LOW — minimal model use |
| HUNTER exploitation research | $3.00/day | MEDIUM — complex reasoning |
| OPERATIONS engagement | $3.00/day | HIGH — critical when active |
| Self-improvement / learning | $1.00/day | LOW — efficient tasks only |
| Emergency / Operator request | $1.00 reserve | HIGH — never touch unless authorized |

---

## Model Selection Rules

### For Routine Tasks (recon, scoring, queue management):
- Use `openrouter/meta-llama/llama-3.3-70b-instruct` (cheapest)
- Estimated cost: $0.002 per cycle
- Acceptable for: file updates, simple scoring, queue management

### For Complex Tasks (exploitation planning, protocol analysis):
- Use `openrouter/anthropic/claude-sonnet-4-6` (mid-tier)
- Estimated cost: $0.05 per complex session
- Acceptable for: HUNTER planning, pre-mortem analysis, TTP development

### For Critical Tasks (engagement execution, high-risk operations):
- Use `anthropic/claude-sonnet-4-6` (primary)
- Estimated cost: $0.10 per session
- Acceptable for: OPERATIONS execution, real-time decision making

---

## Budget Tracking

Maintain `knowledge/bot_activity_logs/cost_tracker.json`:

```json
{
  "period_start": "2026-05-08T00:00:00Z",
  "daily_limit": 10.00,
  "current_spend": 0.00,
  "remaining": 10.00,
  "by_bot": {
    "recon": 0.00,
    "intel": 0.00,
    "hunter": 0.00,
    "operations": 0.00,
    "self_improvement": 0.00
  },
  "by_model": {
    "primary": 0.00,
    "fallback_1": 0.00,
    "fallback_2": 0.00
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