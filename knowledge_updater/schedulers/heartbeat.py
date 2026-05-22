#!/usr/bin/env python3
"""
heartbeat.py — Knowledge Updater Health Monitor
Runs every 5 minutes, checks scraper health, sends Telegram status

Usage: crontab: */5 * * * * python3 heartbeat.py
"""

import os
import json
from datetime import datetime, timedelta

KBASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = f"{KBASE}/knowledge_updater/state.json"
LOG = f"{KBASE}/knowledge/bot_activity_logs/LOG.md"
ALERT_FILE = f"{KBASE}/knowledge_updater/alert_queue.json"

def log(msg):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    line = f"[{ts}] [updater_heartbeat] {msg}"
    print(line)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def send_telegram(msg):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token:
        return
    try:
        import urllib.request, json as j
        data = j.dumps({'chat_id': chat_id, 'text': msg}).encode()
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data=data, headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log(f"Telegram error: {e}")

def check_health():
    state = {'running': {}, 'last_run': {}, 'failures': {}}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
        except:
            pass
    
    issues = []
    
    for spider in ['cve_spider', 'cert_spider', 'changelog_spider', 'darkweb_spider']:
        failures = state.get('failures', {}).get(spider, 0)
        last_run = state.get('last_run', {}).get(spider)
        
        if failures >= 3:
            issues.append(f"❌ {spider}: {failures} consecutive failures")
        
        if last_run:
            last_dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
            hours_ago = (datetime.utcnow() - last_dt).total_seconds() / 3600
            
            if spider == 'cve_spider' and hours_ago > 5:
                issues.append(f"⚠️ {spider}: {hours_ago:.1f}h since last run")
            elif spider == 'cert_spider' and hours_ago > 1:
                issues.append(f"⚠️ {spider}: {hours_ago:.1f}h since last run")
        else:
            issues.append(f"⚠️ {spider}: never run")
    
    return issues

def check_data_freshness():
    """Check if knowledge base data is stale"""
    stale = []
    
    # Check CVE tracker
    tracker = f"{KBASE}/knowledge/cve_tracker/tracker.json"
    if os.path.exists(tracker):
        try:
            with open(tracker) as f:
                data = json.load(f)
            last_updated = data.get('last_updated')
            if last_updated:
                dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                hours = (datetime.utcnow() - dt).total_seconds() / 3600
                if hours > 6:
                    stale.append(f"⚠️ CVE tracker: {hours:.1f}h old")
        except:
            stale.append("❌ CVE tracker: corrupted or missing")
    
    # Check active targets
    targets = f"{KBASE}/knowledge/targets/active_targets.json"
    if os.path.exists(targets):
        try:
            with open(targets) as f:
                data = json.load(f)
            last_updated = data.get('last_updated')
            if last_updated:
                dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                hours = (datetime.utcnow() - dt).total_seconds() / 3600
                if hours > 24:
                    stale.append(f"⚠️ Active targets: {hours:.1f}h old")
        except:
            pass
    
    return stale

def main():
    log("=== Updater Heartbeat ===")
    
    health_issues = check_health()
    stale_data = check_data_freshness()
    
    if health_issues or stale_data:
        msg = "🔔 Knowledge Updater Status\n\n"
        
        if health_issues:
            msg += "Health Issues:\n" + '\n'.join(health_issues) + "\n\n"
        if stale_data:
            msg += "Stale Data:\n" + '\n'.join(stale_data) + "\n\n"
        
        send_telegram(msg)
        log("Alert sent")
    else:
        log("All systems healthy")
    
    # Count items in updater fresh queue
    fresh_dir = f"{KBASE}/knowledge/updater_fresh"
    if os.path.exists(fresh_dir):
        count = sum(1 for _ in os.listdir(fresh_dir) if _.endswith('.json'))
        log(f"Fresh data files pending: {count}")

if __name__ == '__main__':
    main()