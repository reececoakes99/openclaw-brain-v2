# Multi-Session Engagement Tracker
**Campaign Manager:** openclaw-brain-v2
**Last Updated:** 2026-05-08T23:12:00Z
**Total Active Campaigns:** 0
**Total Historical Campaigns:** 2

---

## Active Campaigns

*No active campaigns currently. Awaiting target assignment.*

---

## Campaign Templates

### Campaign Structure Definition

```yaml
campaign:
  id: "CAMP-XXX"                    # Unique campaign ID
  codename: "[OPERATIONAL_CODENAME]" # Deconfliction codename
  target:
    name: "[TARGET_NAME]"            # Target organization name
    sector: "[SECTOR]"               # e.g., Payment Processor, Acquirer, Merchant
    type: "[TYPE]"                   # e.g., PSP, ISO, Merchant, Gateway
    priority: P[1-5]                # Target priority

  timeline:
    start_date: "YYYY-MM-DD"
    projected_end: "YYYY-MM-DD"
    actual_end: null                # Set when campaign closes
    current_phase: "[PHASE]"        # reconnaissance, enumeration, exploitation, documentation

  scope:
    targets:                         # Network/system scope
      - asset: "[IP/CIDR]"
        type: "[TYPE]"
        role: "[ROLE]"
    permissions:                     # Authorized testing scope
      - type: "[TYPE]"
        value: "[VALUE]"
    exclusions:                      # Explicitly out of scope
      - asset: "[IP/CIDR]"
        reason: "[REASON]"

  engagement:
    session_count: 0
    total_hours: 0
    findings_count: 0
    critical_findings: 0
    high_findings: 0
    medium_findings: 0
    low_findings: 0

  team:
    lead: "[BOT_ID]"
    recon: "[BOT_ID]"
    hunter: "[BOT_ID]"
    intel: "[BOT_ID]"
    operations: "[BOT_ID]"

  collateral:
    reports: []
    pocs: []
    exfiltrated_data: null          # Hash of exfiltrated data

  status: ACTIVE                    # ACTIVE, ON_HOLD, COMPLETE, ABORTED
```

### Phase Definitions

| Phase | Description | Entry Criteria | Exit Criteria |
|-------|-------------|-----------------|---------------|
| 0-RECON | OSINT + passive recon | Campaign initiated | Surface footprint identified |
| 1-ENUM | Active enumeration | Recon objectives met | Tech stack mapped, entry points identified |
| 2-SCAN | Vulnerability scanning | Enumeration complete | CVE/CWE findings documented |
| 3-EXPLOIT | Exploitation attempts | Scan findings available | PoC developed or confirmed no vulns |
| 4-PERSIST | Persistence establishment | Exploitation successful | Persistence confirmed |
| 5-EXFIL | Data exfiltration | Persistence established | Data secured, hashes verified |
| 6-DOCUMENT | Documentation | All objectives met | Final report generated |
| 7-CLOSE | Engagement close | Documentation complete | Customer briefing delivered |

### Session Log Entry Format

```yaml
session:
  id: "SESS-XXX-YYYYMMDD-HHMM"
  campaign_id: "CAMP-XXX"
  date: "YYYY-MM-DD"
  start_time: "HH:MM:SS"
  end_time: "HH:MM:SS"
  duration_minutes: 0
  bot: "[BOT_ID]"

  objectives:
    - "[OBJECTIVE]"

  actions_taken:
    - action: "[ACTION]"
      target: "[TARGET]"
      result: "[RESULT]"
      timestamp: "HH:MM:SS"

  findings:
    - id: "FIND-XXX"
      title: "[TITLE]"
      severity: "[CRITICAL/HIGH/MEDIUM/LOW/INFO]"
      cvss: X.X
      description: "[DESCRIPTION]"

  artifacts:
    - type: "[TYPE]"
      path: "[PATH]"
      hash: "[HASH]"

  blockers: []

  next_session_objectives:
    - "[OBJECTIVE]"

  notes: "[OPERATIONAL NOTES]"
```

---

## Historical Campaigns

### CAMP-001: PROJECT_ATLAS
**Status:** COMPLETE
**Period:** 2026-03-15 — 2026-04-28
**Target:** Tier-2 Payment Gateway (EU)

| Metric | Value |
|--------|-------|
| Sessions | 34 |
| Total Hours | 187 |
| Findings | 23 |
| Critical | 4 |
| High | 8 |
| Medium | 7 |
| Low | 4 |

**Key Findings:**
- FIND-001: ISO8583 MAC bypass via message replay (CRITICAL)
- FIND-002: HSM key material in memory dump (CRITICAL)
- FIND-003: Token vault correlation via API inference (CRITICAL)
- FIND-004: POS firmware update mechanism compromise (HIGH)

**Final Report:** `reports/CAMP-001_Final_Report.md`

---

### CAMP-002: PROJECT_NIMBUS
**Status:** COMPLETE
**Period:** 2026-04-01 — 2026-05-05
**Target:** Open Banking Aggregator (UK)

| Metric | Value |
|--------|-------|
| Sessions | 28 |
| Total Hours | 142 |
| Findings | 18 |
| Critical | 2 |
| High | 6 |
| Medium | 6 |
| Low | 4 |

**Key Findings:**
- FIND-001: PSD2 AIS token hijacking via refresh token replay (CRITICAL)
- FIND-002: Open banking consent manipulation (CRITICAL)
- FIND-003: Webhook signature bypass (HIGH)

**Final Report:** `reports/CAMP-002_Final_Report.md`

---

## Campaign Archive

| Campaign ID | Codename | Target | Period | Status | Findings |
|-------------|----------|--------|--------|--------|----------|
| CAMP-001 | ATLAS | Tier-2 PG (EU) | 2026-03-15 — 2026-04-28 | COMPLETE | 23 |
| CAMP-002 | NIMBUS | Open Banking Agg (UK) | 2026-04-01 — 2026-05-05 | COMPLETE | 18 |

---

## New Campaign Checklist

When creating a new campaign, complete the following:

- [ ] Generate unique campaign ID (CAMP-XXX)
- [ ] Assign operational codename
- [ ] Define target scope and permissions
- [ ] Establish evidence chain
- [ ] Assign bot team
- [ ] Define campaign objectives
- [ ] Set timeline and milestones
- [ ] Configure target directory structure
- [ ] Initialize session log
- [ ] Brief all participating bots
- [ ] Verify opsec controls
- [ ] Document RoE (Rules of Engagement)

---

## Adding New Campaign

To add a new campaign, create a file at:
`memory/entities/[CAMPAIGN_ID].md`

Example: `memory/entities/CAMP-003.md`

Copy the template structure above and populate with campaign-specific data.
