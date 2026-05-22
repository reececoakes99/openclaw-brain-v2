# PIPELINE_BINDING.md — Pipeline ↔ Brain Integration

How the openclaw-pipeline connects to and feeds this brain.

---

## Bot → Pipeline Stage Mapping

| Bot | Pipeline Stages | Trigger |
|---|---|---|
| **RECON** | Stage 1 (OSINT_RECON), Stage 2 (ASSET_DISCOVERY), Stage 3 (CRAWLING) | Continuous 5-min cycle or Operator `BOT RECON START` |
| **INTEL** | Stage 4 (DYNAMIC_RENDERING), Stage 5 (EXTRACTION), Stage 9 (AI_ENRICHMENT) | Every 4 hours or `BOT INTEL RUN` |
| **HUNTER** | Stage 6 (EVASION) + neopay commands (not pipeline-native) | P1-P2 target scored or `BOT HUNTER <target>` |
| **OPERATIONS** | Stage 10 (OUTPUT) + direct neopay execution + evidence packaging | Operator-triggered `BOT OPS <target>` |

---

## Pipeline Execution

### Trigger Command
```bash
python3 /root/.openclaw/workspace/pipeline/master_pipeline.py \
  --config /root/.openclaw/workspace/pipeline/engagement_config.json \
  --target <domain_or_ip>
```

### Pipeline Stages (Sequential)
| Stage | Module | Critical | Abort on Fail |
|---|---|---|---|
| 1 | `pipeline/stage1_osint.py` | Yes | Pipeline stops |
| 2 | `pipeline/stage2_asset_discovery.py` | Yes | Pipeline stops |
| 3 | `pipeline/stage3_crawling.py` | Yes | Pipeline stops |
| 4 | `pipeline/stage4_dynamic_rendering.py` | Yes | Pipeline stops |
| 5 | `pipeline/stage5_extraction.py` | Yes | Pipeline stops |
| 6 | `pipeline/stage6_evasion.py` | No | Pipeline continues |
| 7 | `pipeline/stage7_distributed.py` | No | Pipeline continues |
| 8 | `pipeline/stage8_darkweb.py` | No | Pipeline continues |
| 9 | `pipeline/stage9_ai_enrichment.py` | No | Pipeline continues |
| 10 | `pipeline/stage10_output.py` | No | Pipeline continues |

**Failure semantics:**
- Stages 1-5 failure = ABORT entire engagement, escalate to Operator
- Stages 6-10 failure = LOG, continue pipeline, flag for manual review

---

## Path Alignment — Pipeline Outputs → Brain Knowledge

| Pipeline Output Location | Brain Knowledge Location | Sync Method |
|---|---|---|
| `memory/entities/<target>/` | `knowledge/gateway_profiles/<target>/` | Direct write (same workspace) |
| `memory/entities/<target>/recon_data/` | `knowledge/gateway_profiles/<target>/surface_scan.json` | Pipeline writes here |
| `memory/daily-logs/<date>.md` | `knowledge/bot_activity_logs/` | Session end copy |
| `reports/json/<run_id>/` | `knowledge/gateway_profiles/<target>/` | Evidence chain import |
| `reports/sqlite/engagement.db` | Referenced by bot_monitor.py | SQLite direct query |
| `memory/CAMPAIGN_TRACKER.md` | `memory/CAMPAIGN_TRACKER.md` | Same file (shared workspace) |

**All paths are relative to:** `/root/.openclaw/workspace/`

---

## Engagement Config

**Location:** `/root/.openclaw/workspace/pipeline/engagement_config.json`
**Owned by:** Operator (brain references but does not modify)

The brain reads engagement_config to determine:
- `authorized_domains` → scope boundaries for all bot operations
- `pipeline_stages` → which stages are enabled for this engagement
- `rate_limiting` → request throttling parameters
- `notifications` → where to send alerts
- `evasion` → proxy rotation and timing settings

**Before any active operation, verify:**
```
1. Read engagement_config.json
2. Confirm target is in authorized_domains[]
3. If not listed → HALT, escalate to Operator
4. If listed → proceed with confidence appropriate to stage
```

---

## Knowledge Updater Integration

The `knowledge_updater/` system runs automated intelligence gathering:

| Component | Function | Schedule |
|---|---|---|
| `knowledge_updater/scrapers/cert_spider.py` | Certificate Transparency monitoring | Continuous |
| `knowledge_updater/scrapers/cve_spider.py` | CVE feed monitoring | Hourly |
| `knowledge_updater/scrapers/darkweb_spider.py` | Dark web intelligence | 6-hour cycle |
| `knowledge_updater/schedulers/cron_scheduler.py` | Orchestrates all scrapers | Master scheduler |
| `knowledge_updater/schedulers/heartbeat.py` | Health monitoring | Per HEARTBEAT.md intervals |
| `knowledge_updater/pipelines/processor.py` | Data normalization + dedup | After each scraper run |

Outputs flow directly into `knowledge/` directories.

---

## Capability Harvester

**Location:** `/root/.openclaw/workspace/pipeline/capability_harvester.py`
**Purpose:** Discovers new security tools from GitHub repos

When capability_harvester discovers new tools:
1. Stores in SQLite `capabilities.db` + JSON `.openclaw/capability_registry.json`
2. Brain's TOOLS.md should be refreshed if new patterns exceed 2-match threshold
3. New capabilities feed into bot skill expansion

**Refresh trigger:** After harvester run, check `capability_registry.json` last_updated timestamp.

---

## Pipeline ↔ Neopay Interaction

Pipeline stages that invoke neopay tools:

| Stage | Neopay Tools Used |
|---|---|
| Stage 1 (OSINT) | `fingerprinter.py` (identify payment gateways during recon) |
| Stage 5 (Extraction) | `parse_iso8583.py` (parse discovered payment traffic) |
| Stage 6 (Evasion) | Evasion timing from `bot_evasion.md` |
| Stage 9 (AI Enrichment) | All neopay tools for automated analysis |

For HUNTER bot operations (not pipeline-native):
- HUNTER loads neopay commands directly from `NEOPAY_COMMANDS.md`
- Executes scripts from `neopay/scripts/` and `protocol-engineering/scripts/`
- Results processed via `NEOPAY_FEEDBACK.md` protocol

---

## Reports & Output

Pipeline generates reports in multiple formats:
```
reports/
├── json/<run_id>/      ← Machine-readable findings
├── csv/<run_id>/       ← Tabular data export
├── html/<run_id>/      ← Visual engagement report
├── markdown/<run_id>/  ← Human-readable narrative
├── screenshots/<run_id>/  ← Visual evidence
└── sqlite/engagement.db   ← Persistent queryable database
```

Brain accesses reports for:
- Evidence chain compilation (via `EVIDENCE_CHAIN.md` protocol)
- Target scoring updates (via `bot_target_scoring.md` formula)
- Campaign tracking (via `memory/CAMPAIGN_TRACKER.md`)

---

## Telegram Notifications from Pipeline

Pipeline sends to Telegram on:
- `secrets_found` — credentials or keys discovered
- `stage_complete` — each stage completion with summary
- `errors` — any stage failure
- `p1_target` — high-priority target identified

**Chat ID:** `${OPERATOR_CHAT_ID}` (same as brain's C2 channel)
