#!/usr/bin/env python3
"""
capability_updater.py — OpenClaw Self-Improvement Loop
=======================================================
Reads ops_complete.json feedback and updates capability_registry.json
with confirmed working techniques, success rates, and evasion notes.

Run via: cron every 24 hours
  0 3 * * * python3 /root/.openclaw/workspace/pipeline/agent/capability_updater.py
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime

# Paths
_WORKSPACE = os.getenv('OPENCLAW_WORKSPACE', str(Path(__file__).parent.parent.parent))
WORKSPACE = Path(_WORKSPACE)
REGISTRY_PATH = Path(__file__).parent / 'capability_registry.json'
OPS_COMPLETE = WORKSPACE / 'knowledge' / 'bot_queue' / 'ops_complete.json'
EVASION_LOG = WORKSPACE / 'bot_evasion.md'
LOG_FILE = WORKSPACE / 'knowledge' / 'bot_activity_logs' / 'LOG.md'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [capability_updater] %(message)s')
log = logging.getLogger('capability_updater')


def _log(msg: str):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    line = f"[{ts}] [capability_updater] {msg}"
    log.info(msg)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


def load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def save_registry(registry: dict):
    registry['last_updated'] = datetime.utcnow().isoformat()
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(registry, f, indent=2)
    _log(f"Registry saved — {len(registry['capabilities'])} capabilities")


def load_ops_feedback() -> list:
    if not OPS_COMPLETE.exists():
        return []
    try:
        with open(OPS_COMPLETE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else data.get('completed', [])
    except Exception as e:
        _log(f"Error loading ops feedback: {e}")
        return []


def update_capability_stats(registry: dict, feedback_entries: list) -> dict:
    """
    For each ops_complete entry, update the relevant capability's stats:
    - success_rate (rolling average)
    - confirmed_vectors (add newly confirmed)
    - last_used timestamp
    - detection_events counter
    """
    for entry in feedback_entries:
        confirmed = entry.get('confirmed_vectors', [])
        failed = entry.get('failed_vectors', [])
        detections = entry.get('detection_events', [])
        timestamp = entry.get('timestamp', datetime.utcnow().isoformat())

        for cap_name, cap_data in registry['capabilities'].items():
            # Check if this capability was involved
            involved = any(
                cap_name in str(v) or cap_data.get('category', '') in str(v)
                for v in confirmed + failed
            )
            if not involved:
                continue

            # Initialize stats if not present
            if 'stats' not in cap_data:
                cap_data['stats'] = {
                    'total_uses': 0,
                    'successful_uses': 0,
                    'detection_events': 0,
                    'confirmed_vectors': [],
                    'last_used': None
                }

            stats = cap_data['stats']
            stats['total_uses'] += 1
            stats['last_used'] = timestamp

            # Count successes
            cap_successes = [v for v in confirmed if cap_name in str(v) or cap_data.get('category', '') in str(v)]
            if cap_successes:
                stats['successful_uses'] += len(cap_successes)
                for v in cap_successes:
                    if v not in stats['confirmed_vectors']:
                        stats['confirmed_vectors'].append(v)
                _log(f"  {cap_name}: +{len(cap_successes)} confirmed vectors")

            # Count detections
            cap_detections = [d for d in detections if cap_name in str(d)]
            if cap_detections:
                stats['detection_events'] += len(cap_detections)
                _log(f"  {cap_name}: +{len(cap_detections)} detection events — updating evasion log")
                _append_evasion_note(cap_name, cap_detections, timestamp)

            # Calculate success rate
            if stats['total_uses'] > 0:
                stats['success_rate'] = round(stats['successful_uses'] / stats['total_uses'], 2)

    return registry


def _append_evasion_note(capability: str, detections: list, timestamp: str):
    """Append detection event to bot_evasion.md for pattern learning."""
    note = f"\n### Auto-logged Detection — {capability} — {timestamp}\n"
    for d in detections:
        note += f"- {d}\n"
    try:
        with open(EVASION_LOG, 'a') as f:
            f.write(note)
    except Exception as e:
        _log(f"Could not write evasion log: {e}")


def archive_processed_feedback(feedback_entries: list):
    """Move processed entries to archive to avoid double-counting."""
    archive_path = OPS_COMPLETE.parent / 'ops_complete_archive.json'
    archive = []
    if archive_path.exists():
        try:
            with open(archive_path) as f:
                archive = json.load(f)
        except Exception:
            archive = []

    archive.extend(feedback_entries)
    with open(archive_path, 'w') as f:
        json.dump(archive, f, indent=2)

    # Clear the active queue
    with open(OPS_COMPLETE, 'w') as f:
        json.dump([], f, indent=2)

    _log(f"Archived {len(feedback_entries)} feedback entries")


def generate_improvement_report(registry: dict) -> str:
    """Generate a summary of capability performance for Telegram reporting."""
    lines = ["📊 *Capability Performance Report*\n"]
    for name, cap in registry['capabilities'].items():
        stats = cap.get('stats', {})
        if not stats:
            continue
        rate = stats.get('success_rate', 0)
        uses = stats.get('total_uses', 0)
        detections = stats.get('detection_events', 0)
        emoji = '✅' if rate >= 0.7 else ('⚠️' if rate >= 0.4 else '🔴')
        lines.append(f"{emoji} `{name}`: {uses} uses, {rate*100:.0f}% success, {detections} detections")
    return '\n'.join(lines)


def main():
    _log("=== Capability Updater Starting ===")

    registry = load_registry()
    feedback = load_ops_feedback()

    if not feedback:
        _log("No new ops feedback — nothing to process")
        return

    _log(f"Processing {len(feedback)} feedback entries")
    registry = update_capability_stats(registry, feedback)
    save_registry(registry)
    archive_processed_feedback(feedback)

    report = generate_improvement_report(registry)
    _log(f"Improvement report:\n{report}")

    # Write report to daily log
    daily_log = WORKSPACE / 'memory' / 'daily-logs' / f"{datetime.utcnow().strftime('%Y-%m-%d')}.md"
    daily_log.parent.mkdir(parents=True, exist_ok=True)
    with open(daily_log, 'a') as f:
        f.write(f"\n## Capability Update — {datetime.utcnow().isoformat()}\n\n{report}\n")

    _log("=== Capability Updater Complete ===")


if __name__ == '__main__':
    main()
