#!/usr/bin/env python3
"""
cron_scheduler.py — Master scheduler for all knowledge scrapers
Runs on Unix cron, manages execution, health checks, and alerting

Usage:
  python3 cron_scheduler.py --start       # Start all schedulers
  python3 cron_scheduler.py --stop         # Stop all schedulers
  python3 cron_scheduler.py --status      # Show scheduler status
  python3 cron_scheduler.py --run-now    # Run all scrapers immediately
  python3 cron_scheduler.py --logs        # Show recent log entries
"""

import os
import sys
import json
import time
import signal
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Configuration
KBASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHED_LOG = f"{KBASE}/knowledge_updater/scheduler.log"
PID_FILE = f"{KBASE}/knowledge_updater/scheduler.pid"
LOG = f"{KBASE}/knowledge/bot_activity_logs/LOG.md"

# Cron schedule definitions
SCHEDULES = {
    'cve_spider': {
        'script': 'scrapers/cve_spider.py',
        'cron': '0 */4 * * *',  # Every 4 hours
        'description': 'NVD/CISA CVE feed scraper',
        'timeout': 300,
        'always_on': True
    },
    'cert_spider': {
        'script': 'scrapers/cert_spider.py',
        'cron': '*/30 * * * *',  # Every 30 minutes
        'description': 'Certificate transparency log scraper',
        'timeout': 180,
        'always_on': True
    },
    'changelog_spider': {
        'script': 'scrapers/changelog_spider.py',
        'cron': '0 6 * * *',  # Daily at 06:00 UTC
        'description': 'Vendor changelog monitor',
        'timeout': 600,
        'always_on': False
    },
    'darkweb_spider': {
        'script': 'scrapers/darkweb_spider.py',
        'cron': '0 */12 * * *',  # Every 12 hours
        'description': 'Dark web breach monitoring',
        'timeout': 900,
        'always_on': False
    }
}

def log(msg, level='INFO'):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG, 'a') as f:
        f.write(line + '\n')
    with open(SCHED_LOG, 'a') as f:
        f.write(line + '\n')

def load_state():
    """Load scheduler state"""
    state_file = f"{KBASE}/knowledge_updater/state.json"
    if os.path.exists(state_file):
        try:
            with open(state_file) as f:
                return json.load(f)
        except:
            pass
    return {'running': {}, 'last_run': {}, 'failures': {}, 'enabled': {}}

def save_state(state):
    """Save scheduler state"""
    os.makedirs(f"{KBASE}/knowledge_updater", exist_ok=True)
    with open(f"{KBASE}/knowledge_updater/state.json", 'w') as f:
        json.dump(state, f, indent=2)

def get_status(spider_name):
    """Get status of a spider"""
    state = load_state()

    last_run = state.get('last_run', {}).get(spider_name)
    failures = state.get('failures', {}).get(spider_name, 0)
    running = state.get('running', {}).get(spider_name, False)

    status = 'RUNNING' if running else 'STOPPED'
    if failures >= 3:
        status = 'FAILED'

    return {
        'name': spider_name,
        'status': status,
        'last_run': last_run,
        'failures': failures,
        'cron': SCHEDULES[spider_name]['cron'],
        'description': SCHEDULES[spider_name]['description']
    }

def run_spider(spider_name):
    """Execute a scraper with timeout and error handling"""
    state = load_state()
    cfg = SCHEDULES[spider_name]
    script_path = f"{KBASE}/knowledge_updater/{cfg['script']}"

    if not os.path.exists(script_path):
        log(f"Script not found: {script_path}", 'ERROR')
        return False

    state['running'][spider_name] = True
    save_state(state)

    log(f"Starting {spider_name}...")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            timeout=cfg['timeout'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            state['last_run'][spider_name] = datetime.utcnow().isoformat()
            state['failures'][spider_name] = 0
            log(f"{spider_name} completed successfully")
        else:
            state['failures'][spider_name] = state['failures'].get(spider_name, 0) + 1
            log(f"{spider_name} failed: {result.stderr[:200]}", 'ERROR')

            # Alert after 3 failures
            if state['failures'][spider_name] >= 3:
                log(f"ALERT: {spider_name} has failed {state['failures'][spider_name]} times", 'ERROR')
                send_alert(spider_name, result.stderr[:500])

    except subprocess.TimeoutExpired:
        state['failures'][spider_name] = state['failures'].get(spider_name, 0) + 1
        log(f"{spider_name} timed out after {cfg['timeout']}s", 'ERROR')

    except Exception as e:
        state['failures'][spider_name] = state['failures'].get(spider_name, 0) + 1
        log(f"{spider_name} error: {e}", 'ERROR')

    finally:
        state['running'][spider_name] = False
        save_state(state)

    return result.returncode == 0

def send_alert(spider_name, error):
    """Send Telegram alert on spider failure"""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')

    if not token:
        return

    msg = f"⚠️ Knowledge Updater Alert\n"
    msg += f"Spider: {spider_name}\n"
    msg += f"Error: {error[:200]}\n"
    msg += f"Time: {datetime.utcnow().isoformat()}"

    try:
        import urllib.request, json
        data = json.dumps({'chat_id': chat_id, 'text': msg}).encode()
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data=data, headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=5)
        log(f"Alert sent to Telegram")
    except Exception as e:
        log(f"Telegram alert failed: {e}")

def run_all_now():
    """Run all enabled scrapers immediately"""
    log("=== Running all scrapers (manual trigger) ===")
    results = {}
    for name in SCHEDULES:
        results[name] = run_spider(name)

    log(f"=== Run Complete ===")
    for name, success in results.items():
        status = "✅" if success else "❌"
        log(f"{status} {name}")

    return results

def show_status():
    """Display scheduler status"""
    print("\n=== Knowledge Updater Status ===")
    for name in SCHEDULES:
        s = get_status(name)
        enabled = '🔴' if SCHEDULES[name].get('always_on') else '🟡'
        status_icon = '🔄' if s['status'] == 'RUNNING' else ('❌' if s['status'] == 'FAILED' else '⏸️')

        print(f"\n{enabled} {status_icon} {name}")
        print(f"   Schedule: {s['cron']}")
        print(f"   Description: {s['description']}")
        print(f"   Status: {s['status']}")
        print(f"   Failures: {s['failures']}")
        if s['last_run']:
            print(f"   Last run: {s['last_run']}")

    print()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='OpenClaw Knowledge Updater Scheduler')
    parser.add_argument('--start', action='store_true', help='Start all schedulers')
    parser.add_argument('--stop', action='store_true', help='Stop all schedulers')
    parser.add_argument('--status', action='store_true', help='Show scheduler status')
    parser.add_argument('--run-now', action='store_true', help='Run all scrapers immediately')
    parser.add_argument('--logs', action='store_true', help='Show recent log entries')
    parser.add_argument('--spider', type=str, help='Run specific spider')

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.run_now:
        run_all_now()
    elif args.logs:
        if os.path.exists(LOG):
            with open(LOG) as f:
                lines = f.readlines()
            print(''.join(lines[-50:]))
    elif args.spider:
        if args.spider in SCHEDULES:
            run_spider(args.spider)
        else:
            print(f"Unknown spider: {args.spider}")
            print(f"Available: {list(SCHEDULES.keys())}")
    else:
        # Interactive mode — check what needs to run
        print("Knowledge Updater Scheduler")
        print("Options: --status, --run-now, --spider <name>, --logs")
        print("\nCrontab entry for this scheduler:")
        print("*/5 * * * * cd /root/.openclaw/workspace/knowledge_updater && python3 cron_scheduler.py --check")
        show_status()

if __name__ == '__main__':
    main()
