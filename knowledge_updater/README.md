# KNOWLEDGE AUTO-UPDATER — Data Ingestion System

## Overview

Automated pipelines that continuously scrape, parse, and ingest external data into the knowledge base. Keeps the agent's intelligence fresh without manual intervention.

```
External Sources → Scrapers → Processing → Ingestion → Knowledge Base
     (scheduled every 1-24h)    (dedup+normalize)   (auto-update)
```

## Data Sources

| Source | Type | Update Freq | Targets |
|---|---|---|---|
| NVD (CVE feeds) | JSON | 4h | Payment CVEs |
| CISA KEV | CSV | Daily | Known exploited vulns |
| Shodan API | JSON | 6h | Payment infrastructure |
| Certificate Transparency | JSON | 2h | New payment domains |
| Dark web monitoring | Custom | 12h | Breach data |
| Vendor changelogs | HTML | Daily | Version updates |
| SecLists/GitHub | Git | Daily | Wordlist updates |
| Threat feeds | JSON | 4h | IOCs |

## Architecture

```
scrapers/          — Scrapy/BS4 spider implementations
  ├── cve_spider.py       — NVD CVE feed scraper
  ├── cert_spider.py      — Certificate transparency
  ├── changelog_spider.py — Vendor changelog monitor
  └── darkweb_spider.py   — Dark web mention tracker

pipelines/         — Data processing pipelines
  ├── processor.py        — Dedup, normalize, enrich
  ├── deduplicator.py     — SHA256 dedup against existing
  └── enricher.py          — Add metadata, tags, scores

schedulers/        — Scheduling engines
  ├── prefect_flow.py     — Prefect pipeline orchestration
  ├── cron_scheduler.py   — Unix cron wrapper
  └── heartbeat.py         — Health check + alerting

config/
  ├── sources.yaml        — Source configurations
  ├── schedule.yaml       — Update frequencies
  └── ingestion.yaml      — Processing rules
```

## Scheduling Strategy

```yaml
# config/schedule.yaml
schedules:
  cve_feed:
    source: nvd
    frequency: "0 */4 * * *"  # Every 4 hours
    priority: P1
    always_on: true

  cert_transparency:
    source: crt.sh
    frequency: "*/30 * * * *"  # Every 30 minutes
    priority: P2
    always_on: true

  changelog:
    source: vendor_feeds
    frequency: "0 6 * * *"  # Daily at 06:00 UTC
    priority: P3
    always_on: true

  darkweb:
    source: tor_sites
    frequency: "0 */12 * * *"  # Every 12 hours
    priority: P1
    always_on: true
```

## Quick Start

```bash
# Install dependencies
pip install scrapy beautifulsoup4 lxml prefect schedule

# Run a single scraper
python3 -m scrapy runspider scrapers/cve_spider.py -o knowledge/cve_tracker/new_cves.json

# Run all scrapers via scheduler
python3 schedulers/cron_scheduler.py --start

# Run Prefect flow
python3 schedulers/prefect_flow.py
```

## Output

All scraped data lands in `knowledge/updater_fresh/` before merge:
- `knowledge/updater_fresh/cves/YYYY-MM-DD.json`
- `knowledge/updater_fresh/domains/YYYY-MM-DD.json`
- `knowledge/updater_fresh/breaches/YYYY-MM-DD.json`

Pipeline merges into live knowledge base files, flagging new entries for review.