# Campaign Manager — Track Multi-Session Engagement Lifecycle

## Metadata

- **Skill Name:** campaign-manager
- **Type:** Engagement Tracking / Campaign Orchestration
- **Author:** OpenClaw Brain v2
- **Version:** 1.0.0
- **Last Updated:** 2026-05-09

---

## Overview

The Campaign Manager skill orchestrates the full lifecycle of each engagement campaign from initial reconnaissance through post-engagement archiving. It maintains structured session logs, tracks phase progression, documents all findings with evidence, generates progress reports, and manages campaign escalation triggers.

Each engagement against a target is treated as a campaign with a defined progression through standardized phases. This ensures nothing falls through the cracks, findings are properly documented for reporting, and campaign health can be measured objectively over time.

---

## Trigger Conditions

**Autonomous Triggers:**
- User initializes a new campaign: "start campaign against <target>"
- End of each engagement session: auto-generate session summary
- Weekly: `0 9 * * 1` (Monday 09:00 UTC) — generate weekly Telegram report
- Phase transition detected (via other skills reporting phase change)

**Manual Triggers:**
- User: "start new campaign for <target>"
- User: "how is campaign <target> going?"
- User: "log this finding to campaign <target>"
- User: "end campaign <target>" or "archive campaign <target>"
- User: "generate report for campaign <target>"
- User: "campaign stats for <target>"
- User: "list all active campaigns"
- User: "escalate campaign <target>"

---

## When to Use

| Scenario | Action |
|---|---|
| New engagement begins | Initialize campaign directory and tracker |
| End of every engagement session | Log session with findings and next steps |
| Weekly client update | Generate weekly summary report |
| Target goes dark (unresponsive) | Trigger escalation workflow |
| Finding rate drops significantly | Analyze phase viability, consider pivot |
| Countermeasure detected during engagement | Log detection, update TTP map |
| Engagement complete | Generate final report, archive campaign |
| Client requests status update | Pull campaign stats, generate report |

---

## Operational Procedure

### Phase 1 — Campaign Initialization

**Step 1.1 — Create Directory Structure**

For a new target, create the full directory tree:

```bash
TARGET_NAME="target-alpha"
CAMPAIGN_DIR="/root/.nanobot/workspace/openclaw-brain-v2/knowledge/gateway_profiles/${TARGET_NAME}"
mkdir -p "${CAMPAIGN_DIR}"/{
  sessions,        # Individual session logs
  findings,       # Finding-specific evidence
  reports,        # Generated reports
  screenshots,   # Screenshots and visual evidence
  logs,           # Raw log captures
  poc,            # Proof-of-concept artifacts
  iocextract,     # Extracted indicators
  archived        # Post-engagement archived material
}
chmod -R 700 "${CAMPAIGN_DIR}"
```

**Step 1.2 — Initialize Campaign Log JSON**

```bash
cat > "${CAMPAIGN_DIR}/campaign_log.json" << 'EOF'
{
  "campaign_id": "camp_$(date +%Y%m%d_%H%M%S)",
  "target": "TARGET_NAME",
  "target_domain": "example.com",
  "target_ip_ranges": [],
  "payment_providers": [],
  "status": "active",
  "created": "2026-05-09T00:00:00Z",
  "last_activity": "2026-05-09T00:00:00Z",
  "current_phase": "recon",
  "phase_history": [
    {
      "phase": "recon",
      "started": "2026-05-09T00:00:00Z",
      "completed": null,
      "sessions_spent": 0,
      "notes": "Campaign initialized"
    }
  ],
  "sessions": [],
  "findings": [],
  "statistics": {
    "total_sessions": 0,
    "total_findings": 0,
    "p1_findings": 0,
    "p2_findings": 0,
    "p3_findings": 0,
    "p4_findings": 0,
    "hours_invested": 0,
    "critical_findings": 0,
    "findings_this_week": 0
  },
  "escalation_flags": {
    "target_dark": false,
    "finding_rate_drop": false,
    "countermeasure_detected": false,
    "client_notify": false
  },
  "references": {
    "scope_document": "knowledge/scopes/TARGET_NAME_scope.pdf",
    "rules_of_engagement": "knowledge/roe/TARGET_NAME_roe.pdf"
  },
  "archived": false,
  "archived_date": null
}
EOF
```

**Step 1.3 — Update Memory CAMPAIGN_TRACKER**

```bash
# Append to the master campaign tracker
cat >> /root/.nanobot/workspace/openclaw-brain-v2/memory/CAMPAIGN_TRACKER.md << EOF

## $(date '+%Y-%m-%d') — Campaign: ${TARGET_NAME}

| Field | Value |
|---|---|
| Status | 🟢 Active |
| Current Phase | recon |
| Target | ${TARGET_NAME} |
| Created | $(date -Iseconds) |
| Sessions | 0 |
| Findings | 0 |

EOF
```

---

### Phase 2 — Session Logging

**Step 2.1 — Session Start**

```bash
SESSION_ID="sess_$(date '+%Y%m%d_%H%M%S')"
CURRENT_PHASE=$(jq -r '.current_phase' "${CAMPAIGN_DIR}/campaign_log.json")

# Create session directory
mkdir -p "${CAMPAIGN_DIR}/sessions/${SESSION_ID}"
cat > "${CAMPAIGN_DIR}/sessions/${SESSION_ID}/session.json" << 'EOF'
{
  "session_id": "SESSION_ID",
  "started": "$(date -Iseconds)",
  "ended": null,
  "phase": "CURRENT_PHASE",
  "actions_taken": [],
  "commands_executed": [],
  "findings_this_session": [],
  "next_steps": [],
  "screenshot_count": 0,
  "notes": ""
}
EOF
```

**Step 2.2 — During Session Logging**

Log every significant action in real-time:

```bash
log_action() {
  local session_id="$1"
  local action="$2"
  local command="$3"
  local finding_ref="$4"
  
  jq --arg ts "$(date -Iseconds)" \
     --arg action "$action" \
     --arg cmd "$command" \
     --arg finding "$finding_ref" \
     '.actions_taken += [{
       "timestamp": $ts,
       "action": $action,
       "command": $cmd,
       "finding_ref": $finding
     }]' \
     "${CAMPAIGN_DIR}/sessions/${session_id}/session.json" \
  > "${CAMPAIGN_DIR}/sessions/${session_id}/session.json.tmp" \
  && mv "${CAMPAIGN_DIR}/sessions/${session_id}/session.json.tmp" \
     "${CAMPAIGN_DIR}/sessions/${session_id}/session.json"
}
```

**Step 2.3 — Session End**

```bash
end_session() {
  local session_id="$1"
  local duration_minutes="$2"
  local findings_count="$3"
  local next_phase="$4"
  
  # Update session log
  jq --arg ended "$(date -Iseconds)" \
     --arg dur "$duration_minutes" \
     --arg finding_count "$findings_count" \
     --arg next "$next_phase" \
     '.ended = $ended | .duration_minutes = ($dur | tonumber) | .findings_this_session = $finding_count | .next_planned_phase = $next' \
     "${CAMPAIGN_DIR}/sessions/${session_id}/session.json"
  
  # Update campaign statistics
  jq --arg next_phase "$next_phase" \
     --arg dur "$duration_minutes" \
     '.last_activity = (now | strftime("%Y-%m-%dT%H:%M:%SZ")) |
      .statistics.total_sessions += 1 |
      .statistics.hours_invested += ($dur | tonumber / 60 | . * 100 | floor / 100)' \
     "${CAMPAIGN_DIR}/campaign_log.json" \
  > "${CAMPAIGN_DIR}/campaign_log.json.tmp" \
  && mv "${CAMPAIGN_DIR}/campaign_log.json.tmp" "${CAMPAIGN_DIR}/campaign_log.json"
}
```

---

### Phase 3 — Phase Tracking

**Step 3.1 — Phase Definitions**

| Phase | Description | Entry Criteria |
|---|---|---|
| **recon** | Initial reconnaissance | Campaign created |
| **surface** | Surface-level enumeration | Basic footprinting complete |
| **deep** | Deep enumeration and fingerprinting | Surface scan complete |
| **exploit** | Active exploitation | Sufficient findings, client approval |
| **persistence** | Establishing persistence | Initial access gained |
| **exfil** | Data exfiltration | Persistence established |
| **cleanup** | Covering tracks | Exfil objectives complete |
| **complete** | Engagement concluded | All objectives met |

**Step 3.2 — Phase Transition**

```bash
transition_phase() {
  local target="$1"
  local from_phase="$2"
  local to_phase="$3"
  local reason="$4"
  
  CAMPAIGN_DIR="/root/.nanobot/workspace/openclaw-brain-v2/knowledge/gateway_profiles/${target}"
  
  jq --arg ts "$(date -Iseconds)" \
     --arg from "$from_phase" \
     --arg to "$to_phase" \
     --arg reason "$reason" \
     '.phase_history += [{
       "phase": $to,
       "started": $ts,
       "completed": $ts,
       "transition_reason": $reason
     }] | .current_phase = $to | .last_activity = $ts' \
     "${CAMPAIGN_DIR}/campaign_log.json" \
  > "${CAMPAIGN_DIR}/campaign_log.json.tmp" \
  && mv "${CAMPAIGN_DIR}/campaign_log.json.tmp" "${CAMPAIGN_DIR}/campaign_log.json"
  
  echo "✅ Phase transition: ${from_phase} → ${to_phase} (${reason})"
}
```

---

### Phase 4 — Finding Documentation

**Step 4.1 — Record a Finding**

```bash
add_finding() {
  local campaign="$1"
  local finding_id="$2"
  local severity="$3"
  local category="$4"
  local title="$5"
  local description="$6"
  local evidence_path="$7"
  local cve_ids="$8"
  
  CAMPAIGN_DIR="/root/.nanobot/workspace/openclaw-brain-v2/knowledge/gateway_profiles/${campaign}"
  FINDING_JSON=$(cat << EOFJ
{
  "finding_id": "${finding_id}",
  "severity": "${severity}",
  "category": "${category}",
  "title": "${title}",
  "description": "${description}",
  "discovered_session": "${SESSION_ID}",
  "discovered_date": "$(date -Iseconds)",
  "evidence": {
    "screenshots": [],
    "logs": [],
    "poc_files": [],
    "network_captures": []
  },
  "cve_ids": [${cve_ids}],
  "status": "open",
  "verified": false,
  "remediated": false,
  "remediation_date": null
}
EOFJ
)
  
  echo "${FINDING_JSON}" | jq . > "${CAMPAIGN_DIR}/findings/${finding_id}.json"
  
  # Add evidence path if provided
  if [ -n "$evidence_path" ] && [ -f "$evidence_path" ]; then
    cp -r "$evidence_path" "${CAMPAIGN_DIR}/findings/${finding_id}/"
    jq --arg path "$evidence_path" \
       '.evidence.logs += [$path]' \
       "${CAMPAIGN_DIR}/findings/${finding_id}.json" \
    > "${CAMPAIGN_DIR}/findings/${finding_id}.json.tmp" \
    && mv "${CAMPAIGN_DIR}/findings/${finding_id}.json.tmp" \
       "${CAMPAIGN_DIR}/findings/${finding_id}.json"
  fi
  
  # Update campaign log
  jq --arg fid "$finding_id" \
     --arg sev "$severity" \
     '.findings += [{id: $fid, severity: $sev}] |
      .statistics.total_findings += 1 |
      .statistics["\($sev)_findings"] += 1' \
     "${CAMPAIGN_DIR}/campaign_log.json" \
  > "${CAMPAIGN_DIR}/campaign_log.json.tmp" \
  && mv "${CAMPAIGN_DIR}/campaign_log.json.tmp" "${CAMPAIGN_DIR}/campaign_log.json"
}
```

**Step 4.2 — Evidence Attachment**

```bash
# Screenshot
attach_screenshot() {
  local finding_id="$1"
  local screenshot_path="$2"
  local description="$3"
  
  cp "$screenshot_path" "${CAMPAIGN_DIR}/screenshots/"
  jq --arg sp "$screenshot_path" \
     --arg desc "$description" \
     '.evidence.screenshots += [{
       "path": $sp,
       "description": $desc,
       "captured": (now | strftime("%Y-%m-%dT%H:%M:%SZ"))
     }]' \
     "${CAMPAIGN_DIR}/findings/${finding_id}.json"
}
```

---

### Phase 5 — Weekly Report to Telegram

**Step 5.1 — Generate Report**

```bash
generate_weekly_report() {
  local target="$1"
  CAMPAIGN_DIR="/root/.nanobot/workspace/openclaw-brain-v2/knowledge/gateway_profiles/${target}"
  
  STATS=$(jq '.statistics' "${CAMPAIGN_DIR}/campaign_log.json")
  PHASE=$(jq -r '.current_phase' "${CAMPAIGN_DIR}/campaign_log.json")
  SESSIONS=$(jq '.sessions | length' "${CAMPAIGN_DIR}/campaign_log.json")
  P1=$(jq -r '.statistics.p1_findings' <<< "$STATS")
  P2=$(jq -r '.statistics.p2_findings' <<< "$STATS")
  P3=$(jq -r '.statistics.p3_findings' <<< "$STATS")
  HOURS=$(jq -r '.statistics.hours_invested' <<< "$STATS")
  
  cat << EOF
📊 WEEKLY CAMPAIGN REPORT — ${target}

🎯 Current Phase: ${PHASE}
📅 Report Date: $(date '+%Y-%m-%d')

📈 Campaign Statistics:
   • Total Sessions: ${SESSIONS}
   • Hours Invested: ${HOURS}
   • Total Findings: $(jq -r '.statistics.total_findings' <<< "$STATS")

🔴 Severity Breakdown:
   • P1 (Critical): ${P1}
   • P2 (High):     ${P2}
   • P3 (Medium):   ${P3}

🔄 Phase History:
$(jq -r '.phase_history[] | "   • \(.phase) → started: \(.started)"' "${CAMPAIGN_DIR}/campaign_log.json")

⚠️ Escalation Flags:
$(jq -r '.escalation_flags | to_entries | .[] | "   • \(.key): \(.value)"' "${CAMPAIGN_DIR}/campaign_log.json")

📋 Recent Findings (last 7 days):
$(jq -r '.findings[] | select(.discovered_date > "'$(date -d '7 days ago' -I)'") | "   • [\(._severity)] \(.title)"' "${CAMPAIGN_DIR}/campaign_log.json" 2>/dev/null || echo "   • No new findings this week")

📌 Next Steps:
   • Continue ${PHASE} phase
   • Review P1 findings for immediate remediation
EOF
}
```

**Step 5.2 — Send to Telegram**

```bash
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHANNEL_ID}" \
  -d text="$(generate_weekly_report "${target}")" \
  -d parse_mode="Markdown"
```

---

### Phase 6 — Escalation Triggers

**Step 6.1 — Detection Scripts**

```bash
check_escalation_triggers() {
  local target="$1"
  CAMPAIGN_DIR="/root/.nanobot/workspace/openclaw-brain-v2/knowledge/gateway_profiles/${target}"
  
  LAST_ACTIVITY=$(jq -r '.last_activity' "${CAMPAIGN_DIR}/campaign_log.json")
  DAYS_SINCE=$((${DAYS_SINCE_LAST_ACTIVITY}))
  
  # Target goes dark (>7 days no activity)
  if [ "$DAYS_SINCE" -gt 7 ]; then
    jq '.escalation_flags.target_dark = true' "${CAMPAIGN_DIR}/campaign_log.json" \
    > "${CAMPAIGN_DIR}/campaign_log.json.tmp" \
    && mv "${CAMPAIGN_DIR}/campaign_log.json.tmp" "${CAMPAIGN_DIR}/campaign_log.json"
    
    send_telegram_alert "🟠 ESCALATION: Campaign ${target} has been inactive for ${DAYS_SINCE} days. Target may have gone dark or detected the engagement."
  fi
  
  # Finding rate drop (>3 sessions with <1 new finding)
  RECENT_FINDINGS=$(jq '[.sessions[-3:][] | .findings_this_session] | add' "${CAMPAIGN_DIR}/campaign_log.json")
  if [ "$RECENT_FINDINGS" -eq 0 ]; then
    jq '.escalation_flags.finding_rate_drop = true' "${CAMPAIGN_DIR}/campaign_log.json" \
    > "${CAMPAIGN_DIR}/campaign_log.json.tmp" \
    && mv "${CAMPAIGN_DIR}/campaign_log.json.tmp" "${CAMPAIGN_DIR}/campaign_log.json"
    
    send_telegram_alert "🟡 ESCALATION: Campaign ${target} finding rate has dropped significantly. Consider phase pivot or target re-evaluation."
  fi
  
  # Countermeasure detected (logged by other skills)
  # Other skills call: jq '.escalation_flags.countermeasure_detected = true'
}
```

---

### Phase 7 — Campaign Archive

**Step 7.1 — Archive Procedure**

```bash
archive_campaign() {
  local target="$1"
  local archive_reason="$2"
  
  CAMPAIGN_DIR="/root/.nanobot/workspace/openclaw-brain-v2/knowledge/gateway_profiles/${target}"
  ARCHIVE_DIR="/root/.nanobot/workspace/openclaw-brain-v2/knowledge/targets/archived/${target}"
  
  # Finalize campaign log
  jq --arg arch_reason "$archive_reason" \
     --arg arch_date "$(date -Iseconds)" \
     '.status = "archived" | .archived = true | .archived_date = $arch_date | .archive_reason = $arch_reason' \
     "${CAMPAIGN_DIR}/campaign_log.json" \
  > "${CAMPAIGN_DIR}/campaign_log.json.tmp" \
  && mv "${CAMPAIGN_DIR}/campaign_log.json.tmp" "${CAMPAIGN_DIR}/campaign_log.json"
  
  # Move to archive
  mkdir -p "$(dirname "$ARCHIVE_DIR")"
  mv "${CAMPAIGN_DIR}" "${ARCHIVE_DIR}"
  
  # Update CAMPAIGN_TRACKER
  sed -i "s/| 🟢 Active |/| 🔵 Archived |/" \
     /root/.nanobot/workspace/openclaw-brain-v2/memory/CAMPAIGN_TRACKER.md
  
  echo "✅ Campaign ${target} archived to ${ARCHIVE_DIR}"
}
```

---

## Campaign Statistics

| Metric | Description |
|---|---|
| `total_sessions` | Number of engagement sessions |
| `total_findings` | Total findings across all severities |
| `p1_findings` | Critical findings requiring immediate action |
| `p2_findings` | High-severity findings |
| `p3_findings` | Medium-severity findings |
| `hours_invested` | Total time spent on campaign |
| `findings_this_week` | Rate indicator for escalation detection |
| `current_phase` | Active campaign phase |

---

## Cross-References

- **CAMPAIGN_TRACKER.md** — Master list of all campaigns and current status
- **memory/entities/** — Target entity data that feeds into campaign initialization
- **cve-tracker skill** — CVE findings feed into campaign finding logs
- **threat-intel skill** — Breach intel updates affect campaign phase decisions
- **knowledge/gateway_profiles/<target>/campaign_log.json** — Per-target campaign data
- **knowledge/gateway_profiles/<target>/findings/** — All finding evidence
- **knowledge/targets/archived/** — Archived campaign data

---

## Example Session

**Query:** `"start new campaign for target-beta"`

**Output:**
```
[+] Initializing new campaign: target-beta
[+] Creating campaign directory structure...
[+] Directory: knowledge/gateway_profiles/target-beta/
    ├── sessions/
    ├── findings/
    ├── reports/
    ├── screenshots/
    ├── logs/
    ├── poc/
    ├── iocextract/
    └── archived/
[+] Initializing campaign_log.json...
[+] Campaign ID: camp_20260509_071530
[+] Phase: recon
[+] Status: 🟢 Active
[+] Updating memory/CAMPAIGN_TRACKER.md...
[✓] Campaign target-beta initialized successfully.
```

**Query:** `"how is campaign target-beta going?"`

**Output:**
```
📊 Campaign Status: target-beta

🎯 Current Phase: deep
📅 Last Activity: 2026-05-08T14:30:00Z
⏱️ Time Since Last Session: 16 hours

📈 Statistics:
   Total Sessions:  7
   Hours Invested: 23.5
   Total Findings: 12

🔴 Severity:
   P1: 2   P2: 5   P3: 4   P4: 1

🔄 Phase History:
   recon  → surface → deep  → [current]

⚠️ Escalation Flags:
   • target_dark:            false
   • finding_rate_drop:       false
   • countermeasure_detected: false

📋 Open P1 Findings:
   • [P1-F001] SQL Injection in payment processor endpoint
   • [P1-F002] Insecure API key in client-side JS

📌 Next Steps:
   • Verify SQLi PoC with evidence capture
   • Document API key exposure scope
   • Prepare for exploit phase with client approval
```
