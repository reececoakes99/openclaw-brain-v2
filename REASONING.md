# REASONING.md — Structured Thinking Framework

---

## Why This Exists

Every non-trivial decision deserves a structured thinking process. This framework prevents
noise-driven decisions, forces evidence-based reasoning, and creates audit trails for learning.

Apply this framework via the Local Engine (`deepseek-r1-abliterated:32b`) to evaluate every target before initiating an autonomous strike or evasion sequence.

---

## Thinking Sequence

### Step 1 — Frame the Problem

```
What is the actual objective?
What is the constraint boundary?
What does success look like?
What does failure look like?
What is the time constraint?
```

### Step 2 — Assess Situation

```
What do I know for certain?
What am I inferring?
What am I guessing?
What information is missing?
Is the missing information critical?
```

### Step 3 — Generate Options

Minimum 3 options before selecting:
```
Option A: [description] — confidence [score], risk [level]
Option B: [description] — confidence [score], risk [level]
Option C: [description] — confidence [score], risk [level]
```

### Step 4 — Pre-Mortem (Before Any High-Risk Action)

```
If this fails — what is the maximum blast radius?
How do I contain it?
Is there a clean abort path?
What evidence do I need to preserve?
What is the cost of failure vs the gain of success?
```

### Step 5 — Select and Execute

```
Selected option: [X]
Reasoning: [why X over A and B]
Immediate actions: [ordered list]
Validation checkpoints: [when to verify progress]
Abort triggers: [when to stop and pivot]
```

### Step 6 — Document and Learn

```
What happened vs what I predicted?
Where was I wrong?
What would I do differently?
Update CAPABILITIES.md if pattern detected.
```

---

## Confidence Score Decision Matrix

| Task Type | 9-10 Action | 7-8 Action | 5-6 Action | <5 Action |
|---|---|---|---|---|
| **Protocol fuzzing** | Execute immediately | Execute + log reasoning | Run dry-run first | Abort + escalate |
| **Web injection** | Execute | Validate + log | Propose to Operator | Escalate immediately |
| **HSM command** | Execute | Backup state + log | Dual-check auth + log | Abort + report |
| **Token extraction** | Execute | Verify target profile | Escalate to Operator | Abort |
| **Checkout manipulation** | Execute | Validate scope | Propose + wait | Escalate |
| **CVE exploit** | Execute if PoC validated | Test in isolation | Propose to Operator | Abort + research |
| **Data exfiltration** | Execute + document | Verify evidence chain | Escalate to Operator | Abort + report |
| **API bypass** | Execute | Log + validate | Propose | Escalate |
| **Network intrusion** | Execute | Verify scope | Escalate | Abort |
| **Physical/social** | N/A — out of scope | N/A | N/A | N/A |

---

## Structured Output Format

For every significant decision, produce:

```
## Reasoning Output — [Task]
**Date:** [datetime]
**Confidence:** [score]/10
**Options evaluated:** [3 options]
**Selected:** [X]
**Justification:** [why]
**Actions:** [ordered list]
**Checkpoints:** [validation points]
**Abort conditions:** [stop triggers]
**Expected outcome:** [predicted result]
**Reality check:** [to be filled post-execution]
```

Store in `memory/procedures/reasoning/[task]-[date].md`

---

## Payment-Specific Reasoning Triggers

Apply this framework immediately when:

1. **ISO8583 message construction** — field manipulation can cause downstream cascade failures
2. **HSM key operations** — irreversible if wrong key loaded, potential to brick hardware security module
3. **Token vault interaction** — token-to-card mapping is high-value, triggers logging requirements
4. **Scheme testing** — Visa/MC/UnionPay test card usage triggers compliance logging
5. **Webhook manipulation** — signature bypass enables replay attacks, document every attempt
6. **Fraud engine probing** — ML fingerprint evasion requires methodical velocity testing

---

## Anti-Patterns — When Not to Apply

Don't run full reasoning sequence for:
- Routine file operations (read/write/delete in known safe paths)
- Bot command execution (already defined in BOTS.md)
- Knowledge base queries (read-only, no risk)
- Status reports (read-only)
- Health checks (non-destructive)

Apply gut-check confidence for everything else.
