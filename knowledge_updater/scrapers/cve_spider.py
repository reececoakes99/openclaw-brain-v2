#!/usr/bin/env python3
"""
cve_spider.py — NVD/CISA CVE Feed Scraper
Fetches CVEs from NVD API and CISA KEV catalog
Updates: knowledge/cve_tracker/tracker.json
Run via: cron every 4 hours
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import ssl

# Paths — resolve against OPENCLAW_WORKSPACE env var with fallback to repo root
_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KBASE = os.getenv('OPENCLAW_WORKSPACE', os.path.join(_SCRIPT_DIR, '..'))
TRACKER = os.path.join(KBASE, 'knowledge', 'cve_tracker', 'tracker.json')
QUEUE = os.path.join(KBASE, 'knowledge', 'bot_queue', 'recon_pending.json')
LOG = os.path.join(KBASE, 'knowledge', 'bot_activity_logs', 'LOG.md')
FRESHPATH = os.path.join(KBASE, 'knowledge', 'updater_fresh', 'cves')

# Ensure fresh data dir
os.makedirs(FRESHPATH, exist_ok=True)

def log(msg):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    line = f"[{ts}] [cve_spider] {msg}"
    print(line)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def fetch_nvd_cves():
    """
    Fetch recent CVEs from NVD 2.0 API.
    Focus on payment-related keywords: payment, gateway, POS, ISO8583, HSM, PCI
    """
    ctx = ssl.create_default_context()
    nvd_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    keywords = ['payment', 'gateway', 'POS', 'acquirer', 'card', 'PCI', 'ISO8583', 'HSM', 'webhook', 'token']
    new_cves = []
    
    # Fetch last 48 hours of CVEs
    now = datetime.utcnow()
    start = (now - timedelta(hours=48)).isoformat() + '+00:00'
    
    params = f"?pubStartDate={start}&resultsPerPage=100"
    
    for keyword in keywords:
        try:
            url = f"{nvd_url}{params}&keyword={keyword}"
            req = urllib.request.Request(url, headers={'User-Agent': 'OpenClaw-KnowledgeUpdater/1.0'})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                data = json.loads(r.read())
            
            for item in data.get('vulnerabilities', []):
                cve = item['cve']
                cve_id = cve.get('id', 'N/A')
                desc = cve['descriptions'][0]['value'] if cve.get('descriptions') else ''
                
                cvss_v3 = None
                severity = 'LOW'
                for ref in cve.get('metrics', {}).get('cvssMetricV31', []):
                    cvss_v3 = ref['cvssData']
                    severity = cvss_v3.get('baseSeverity', 'LOW')
                    break
                
                cpe_list = []
                for config in cve.get('configurations', []):
                    for node in config.get('nodes', []):
                        for cpe in node.get('cpeMatch', []):
                            cpe_list.append(cpe.get('criteria', ''))
                
                cve_entry = {
                    'cve_id': cve_id,
                    'description': desc[:500],
                    'severity': severity,
                    'cvss_score': cvss_v3.get('baseScore') if cvss_v3 else None,
                    'published': cve.get('published', ''),
                    'last_modified': cve.get('lastModified', ''),
                    'cpes': cpe_list[:10],
                    'references': [r['url'] for r in cve.get('references', [])[:5]],
                    'keyword_match': keyword,
                    'scraped_at': datetime.utcnow().isoformat(),
                    'exploit_available': False,
                    'linked_targets': [],
                    'mitigation': ''
                }
                
                # Check ExploitDB for PoC
                # (simplified — real implementation would check ExploitDB API)
                
                new_cves.append(cve_entry)
                log(f"  Found: {cve_id} (severity={severity}, score={cve_entry['cvss_score']})")
                
        except Exception as e:
            log(f"  Error fetching {keyword}: {e}")
    
    return new_cves

def fetch_cisa_kev():
    """
    Fetch CISA Known Exploited Vulnerabilities catalog
    High priority — these are actively exploited
    """
    ctx = ssl.create_default_context()
    kev_url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    
    try:
        req = urllib.request.Request(kev_url, headers={'User-Agent': 'OpenClaw-KnowledgeUpdater/1.0'})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            data = json.loads(r.read())
        
        kev_cves = []
        for vuln in data.get('vulnerabilities', []):
            cve_id = vuln.get('cveID', '')
            if any(k in vuln.get('shortDescription', '').lower() for k in 
                   ['payment', 'web', 'api', 'server', 'gateway', 'card', 'transaction']):
                kev_cves.append({
                    'cve_id': cve_id,
                    'vendor_project': vuln.get('vendorProject', ''),
                    'product': vuln.get('product', ''),
                    'description': vuln.get('shortDescription', ''),
                    'date_added': vuln.get('dateAdded', ''),
                    'due_date': vuln.get('dueDate', ''),
                    'action_required': vuln.get('requiredAction', ''),
                    'known_ransomware_campaign_use': vuln.get('knownRansomwareCampaignUse', ''),
                    'source': 'CISA_KEV',
                    'priority': 'P1',  # Actively exploited = highest priority
                    'scraped_at': datetime.utcnow().isoformat()
                })
                log(f"  KEV: {cve_id} — {vuln.get('shortDescription', '')[:80]}")
        
        return kev_cves
        
    except Exception as e:
        log(f"CISA KEV fetch error: {e}")
        return []

def merge_cves(nvd_cves, kev_cves):
    """
    Merge new CVEs into existing tracker, dedup by CVE ID
    """
    tracker = {'cves': [], 'last_updated': None}
    
    if os.path.exists(TRACKER):
        try:
            with open(TRACKER) as f:
                tracker = json.load(f)
        except:
            tracker = {'cves': [], 'last_updated': None}
    
    existing_ids = {c['cve_id'] for c in tracker.get('cves', [])}
    
    merged = 0
    for cve in nvd_cves + kev_cves:
        if cve['cve_id'] not in existing_ids:
            tracker['cves'].insert(0, cve)  # Newest first
            merged += 1
            
            # Flag P1 to HUNTER queue
            if cve.get('priority') == 'P1' or (cve.get('cvss_score', 0) >= 9.0):
                queue_recon(cve)
    
    tracker['last_updated'] = datetime.utcnow().isoformat()
    tracker['total_count'] = len(tracker['cves'])
    
    return tracker, merged

def queue_recon(cve):
    """Push P1 CVE to INTEL queue for scoring"""
    queue = {'pending': [], 'last_updated': None}
    
    if os.path.exists(QUEUE):
        try:
            with open(QUEUE) as f:
                queue = json.load(f)
        except:
            queue = {'pending': [], 'last_updated': None}
    
    # Add to recon queue if not already present
    existing = {item.get('cve_id') for item in queue.get('pending', [])}
    if cve['cve_id'] not in existing:
        queue['pending'].append({
            'type': 'cve_alert',
            'cve_id': cve['cve_id'],
            'severity': cve.get('severity'),
            'cvss': cve.get('cvss_score'),
            'enqueued_at': datetime.utcnow().isoformat(),
            'action': 'score_and_hunter'
        })
        log(f"  → Queued to INTEL: {cve['cve_id']}")
    
    queue['last_updated'] = datetime.utcnow().isoformat()
    with open(QUEUE, 'w') as f:
        json.dump(queue, f, indent=2)

def main():
    log("=== Starting CVE Spider ===")
    
    # Fetch from NVD
    log("Fetching NVD CVEs (last 48h, payment keywords)...")
    nvd_cves = fetch_nvd_cves()
    log(f"NVD: {len(nvd_cves)} CVEs found")
    
    # Fetch from CISA KEV
    log("Fetching CISA KEV catalog...")
    kev_cves = fetch_cisa_kev()
    log(f"CISA KEV: {len(kev_cves)} relevant CVEs")
    
    # Merge and save
    tracker, merged = merge_cves(nvd_cves, kev_cves)
    
    with open(TRACKER, 'w') as f:
        json.dump(tracker, f, indent=2)
    
    # Also save fresh copy
    fresh_file = f"{FRESHPATH}/{datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')}.json"
    with open(fresh_file, 'w') as f:
        json.dump({'nvd': nvd_cves, 'kev': kev_cves, 'merged': merged}, f, indent=2)
    
    log(f"=== CVE Spider Complete ===")
    log(f"Total in tracker: {tracker['total_count']}")
    log(f"New CVEs merged: {merged}")
    log(f"Fresh dump: {fresh_file}")

if __name__ == '__main__':
    main()