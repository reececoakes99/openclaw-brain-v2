#!/usr/bin/env python3
"""
processor.py — Main data ingestion pipeline
Deduplicates, normalizes, enriches, and merges scraped data into the knowledge base

Usage:
  python3 processor.py --run              # Run full pipeline
  python3 processor.py --source cve       # Process specific source
  python3 processor.py --dry-run          # Show what would change
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

KBASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRESH = f"{KBASE}/knowledge/updater_fresh"
LOG = f"{KBASE}/knowledge/bot_activity_logs/LOG.md"

def log(msg):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    line = f"[{ts}] [processor] {msg}"
    print(line)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def sha256_content(item):
    """Generate content hash for deduplication"""
    content_str = json.dumps(item, sort_keys=True)
    return hashlib.sha256(content_str.encode()).hexdigest()

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return None

def dedup_existing(existing_items, new_items, key_field):
    """Remove items already in knowledge base"""
    existing_ids = {item.get(key_field) for item in existing_items if key_field in item}
    return [item for item in new_items if item.get(key_field) not in existing_ids]

def enrich_cves(cves):
    """Enrich CVE entries with derived data"""
    for cve in cves:
        # Add priority based on severity + CVSS
        score = cve.get('cvss_score', 0) or 0
        severity = cve.get('severity', 'LOW')

        if score >= 9.0 or cve.get('priority') == 'P1':
            cve['derived_priority'] = 'P1'
            cve['action_required'] = True
        elif score >= 7.0:
            cve['derived_priority'] = 'P2'
            cve['action_required'] = False
        else:
            cve['derived_priority'] = 'P3'
            cve['action_required'] = False

        # Add source attribution
        cve['enriched_at'] = datetime.utcnow().isoformat()

    return cves

def enrich_targets(targets):
    """Enrich target entries with scoring"""
    for target in targets:
        # Calculate surface risk score
        exposed_endpoints = len(target.get('endpoints', []))
        tech_count = len(target.get('technologies', []))
        ssl_issues = target.get('ssl_issues', 0)

        risk_score = min(10, (exposed_endpoints * 0.3) + (tech_count * 0.5) + (ssl_issues * 1.0))
        target['risk_score'] = round(risk_score, 1)

        if risk_score >= 7:
            target['priority'] = 'P1'
        elif risk_score >= 4:
            target['priority'] = 'P2'
        else:
            target['priority'] = 'P3'

        target['enriched_at'] = datetime.utcnow().isoformat()

    return targets

def merge_cve_tracker(new_cves):
    """Merge new CVEs into main tracker"""
    tracker_path = f"{KBASE}/knowledge/cve_tracker/tracker.json"
    tracker = load_json(tracker_path) or {'cves': [], 'last_updated': None}

    existing = tracker.get('cves', [])
    deduped = dedup_existing(existing, new_cves, 'cve_id')

    # Sort by priority then score
    priority_order = {'P1': 0, 'P2': 1, 'P3': 2}
    deduped.sort(key=lambda x: (
        priority_order.get(x.get('derived_priority', 'P3'), 3),
        -(x.get('cvss_score', 0) or 0)
    ))

    tracker['cves'] = deduped + existing
    tracker['last_updated'] = datetime.utcnow().isoformat()
    tracker['total_count'] = len(tracker['cves'])
    tracker['new_in_run'] = len(deduped)

    with open(tracker_path, 'w') as f:
        json.dump(tracker, f, indent=2)

    return len(deduped)

def merge_targets(new_targets):
    """Merge new targets into active targets"""
    targets_path = f"{KBASE}/knowledge/targets/active_targets.json"
    targets = load_json(targets_path) or {'targets': [], 'last_updated': None}

    existing = targets.get('targets', [])
    deduped = dedup_existing(existing, new_targets, 'domain')

    targets['targets'] = deduped + existing
    targets['last_updated'] = datetime.utcnow().isoformat()
    targets['total_count'] = len(targets['targets'])
    targets['new_in_run'] = len(deduped)

    with open(targets_path, 'w') as f:
        json.dump(targets, f, indent=2)

    return len(deduped)

def run_pipeline(dry_run=False):
    """Run the full ingestion pipeline"""
    log("=== Starting Processor Pipeline ===")

    results = {'cves': 0, 'targets': 0, 'breaches': 0, 'errors': []}

    # Process fresh data
    if not os.path.exists(FRESH):
        log("No fresh data to process")
        return results

    for item_dir in os.listdir(FRESH):
        item_path = os.path.join(FRESH, item_dir)
        if not os.path.isdir(item_path):
            continue

        for fname in os.listdir(item_path):
            if not fname.endswith('.json'):
                continue

            fpath = os.path.join(item_path, fname)
            log(f"Processing: {fname}")

            try:
                with open(fpath) as f:
                    data = json.load(f)

                # Route by type
                if 'cves' in data or 'nvd' in data:
                    cves = data.get('cves', []) + data.get('nvd', []) + data.get('kev', [])
                    enriched = enrich_cves(cves)
                    if not dry_run:
                        merged = merge_cve_tracker(enriched)
                        results['cves'] += merged
                        log(f"  → Merged {merged} new CVEs")
                    else:
                        results['cves'] += len(enriched)

                elif 'targets' in data or 'domains' in data:
                    targets = data.get('targets', []) + data.get('domains', [])
                    enriched = enrich_targets(targets)
                    if not dry_run:
                        merged = merge_targets(enriched)
                        results['targets'] += merged
                        log(f"  → Merged {merged} new targets")
                    else:
                        results['targets'] += len(enriched)

                elif 'breaches' in data:
                    # Process breach data
                    results['breaches'] += len(data['breaches'])
                    log(f"  → {len(data['breaches'])} breach entries")

            except Exception as e:
                results['errors'].append(f"{fname}: {e}")
                log(f"  ❌ Error processing {fname}: {e}")

    log(f"=== Pipeline Complete ===")
    log(f"New CVEs: {results['cves']}")
    log(f"New targets: {results['targets']}")
    log(f"Breach entries: {results['breaches']}")
    if results['errors']:
        log(f"Errors: {len(results['errors'])}")

    return results

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true', help='Run full pipeline')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes')
    parser.add_argument('--source', type=str, help='Process specific source')
    args = parser.parse_args()

    if args.dry_run or args.run or args.source:
        run_pipeline(dry_run=args.dry_run)
    else:
        print("Usage: processor.py --run | --dry-run | --source <name>")
