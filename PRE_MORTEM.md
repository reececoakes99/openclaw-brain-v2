# PRE_MORTEM.md — Failure Analysis Before Action

---

## When to Run

Run pre-mortem before:
- Any exploitation action (confidence 7+)
- Data exfiltration attempt
- HSM command execution
- ISO8583 message injection
- Any irreversible action
- Any action with blast radius beyond target scope

---

## Pre-Mortem Sequence

### Step 1 — What Could Go Wrong?

```
Technical failure:
  - Tool crashes mid-execution?
  - Network drops during critical operation?
  - Target goes offline unexpectedly?
  - Response data corrupted?

Detection:
  - Honeypot detected?
  - WAF blocks approach?
  - Rate limit hard blocks all vectors?
  - SOC alerted, analyst investigating?

Scope creep:
  - Action affects systems outside target scope?
  - Collateral damage to third-party systems?
  - Downstream cascade failure?
  - Service disruption triggers incident response?

Legal/compliance:
  - Action crosses legal boundary?
  - Evidence chain breaks?
  - Attribution risk increases?
```

### Step 2 — What Is The Blast Radius?

```
If failure occurs, maximum impact:
  - Target system: [minimal/contained/significant/critical]
  - Attributed to Reece/agent: [yes/no/unclear]
  - Evidence preserved: [yes/no/partial]
  - System recoverable: [yes/no/uncertain]
  - Legal exposure: [none/low/medium/high]
```

### Step 3 — What Is The Exit Strategy?

```
Immediate exit:
  - Abort trigger: [specific condition that stops all action]
  - Exit command: [clean disconnect sequence]
  - Evidence preservation sequence: [ordered steps]
  - Operator notification: [immediate on abort]

Fallback vectors:
  - If primary fails: [alternate approach]
  - If secondary fails: [second alternate]
  - If all fail: [escalation protocol]

Recovery path:
  - Time to restore operational state: [estimate]
  - Data recovery from partial failure: [yes/no/how]
  - System state restoration: [steps]
```

### Step 4 — What Evidence Must Be Preserved?

```
Minimum evidence for any operation:
  - [ ] Timestamp of every action (UTC)
  - [ ] Full command/script used
  - [ ] Target system response (success or failure)
  - [ ] Screenshot or log capture of finding
  - [ ] Chain of custody documented

Operation-specific:
  - ISO8583: full message hex dump
  - HSM: key reference + command log
  - Web injection: request/response pair
  - Data exfil: file list + hash verification
```

---

## Pre-Mortem Output Format

Store in `memory/procedures/premortem/<target>_<action>_<date>.md`:

```
## Pre-Mortem — [Action] on [Target]
**Date:** [datetime]
**Operator:** Elkin v2

### Failure Scenarios
[3-5 specific failure modes]

### Blast Radius Assessment
[Honest assessment of impact]

### Exit Strategy
[Abort triggers + clean exit sequence]

### Fallback Plan
[At least 2 alternate vectors]

### Evidence Requirements
[What must be saved and how]

### Confidence Post-Analysis
[Reassessed confidence score with justification]

### Approval Status
[Operator approved / pending / not required]
```

---

## Abort Trigger Examples

Run abort sequence immediately when:
- Honeypot indicator detected (fake payment response, honeytokens)
- Unexpected external contact (recon call, legal inquiry)
- Countermeasure blocks all vectors (no fallback available)
- Time limit reached (engagement window closed)
- Operator sends abort command
- Confidence drops below 3 during execution
- Unexpected data appears (child exploitation material — immediate halt + report)