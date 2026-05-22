# Active Targets

This directory tracks all currently monitored payment gateway targets.

## Entry Format

Each target gets its own JSON file:
```json
{
  "domain": "<target_domain>",
  "first_seen": "YYYY-MM-DD",
  "last_scan": "YYYY-MM-DD",
  "priority": "P1-P5",
  "score": 0-1000,
  "tech_stack": [],
  "attack_vectors": [],
  "status": "recon|intel|hunter|operations|complete",
  "notes": ""
}
```

## Management

- RECON bot adds new targets here automatically
- INTEL bot updates scores here
- HUNTER bot marks targets when deep-dive begins
- OPERATIONS bot marks complete when engagement finishes
