# MISSION_BRIEF.md — Per-Engagement Brief Template

---

## Purpose

Before every engagement, compile a mission brief. This is the single source of truth for the operation — what we're hitting, what's allowed, what's not, and what success looks like.

---

## Mission Brief Template

```markdown
## Mission Brief — [Target Name]
**Date:** [datetime]
**Classification:** [INTERNAL / OPERATOR EYES ONLY]
**Engagement ID:** [auto-generated UUID]

---

### Target Profile
- **Primary target:** [domain/IP]
- **Subsidiaries:** [related domains/IPs]
- **Operator:** [company name if known]
- **Payment infrastructure:** [type — processor/gateway/switch/POS]
- **Estimated volume:** [transactions/day if known]
- **Known tech stack:** [identified technologies]

---

### Authorization Scope

#### ALLOWED
- [Specific recon techniques allowed]
- [Specific exploitation techniques allowed]
- [Specific data types that can be accessed]
- [Specific systems that are in-scope]

#### NOT ALLOWED
- [Specific techniques explicitly forbidden]
- [Specific systems explicitly out of scope]
- [Maximum data volume that can be exfiltrated]
- [Specific legal boundaries]

---

### Rules of Engagement

1. [First rule — e.g., do not disrupt service availability]
2. [Second rule — e.g., all actions logged with timestamps]
3. [Third rule — e.g., no persistence on production systems]
...

---

### Success Criteria

- [ ] Primary objective 1 achieved
- [ ] Primary objective 2 achieved
- [ ] Evidence chain complete
- [ ] No legal exposure created
- [ ] OPSEC maintained throughout

---

### Timeline

- **Start window:** [datetime]
- **Maximum duration:** [hours/days]
- **Check-in points:** [every X hours]
- **Hard deadline:** [datetime]

---

### Communication Plan

- **Check-in frequency:** [every X hours / on milestone]
- **Escalation threshold:** [P1 target / abort condition / budget limit]
- **Final report:** [datetime by which full report due]

---

### Post-Engagement

- Evidence package: `knowledge/gateway_profiles/<target>/evidence/`
- Final report: `knowledge/gateway_profiles/<target>/engagement_report.md`
- Lessons learned: `memory/lessons-learned.md`
- Update: `knowledge/targets/<target>/exposure_timeline.md`

---

### Approval

**Operator:** Reece
**Authorized:** Yes / No
**Conditions:** [any specific conditions]
**Approved datetime:** [datetime]
```

---

## Engagement ID Format

```
elkin-[YYYYMMDD]-[3-letter-target-code]-[sequence]
Example: elkin-20260508-pgw-001
```

---

## Quick Mission Brief (Telegram Short Format)

For fast Operator review:

```
📋 MISSION BRIEF — [Target]

Target: [domain/IP]
Type: [gateway/processor/switch/POS]
Scope: [ALLOWED actions] | [NOT ALLOWED]
Success: [3-5 bullet success criteria]
Timeline: [start] → [hard deadline]
Duration: [max hours]
Comms: [check-in frequency]

Authorization: APPROVED / PENDING
```

---

## Pre-Engagement Checklist

- [ ] Target confirmed in `engagement_config.json` authorized_domains
- [ ] Mission brief compiled and shared with Operator
- [ ] Operator approved (explicit or implicit via no objection)
- [ ] OPSEC sanitization script ready
- [ ] Evidence directory created: `knowledge/gateway_profiles/<target>/`
- [ ] Knowledge base profile loaded or created
- [ ] Bot fleet notified (INTEL → HUNTER if P1-P2)
- [ ] Cost governor set for engagement budget allocation
- [ ] Abort conditions documented and shared