# NEOPAY_FEEDBACK.md — Result Ingestion Protocol

How to classify, store, and act on neopay command execution results.

---

## Result Classification

Every neopay command produces one of these outcomes:

| Classification | Criteria | Confidence Impact | Next Action |
|---|---|---|---|
| `vulnerability_confirmed` | Exploit succeeded, evidence captured | +1.0 | Write to gateway_profiles, escalate if P2→P1, package for OPS |
| `weakness_identified` | Unexpected behavior but not exploitable yet | +0.5 | Queue for deeper testing, update attack_vectors.json |
| `inconclusive` | No clear result, needs different approach | 0 | Re-queue with variant parameters, increase confidence threshold |
| `blocked` | WAF/IDS/rate-limit/honeypot detected | +0.5 (detection = intel) | Log to bot_evasion.md, update evasion techniques, rotate approach |
| `failed` | Tool error, network issue, script crash | -0.5 | Log to memory/ERRORS.md, diagnose, fix, retry once |
| `timeout` | No response within threshold | 0 | Verify connectivity, try alternate port/protocol, log |

---

## Knowledge Update Rules

### On `vulnerability_confirmed`:
```
1. Write finding → knowledge/gateway_profiles/<target>/vulnerability_findings.json
   Format: {finding_id, timestamp, command_used, DE_fields_affected, evidence_path, severity}
2. Update → knowledge/gateway_profiles/<target>/attack_vectors.json (mark vector as confirmed)
3. Log evidence → knowledge/gateway_profiles/<target>/engagement_prep/evidence/
4. Update → memory/TTP_INDEX.md (add/update technique)
5. If target was P2 → recalculate score, promote to P1 if threshold met
6. Notify Operator via Telegram with finding summary
7. Write to knowledge/bot_activity_logs/<bot>/YYYY-MM-DD.md
```

### On `weakness_identified`:
```
1. Append → knowledge/gateway_profiles/<target>/attack_vectors.json (new potential vector)
2. Queue deeper test → knowledge/bot_queue/hunter_queue.json (specific follow-up)
3. Update → knowledge/gateway_profiles/<target>/surface_scan.json (new surface data)
4. Log → knowledge/bot_activity_logs/<bot>/YYYY-MM-DD.md
```

### On `blocked`:
```
1. Log detection event → knowledge/bot_activity_logs/<bot>/YYYY-MM-DD.md
2. Document detection mechanism → bot_evasion.md (what triggered, what to avoid)
3. Update → knowledge/gateway_profiles/<target>/tech_stack.json (WAF/IDS info)
4. Rotate approach: change timing, proxy, UA, technique
5. If 3+ blocks on same target → escalate to Operator for strategy review
```

### On `inconclusive`:
```
1. Re-queue → knowledge/bot_queue/hunter_queue.json with:
   - Different parameters
   - Higher confidence threshold requirement (original + 1)
   - Max 3 re-queues before marking target as "needs manual review"
2. Log attempt → knowledge/bot_activity_logs/<bot>/YYYY-MM-DD.md
```

### On `failed`:
```
1. Log error → memory/ERRORS.md with full context (command, args, error output)
2. Log error → .learnings/ERRORS.md (for pattern detection)
3. Diagnose: check connectivity, dependencies, script version
4. Retry once with fixed parameters
5. If retry fails → escalate with error context
```

---

## Confidence Score Adjustment

After every neopay execution, adjust target confidence:

| Result | Score Change | Maximum | Minimum |
|---|---|---|---|
| vulnerability_confirmed | +1.0 per finding | 10/10 | — |
| weakness_identified | +0.5 | 10/10 | — |
| blocked (detection = intel) | +0.5 | 10/10 | — |
| failed (tool error) | -0.5 | — | 1/10 |
| false_positive confirmed | -2.0 | — | 1/10 |
| inconclusive | 0 | — | — |

Write updated confidence to: `knowledge/gateway_profiles/<target>/score_history.json`

---

## Evidence Chain Integration

All neopay outputs auto-classify into evidence categories:

| Evidence Category | Neopay Output Types |
|---|---|
| **A (Critical)** | Confirmed exploitation: shell access, data retrieved, successful injection |
| **B (High)** | Technical proof: response code anomalies, error messages revealing internals |
| **C (Medium)** | Supporting: scan results, fingerprints, protocol analysis |
| **D (Low)** | Context: timing data, connection metadata, reconnaissance |

Evidence metadata format:
```
{
  "evidence_id": "EVD-YYYY-MM-DD-HHMMSS-<category>",
  "timestamp_utc": "ISO8601",
  "command": "<full command executed>",
  "target": "<host:port>",
  "category": "A|B|C|D",
  "output_path": "<path to raw output>",
  "sha256": "<hash of raw output file>",
  "classification": "<result classification>",
  "confidence_at_time": <score>
}
```

---

## Queue Promotion Logic

| Condition | Action |
|---|---|
| P3 target + vulnerability_confirmed | Promote to P2, queue for HUNTER deep-dive |
| P2 target + vulnerability_confirmed (severity HIGH+) | Promote to P1, immediate HUNTER escalation |
| P2 target + 3 weaknesses identified on same surface | Promote to P1 (compound risk) |
| Any target + `blocked` 3+ times | Flag for evasion strategy review before retry |
| P1 target + all vectors exhausted | Mark COMPLETE, archive, schedule 90-day recheck |

Write promotion events to: `knowledge/bot_queue/escalation.json`

---

## Feedback Loop to INTEL Bot

After every HUNTER or OPS execution cycle, write feedback for INTEL scoring refinement:

```
knowledge/bot_queue/ops_complete.json append:
{
  "target_id": "<target>",
  "timestamp": "ISO8601",
  "commands_executed": [<list of commands>],
  "results": [<list of classifications>],
  "confirmed_vectors": [<attack_vector_ids that worked>],
  "failed_vectors": [<attack_vector_ids that failed>],
  "detection_events": [<evasion failures>],
  "scoring_feedback": {
    "original_score": <number>,
    "recommended_adjustment": <+/- number>,
    "reasoning": "<why>"
  }
}
```

INTEL bot uses this to:
1. Refine scoring model (was P1 actually exploitable?)
2. Adjust weight factors in scoring formula
3. Update threat surface calculations for similar targets
