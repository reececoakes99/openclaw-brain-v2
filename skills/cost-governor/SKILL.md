# SKILL: cost-governor

## Identity
- **Name:** cost-governor
- **Category:** Operations Support
- **Trigger:** At agent startup, before every API call, at 80% daily budget, and at budget exhaustion
- **Confidence requirement:** 5/10

## Overview

API spend is controlled with a hard cap. This skill tracks every model call, enforces budget limits, prioritizes requests, and prevents runaway costs. The default limit is $10/day but it's configurable per engagement.

## Operational Procedure

### Step 1: Budget Initialization

```bash
# Set budget at agent startup
export DAILY_BUDGET=10  # USD
export WARN_THRESHOLD=0.8  # 80%
export HARD_STOP=1.0  # 100%
export CURRENT_SPEND=0

# Load spend log
SPEND_LOG="knowledge/cost_log.json"
if [ ! -f "$SPEND_LOG" ]; then
  echo '{"date":"'$(date +%Y-%m-%d)'","calls":[],"total_spend":0}' > "$SPEND_LOG"
fi

echo "Budget initialized: \$$DAILY_BUDGET/day | Current: \$$CURRENT_SPEND"
```

### Step 2: Pre-Call Budget Check

```python
#!/usr/bin/env python3
"""
pre_call_check.py — run before every API call
Returns: allow=True/False, reason
"""
import json, os
from datetime import datetime, timedelta

SPEND_LOG = os.environ.get('SPEND_LOG', 'knowledge/cost_log.json')
DAILY_BUDGET = float(os.environ.get('DAILY_BUDGET', '10'))
WARN_THRESHOLD = float(os.environ.get('WARN_THRESHOLD', '0.8'))

def check_budget():
    # Load spend log
    with open(SPEND_LOG) as f:
        log = json.load(f)
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Reset if new day
    if log.get('date') != today:
        log = {'date': today, 'calls': [], 'total_spend': 0}
    
    # Calculate current spend
    current = log.get('total_spend', 0)
    limit = DAILY_BUDGET
    
    # Hard stop
    if current >= limit:
        return False, f"BUDGET EXHAUSTED: ${current}/${limit}"
    
    # Warning threshold
    if current >= limit * WARN_THRESHOLD:
        return False, f"BUDGET WARNING: ${current}/${limit} (80% threshold)"
    
    return True, f"Approved: ${current}/${limit}"

allow, reason = check_budget()
print(reason)
exit(0 if allow else 1)
```

### Step 3: Model Selection Strategy

```python
#!/usr/bin/env python3
"""
model_selector.py — choose optimal model based on task complexity and budget
"""
import os

# Model cost per 1K tokens (approximate)
MODELS = {
    'anthropic/claude-sonnet-4-6': {'cost': 3.00, 'context': 200000, 'quality': 'high'},
    'openrouter/anthropic/claude-sonnet-4-6': {'cost': 3.00, 'context': 200000, 'quality': 'high'},
    'openrouter/meta-llama/llama-3.3-70b-instruct': {'cost': 0.70, 'context': 128000, 'quality': 'medium'},
    'openrouter/google/gemini-flash-2.0': {'cost': 0.10, 'context': 1000000, 'quality': 'medium'},
}

# Cost-based model selection
def select_model(task_complexity, budget_remaining):
    """
    task_complexity: 'high' | 'medium' | 'low'
    budget_remaining: float (USD)
    """
    if budget_remaining < 1.0:
        # Near budget limit — use cheapest
        return 'openrouter/google/gemini-flash-2.0'
    
    if task_complexity == 'high':
        return 'anthropic/claude-sonnet-4-6'
    elif task_complexity == 'medium':
        return 'openrouter/anthropic/claude-sonnet-4-6'
    else:
        return 'openrouter/meta-llama/llama-3.3-70b-instruct'

# Example usage
task = os.environ.get('TASK_TYPE', 'medium')
remaining = float(os.environ.get('BUDGET_REMAINING', '10'))
model = select_model(task, remaining)
print(f"Selected model: {model} (task={task}, budget=${remaining:.2f})")
```

### Step 4: Request Logging

```python
#!/usr/bin/env python3
"""
log_api_call.py — log every API call with cost
"""
import json, os
from datetime import datetime

SPEND_LOG = os.environ.get('SPEND_LOG', 'knowledge/cost_log.json')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8069069638')

def log_call(model, input_tokens, output_tokens, cost):
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Load log
    try:
        with open(SPEND_LOG) as f:
            log = json.load(f)
    except:
        log = {'date': today, 'calls': [], 'total_spend': 0}
    
    # Reset if new day
    if log.get('date') != today:
        log = {'date': today, 'calls': [], 'total_spend': 0}
    
    # Add call
    call = {
        'timestamp': datetime.now().isoformat(),
        'model': model,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'cost': round(cost, 4)
    }
    log['calls'].append(call)
    log['total_spend'] = round(log.get('total_spend', 0) + cost, 4)
    
    # Save log
    with open(SPEND_LOG, 'w') as f:
        json.dump(log, f, indent=2)
    
    # Check warn threshold
    daily_budget = float(os.environ.get('DAILY_BUDGET', '10'))
    if log['total_spend'] >= daily_budget * 0.8:
        # Send warning to Telegram
        import urllib.request, json as j
        msg = f"⚠️ Budget warning: ${log['total_spend']:.2f}/${daily_budget} (80%)"
        data = j.dumps({'chat_id': TELEGRAM_CHAT_ID, 'text': msg}).encode()
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            data=data, headers={'Content-Type': 'application/json'}
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except:
            pass
    
    print(f"Logged: {model} | {input_tokens}in/{output_tokens}out | ${cost:.4f} | Total: ${log['total_spend']:.4f}")
```

### Step 5: Budget Enforcement at Exhaustion

```bash
#!/bin/bash
# enforce_budget.sh — run at budget exhaustion

SPEND_LOG="knowledge/cost_log.json"
DAILY_BUDGET=${DAILY_BUDGET:-10}

# Check current spend
total=$(python3 -c "import json; log=json.load(open('$SPEND_LOG')); print(log.get('total_spend', 0))")

if (( $(echo "$total >= $DAILY_BUDGET" | bc -l) )); then
    echo "🚨 BUDGET EXHAUSTED: \$$total/\$$DAILY_BUDGET"
    echo "Stopping all non-essential API calls."
    
    # Disable all skills that call APIs
    export API_ENABLED=0
    
    # Alert Telegram
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d "chat_id=${TELEGRAM_CHAT_ID}" \
          -d "text=🚨 Budget exhausted: \$$total/\$$DAILY_BUDGET. All API calls suspended until reset." \
          > /dev/null 2>&1
    fi
    
    # Disable scheduled tasks
    crontab -l | grep -v "cost-governor\|budget" > /tmp/cron.tmp
    crontab /tmp/cron.tmp 2>/dev/null || true
    
    exit 1
fi
```

### Step 6: Request Batching

```python
#!/usr/bin/env python3
"""
batch_queuer.py — queue non-urgent requests for batch processing
"""
import json, os, time
from datetime import datetime

BATCH_QUEUE = 'knowledge/batch_queue.json'

def enqueue(task_type, prompt, priority='low'):
    queue_item = {
        'task_type': task_type,
        'prompt': prompt,
        'priority': priority,
        'enqueued_at': datetime.now().isoformat()
    }
    
    # Load existing queue
    try:
        with open(BATCH_QUEUE) as f:
            queue = json.load(f)
    except:
        queue = []
    
    queue.append(queue_item)
    
    with open(BATCH_QUEUE, 'w') as f:
        json.dump(queue, f, indent=2)
    
    return len(queue) - 1

def process_batch():
    """Process queued requests during low-activity window"""
    with open(BATCH_QUEUE) as f:
        queue = json.load(f)
    
    # Only process in off-peak (after work hours)
    hour = datetime.now().hour
    if 8 <= hour <= 22:  # Don't batch during active hours
        print(f"Skipping batch — still in active hours ({hour}:00)")
        return
    
    # Process up to 5 queued items
    processed = 0
    while queue and processed < 5:
        item = queue.pop(0)
        print(f"Processing batch item: {item['task_type']}")
        # Execute task (call API)
        # ...
        processed += 1
    
    with open(BATCH_QUEUE, 'w') as f:
        json.dump(queue, f, indent=2)
    
    print(f"Batch complete: {processed} items, {len(queue)} remaining")

# Run daily at 22:00
# crontab: 0 22 * * * python3 batch_queuer.py --process
```

## Model Cost Reference

| Model | Input $/1M | Output $/1M | Best For |
|---|---|---|---|
| Claude Sonnet 4-6 | $3.00 | $15.00 | Complex reasoning, planning |
| Claude Haiku | $0.25 | $1.25 | Routine tasks, summaries |
| Gemini Flash 2.0 | $0.10 | $0.40 | High-volume, low-complexity |
| Llama 3.3 70B | $0.70 | $0.90 | Medium tasks, fallback |

## Budget Rules

| Spend | Action |
|---|---|
| 0-60% | Normal operations |
| 60-80% | Switch to cheaper models, batch requests |
| 80-99% | Suspend non-critical tasks, alert Reece |
| 100% | Hard stop — no API calls until midnight reset |

## Output

Cost tracking goes to:
- `knowledge/cost_log.json` — per-call cost log, daily totals
- `knowledge/batch_queue.json` — queued batch requests
- Telegram alert at 80% threshold
- Weekly cost report: model breakdown, total spend, efficiency

## Cross-References

- `COST_GOVERNOR.md` — budget policy
- `AUTOMATION_TRIGGERS.md` — cron scheduling
- `telegram-alert` — alert integration

## Troubleshooting

| Problem | Solution |
|---|---|
| Spend log corrupted | Reset to `{"date":today, "calls":[], "total_spend":0}` |
| Telegram alerts not sending | Check bot token, retry manually |
| Model API down | Fallback chain: primary → fallback1 → fallback2 → local |
| Budget not resetting at midnight | Check system timezone matches expected |