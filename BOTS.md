# BOTS.md — Bot Fleet Command System

---

## Overview

Four specialized bots form a unified intelligence network. Each operates independently with shared context, continuous feedback loops, and autonomous decision trees. Nothing is forgotten. Everything compounds.

```
         ┌─────────────────────────────────────────┐
         │           ELKIN COMMANDER               │
         │   Session startup, escalation, reports   │
         └──────────┬──────────────────────────────┘
                    │
    ┌───────────────┼───────────────┬───────────────┐
    │               │               │               │
  RECON ──────── INTEL ──────── HUNTER ────── OPERATIONS
    │               │               │               │
    └───────────────┴───────────────┴───────────────┘
                         │
              ┌──────────┴──────────┐
              │   KNOWLEDGE BASE    │
              │  targets/           │
              │  gateway_profiles/  │
              │  cve_tracker/       │
              │  payment_protocol_db/
              │  bot_activity_logs/
              │  bot_queue/         │
              └─────────────────────┘
```

---

## Bot Communication Protocol

Each bot writes output to the knowledge base and signals the next bot via queue files.

| Signal | From | To | Trigger |
|---|---|---|---|
| `recon_pending.json` | RECON | INTEL | New target discovered or target updated |
| `intel_scored.json` | INTEL | HUNTER | Target scored P1-P2 |
| `hunter_ready.json` | HUNTER | OPERATIONS | Attack package complete |
| `ops_complete.json` | OPERATIONS | INTEL | Feedback loop — engagement results |
| `escalation.json` | Any bot | OPERATIONS + Reece | P1 confirmed, critical event |

---

## Shared Knowledge Base

Every finding goes into `knowledge/` for permanent record and cross-reference:

```
knowledge/
├── targets/                          # All discovered payment gateways
│   ├── active/                      # Priority scored, actively monitored
│   ├── high_priority/               # P1-P2, HUNTER queued
│   └── archived/                   # Abandoned, out of scope, or completed
│
├── gateway_profiles/                 # Per-gateway intelligence
│   ├── <domain>/
│   │   ├── surface_scan.json       # RECON output
│   │   ├── tech_stack.json         # Technology fingerprint
│   │   ├── vulnerability_findings.json  # HUNTER findings
│   │   ├── payment_flow_mapping.json   # Transaction lifecycle
│   │   ├── attack_vectors.json     # Ranked exploit paths
│   │   ├── exposure_timeline.json  # Discovery → engagement history
│   │   ├── score_history.json      # INTEL scoring over time
│   │   └── engagement_prep/        # OPERATIONS-ready attack package
│   │       ├── playbook.yaml
│   │       ├── payload_templates/
│   │       ├── exploit_sequence.md
│   │       ├── evidence/
│   │       └── chain_of_custody.json
│
├── cve_tracker/                     # CVEs matched to payment stacks
│   ├── active/                     # Affects known targets
│   └── archive/                    # No current targets affected
│
├── breach_correlation/              # Dark web + breach data matches
│   ├── confirmed/                  # Verified breach data
│   └── suspected/                  # Potential matches, unconfirmed
│
├── payment_protocol_db/             # Protocol fingerprints
│   ├── iso8583_variants.json       # HISO93/HISO87 fingerprints
│   ├── pos_protocols.json          # SPDH, HPDH, XFlow signatures
│   └── token_formats.json          # Token generation patterns
│
├── bot_activity_logs/              # All bot actions timestamped
│   ├── recon/
│   ├── intel/
│   ├── hunter/
│   ├── operations/
│   └── health_check.json
│
└── bot_queue/                      # Inter-bot communication
    ├── recon_pending.json
    ├── intel_scored.json
    ├── hunter_ready.json
    ├── ops_complete.json
    ├── escalation.json
    └── trigger_config.json
```

---

## Bot Fleet Status

Each bot has a health status written to `knowledge/bot_activity_logs/health_check.json`:

```json
{
  "timestamp": "2026-05-08T13:00:00Z",
  "recon": {
    "status": "active",
    "last_run": "2026-05-08T12:55:00Z",
    "last_cycle": "complete",
    "targets_found": 12,
    "errors": 0
  },
  "intel": {
    "status": "idle",
    "last_run": "2026-05-08T12:00:00Z",
    "last_cycle": "complete",
    "targets_scored": 12,
    "p1_triggered": 1
  },
  "hunter": {
    "status": "idle",
    "last_run": "2026-05-08T11:30:00Z",
    "last_cycle": "complete",
    "packages_built": 3,
    "p0_confirmed": 1
  },
  "operations": {
    "status": "standby",
    "last_run": null,
    "last_cycle": null,
    "engagements_active": 0,
    "findings_total": 0
  }
}
```

---

## Bot Commands (Operator Can Trigger)

| Command | Effect |
|---|---|
| `BOT RECON START` | Activate RECON scan cycle immediately |
| `BOT RECON STOP` | Halt RECON scanning |
| `BOT INTEL RUN` | Trigger INTEL correlation cycle now |
| `BOT HUNTER <target>` | Trigger HUNTER deep-dive on specific target |
| `BOT OPS <target>` | Load OPERATIONS on specific target (requires engagement_config) |
| `BOT STATUS` | Full bot fleet status to Telegram |
| `BOT QUEUE` | Show current queue depths |
| `BOT ESCALATE <target>` | Mark target P1, trigger HUNTER immediately |

---

## Learning Loop

Every bot cycle improves the system:

```
RECON discovers new gateway
  → INTEL scores it
  → HUNTER builds exploit package
  → OPERATIONS executes on target
  → RESULT feeds back to INTEL
  → INTEL updates scoring model (what worked, what didn't)
  → RECON refines scan patterns (what found things, what didn't)
  → System compounds — gets smarter every cycle
```

**Learning metrics tracked per 100 cycles:**
- RECON: false positive rate, discovery yield
- INTEL: scoring accuracy (was P1 actually exploitable?)
- HUNTER: exploit success rate, time-to-access
- OPERATIONS: clean execution rate, evidence completeness