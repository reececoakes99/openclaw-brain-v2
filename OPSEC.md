# OPSEC.md — Operational Security Protocol

---

## Core Principle

OPSEC is non-negotiable. Every action leaves traces. Every trace can expose Reece, the agent, or future operations. Control the narrative at all times.

---

## Data Sanitization Before Git Push

**Run sanitization on every file before committing to git.**

Checklist for every memory file, bot log, and knowledge base entry:

- [ ] IP addresses — redact to `/24` or replace with `[REDACTED-IP]`
- [ ] Domain names — replace with `[TARGET]` or `[REDACTED-DOMAIN]`
- [ ] Email addresses — replace with `[REDACTED-EMAIL]`
- [ ] API tokens/keys — replace with `[REDACTED-KEY]`
- [ ] Phone numbers — replace with `[REDACTED-PHONE]`
- [ ] Physical addresses — replace with `[REDACTED]`
- [ ] Names of non-public individuals — replace with `[REDACTED-NAME]`
- [ ] PII in screenshots — blur/remove before upload

**Command for automated sanitization:**
```bash
python3 ~/.openclaw/workspace/scripts/sanitize.py --input <file> --output <file>
```

---

## Git History Protection

**Never push the following to git:**
- Raw recon data with IP addresses
- Screenshot files containing PII
- Engagement package with internal IPs
- Bot logs with targeting information
- Credentials of any kind

**If accidental push occurs:**
1. Immediately `git log` to find the commit
2. `git revert <commit>` or use `git filter-branch` for multi-commit cleanup
3. Force push with `git push --force`
4. Report to Operator via Telegram with details

---

## Network Interaction Hygiene

During active reconnaissance or exploitation:

- Rotate User-Agent strings (use `neopay/scripts/useragent_rotator.py`)
- Minimum 2-second delay between rapid requests
- Use residential proxy rotation for high-volume scanning
- Never fire directly from KiloClaw VPS IP — route through proxies for active tests
- Rotate source IP using Tailscale exit nodes when available

---

## Anti-Fingerprinting

Web interactions:
- Disable JavaScript fingerprinting where possible
- Rotate screen resolution and window size signals
- Use randomized timing between interactions
- Match browser profile to common configurations

Protocol interactions:
- Use standardized TLS fingerprinting (JA3) matching Chrome/Firefox defaults
- Avoid sending uncommon header combinations
- Match cipher suite ordering to popular browsers

---

## Clean Exit Procedures

When ending any engagement or session:

1. **Preserve evidence first** — screenshots, logs, PCAP files to evidence directory
2. **Remove artifacts** — temporary files, payload staging files, cron remnants
3. **Close connections** — terminate any persistent connections to target
4. **Sanitize final commit** — run full sanitization check before git push
5. **Notify Operator** — session end report with finding summary

---

## What NOT To Destroy

During cleanup, preserve:
- Timestamped evidence logs
- Engagement package files (knowledge/gateway_profiles/)
- Bot activity logs (for pattern analysis)
- TTP documentation (memory/procedures/)
- CVE tracker entries

---

## Leak Detection Triggers

Monitor for potential data exposure:
- Unauthorized git push detected
- Telegram message failed to send repeatedly
- API key rotation detected in environment
- Unusual login activity on GitHub

**On any leak trigger:** Immediately notify Operator via Telegram with:
- What was potentially exposed
- What systems are affected
- Immediate containment steps taken
- Recommended follow-up actions

---

## Evidence Chain Maintenance

Every piece of data collected during engagement must maintain:
- **Timestamp** — exact time of collection (UTC)
- **Source** — where it came from (URL, tool, protocol)
- **Chain of custody** — who accessed it, when, why
- **Integrity** — hash of original (SHA256) for verification

Store evidence in `knowledge/gateway_profiles/<target>/evidence/` with:
```
YYYY-MM-DD_HHMMSS_<type>_<description>.{txt,png,pcap}
evidence_manifest.json — index of all evidence files
```