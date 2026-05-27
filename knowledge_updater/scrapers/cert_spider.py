#!/usr/bin/env python3
"""
cert_spider.py — Certificate Transparency Log Scraper
======================================================
Discovers new payment-gateway domains within minutes of certificate issuance
by querying crt.sh (Certificate Transparency logs) and filtering for
payment-related keywords.

Outputs:
  knowledge/targets/active_targets.json   — master target registry
  knowledge/updater_fresh/domains/YYYY-MM-DD.json  — new domains from this run
  knowledge/updater_fresh/LOG.md          — structured activity log
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

# ── Paths — resolve against OPENCLAW_WORKSPACE env var ────────────────────────
import os as _os
_WORKSPACE = _os.getenv("OPENCLAW_WORKSPACE", str(Path(__file__).parent.parent.parent))
BASE_DIR   = Path(_WORKSPACE)
KNOWLEDGE  = BASE_DIR / "knowledge"
TARGETS_FILE    = KNOWLEDGE / "targets" / "active_targets.json"
FRESH_DIR       = KNOWLEDGE / "updater_fresh" / "domains"
LOG_FILE        = KNOWLEDGE / "updater_fresh" / "LOG.md"
INTEL_QUEUE_FILE = BASE_DIR / "knowledge" / "bot_activity_logs" / "intel_queue.json"

# ── Payment keyword filter ───────────────────────────────────────────────────
PAYMENT_KEYWORDS = {
    "payment", "gateway", "checkout", "pay", "card", "acquirer",
    "merchant", "pos", "terminal", " acquiring ", "e-commerce",
    "invoice", "billing", "refund", " txn ", "transaction",
    " authorize", "capture", "charge", "stripe", "braintree",
    "adyen", "square", "paypal", "worldpay", "fiserv", "globalpayments",
    "checkout.com",
}
PAYMENT_RE = re.compile(
    r"|".join(re.escape(k) for k in PAYMENT_KEYWORDS), re.IGNORECASE
)

# ── HMM score for subdomains (higher = more likely a real service endpoint) ──
SUBDOMAIN_BONUS = {
    "api": 3, "checkout": 3, "pay": 3, "gateway": 3, "secure": 3,
    "ws": 2, "soap": 2, "rest": 2, "graphql": 2,
    "sandbox": 1, "test": 1, "demo": 1,
    "staging": -1, "dev": -1, "old": -1,
}

# ── HTTP config ──────────────────────────────────────────────────────────────
CRTSH_BASE   = "https://crt.sh"
CRTSH_SEARCH = CRTSH_BASE + "/?q=%25{keyword}&output=json"
UA_HEADER    = "Mozilla/5.0 (compatible; OpenClaw-CertSpider/1.0)"
REQ_TIMEOUT  = 30
RATE_LIMIT   = 2.0          # seconds between requests
MAX_PAGES    = 5            # safety cap
SAVE_CHUNK   = 50           # flush every N domains

# ── Logging ──────────────────────────────────────────────────────────────────
log = logging.getLogger("cert_spider")
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
log.addHandler(_sh)
log.setLevel(logging.INFO)


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S UTC")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_json(path: Path, default: Any = None) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not read %s: %s", path, exc)
    return default if default is not None else {}


def _save_json(path: Path, data: Any, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=indent, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)


def _sha256(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _mklog_entry(level: str, msg: str, **fields: Any) -> dict:
    return {"ts": _ts(), "level": level.upper(), "msg": msg, **fields}


def _append_log(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # simple TSV-like markdown lines
    line = f"| `{entry['ts']}` | `{entry['level']}` | {entry['msg']}"
    if entry.get("domain"):
        line += f" — domain=`{entry['domain']}`"
    if entry.get("count"):
        line += f" (count={entry['count']})"
    line += " |"
    path.write_text(path.read_text(encoding="utf-8") + line + "\n"
                    if path.exists() else
                    "| Timestamp | Level | Message |\n|-----------|-------|--------|\n" + line + "\n",
                    encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
#  Target scoring
# ══════════════════════════════════════════════════════════════════════════════

def score_domain(domain: str) -> int:
    """Higher score → higher priority target."""
    score = 0
    lower = domain.lower()
    # keyword matches
    if PAYMENT_RE.search(lower):
        score += 5
    # subdomain bonuses
    parts = lower.split(".")
    if len(parts) > 2:
        sub = parts[0]
        score += SUBDOMAIN_BONUS.get(sub, 1)
    # TLD penalty (cheap/free TLDs less interesting)
    tld = parts[-1] if parts else ""
    if tld in {"xyz", "top", "club", "work", "click", "link"}:
        score -= 3
    return score


# ══════════════════════════════════════════════════════════════════════════════
#  crt.sh API
# ══════════════════════════════════════════════════════════════════════════════

def fetch_crtsh_page(keyword: str, page: int = 0) -> list[dict]:
    """Fetch one page of CT log results for a keyword search."""
    # crt.sh uses Identity (wildcard) search; replace dots for URL safety
    safe_kw = keyword.replace(".", "%2E")
    url = CRTSH_BASE + f"/?q=%.{safe_kw}&output=json&deduplicate=Y"
    if page > 0:
        url += f"&start={page * 100}"
    log.debug("Fetching %s", url)
    resp = requests.get(url, headers={"User-Agent": UA_HEADER},
                        timeout=REQ_TIMEOUT)
    resp.raise_for_status()
    try:
        data = resp.json()
    except json.JSONDecodeError:
        log.warning("Non-JSON response from crt.sh for %s", keyword)
        data = []
    return data


def parse_cert_entry(entry: dict, seen_shas: set[str]) -> Optional[dict]:
    """Normalize a raw crt.sh entry into our canonical domain record."""
    sha1_raw = entry.get("sha256_hash", "") or ""
    # crt.sh sometimes stores sha256 as uppercase
    sha256 = sha1_raw.lower()
    if not sha256 or sha256 in seen_shas:
        return None

    # issuer name – pick the most specific CN component
    issuer_raw = entry.get("issuer_name", "") or ""
    issuer_cn = ""
    cn_m = re.search(r"CN\s*=\s*([^,\n]+)", issuer_raw)
    if cn_m:
        issuer_cn = cn_m.group(1).strip()
    else:
        issuer_cn = issuer_raw[:60]

    # logged name – may be a wildcard; extract actual SANs from 'name_value'
    name_value = entry.get("name_value", "") or ""
    sans_raw = [ln.strip() for ln in name_value.split("\n") if ln.strip()]
    sans_clean: list[str] = []
    for san in sans_raw:
        san = san.strip()
        # skip IP addresses
        if re.match(r"\d+\.\d+\.\d+\.\d+", san):
            continue
        # skip emails
        if "@" in san:
            continue
        # strip leading *. for wildcards
        san = san.lstrip("*.")
        if san and len(san) < 253:
            sans_clean.append(san.lower())

    if not sans_clean:
        return None

    # primary domain = first SAN
    primary = sans_clean[0]

    # issue / expiry timestamps
    issue_ts_str = entry.get("not_before", "") or ""
    expiry_ts_str = entry.get("not_after", "") or ""
    try:
        issue_date = datetime.fromisoformat(issue_ts_str[:19]).isoformat()
    except Exception:
        issue_date = issue_ts_str[:19] or ""
    try:
        expiry_date = datetime.fromisoformat(expiry_ts_str[:19]).isoformat()
    except Exception:
        expiry_date = expiry_ts_str[:19] or ""

    # fingerprint / hash
    fingerprint = entry.get("issuer_ca_id", "")
    fingerprint = f"ca-{fingerprint}" if fingerprint else sha256[:16]

    record = {
        "domain":       primary,
        "sans":         sorted(set(sans_clean)),
        "issuer":       issuer_cn,
        "sha256":       sha256,
        "issue_date":   issue_date,
        "expiry_date":  expiry_date,
        "ca_id":        entry.get("issuer_ca_id"),
        "log_name":     entry.get("log_name", ""),
        "fingerprint":  fingerprint,
        "score":        score_domain(primary),
        "source":       "crt.sh",
        "seen_at":      _ts(),
    }
    return record


# ══════════════════════════════════════════════════════════════════════════════
#  Deduplication
# ══════════════════════════════════════════════════════════════════════════════

def load_existing_targets() -> tuple[dict, set[str]]:
    """Returns (targets_by_fingerprint, all_sha256_set)."""
    data = _load_json(TARGETS_FILE, default={})
    by_fp: dict[str, dict] = {}
    sha_set: set[str] = set()
    for entry in data.get("targets", []):
        fp = entry.get("fingerprint", "")
        if fp:
            by_fp[fp] = entry
        sh = entry.get("sha256", "")
        if sh:
            sha_set.add(sh)
    return by_fp, sha_set


def write_targets(new_records: list[dict]) -> int:
    """Merge new_records into active_targets.json. Returns count of added."""
    existing_by_fp, _ = load_existing_targets()
    for rec in new_records:
        existing_by_fp[rec["fingerprint"]] = rec

    targets_list = sorted(existing_by_fp.values(),
                          key=lambda x: (-x.get("score", 0), x.get("domain", "")))

    output = {
        "updated": _ts(),
        "total": len(targets_list),
        "targets": targets_list,
    }
    _save_json(TARGETS_FILE, output)
    return len(new_records)


# ══════════════════════════════════════════════════════════════════════════════
#  Intel queue
# ══════════════════════════════════════════════════════════════════════════════

def queue_intel(targets: list[dict], threshold: int = 5) -> int:
    """Push high-value new targets to the INTEL bot queue."""
    queued = [t for t in targets if t.get("score", 0) >= threshold]
    if not queued:
        return 0
    queue = _load_json(INTEL_QUEUE_FILE, default=[])
    existing_domains = {q["domain"] for q in queue}
    added = 0
    for t in queued:
        if t["domain"] not in existing_domains:
            queue.append({
                "domain":     t["domain"],
                "sans":       t.get("sans", []),
                "score":      t.get("score", 0),
                "issuer":     t.get("issuer", ""),
                "queued_at":  _ts(),
                "reason":     "high_cert_score",
            })
            existing_domains.add(t["domain"])
            added += 1
    if added:
        _save_json(INTEL_QUEUE_FILE, queue)
        log.info("Queued %d high-value targets for INTEL bot", added)
    return added


# ══════════════════════════════════════════════════════════════════════════════
#  Fresh run output
# ══════════════════════════════════════════════════════════════════════════════

def write_fresh_domains(domains: list[dict]) -> Path:
    """Save new domains discovered this run."""
    today_str = _today()
    path = FRESH_DIR / f"{today_str}.json"
    output = {
        "run_date": today_str,
        "scraped_at": _ts(),
        "count": len(domains),
        "domains": sorted(domains, key=lambda x: (-x.get("score", 0), x["domain"])),
    }
    _save_json(path, output)
    log.info("Wrote %d new domains to %s", len(domains), path)
    return path


# ══════════════════════════════════════════════════════════════════════════════
#  Main spider
# ══════════════════════════════════════════════════════════════════════════════

def run(keywords: Optional[list[str]] = None,
        max_pages: int = MAX_PAGES,
        rate_limit: float = RATE_LIMIT,
        dry_run: bool = False) -> dict:
    """
    Main entry point.

    Args:
        keywords:    list of domain suffixes/keywords to search.
                    Defaults to PAYMENT_KEYWORDS.
        max_pages:   max result pages per keyword.
        rate_limit:  seconds between requests.
        dry_run:     if True, write output to temp location and print summary.

    Returns:
        dict with keys: new_count, queued_count, fresh_path, errors
    """
    if keywords is None:
        # extract domain-ish keywords from PAYMENT_KEYWORDS
        keywords = [
            "payment", "gateway", "checkout", "pay", "card",
            "acquirer", "merchant", "pos", "billing",
        ]

    _append_log(LOG_FILE, _mklog_entry("INFO", "CertSpider run started",
                                       keywords=keywords))

    all_new: list[dict] = []
    all_sha256: set[str] = set()
    errors: list[str] = []

    for kw in keywords:
        for page in range(max_pages):
            try:
                raw_entries = fetch_crtsh_page(kw, page=page)
            except requests.RequestException as exc:
                err = f"HTTP error on kw={kw} page={page}: {exc}"
                log.error(err)
                errors.append(err)
                continue

            if not raw_entries:
                log.debug("No more results for kw=%s page=%d", kw, page)
                break

            page_new = 0
            for entry in raw_entries:
                rec = parse_cert_entry(entry, all_sha256)
                if rec is None:
                    continue
                all_sha256.add(rec["sha256"])
                all_new.append(rec)
                page_new += 1

            log.info("kw=%s page=%d → %d entries, %d new",
                     kw, page, len(raw_entries), page_new)
            _append_log(LOG_FILE, _mklog_entry("DEBUG",
                                               f"Processed page {page} for keyword={kw}",
                                               entries=len(raw_entries),
                                               new=page_new))

            if page_new == 0:
                break

            time.sleep(rate_limit)

    # ── De-duplicate against existing targets ─────────────────────────────────
    _, existing_shas = load_existing_targets()
    truly_new = [r for r in all_new if r["sha256"] not in existing_shas]
    log.info("Total scraped: %d | Already known: %d | New this run: %d",
             len(all_new), len(all_new) - len(truly_new), len(truly_new))
    _append_log(LOG_FILE, _mklog_entry("INFO",
                                       f"Scraping complete",
                                       total=len(all_new),
                                       already_known=len(all_new) - len(truly_new),
                                       new=len(truly_new)))

    # ── Sort by score ──────────────────────────────────────────────────────────
    truly_new.sort(key=lambda x: (-x.get("score", 0), x["domain"]))

    # ── Write fresh domains ────────────────────────────────────────────────────
    fresh_path = write_fresh_domains(truly_new) if truly_new else None

    # ── Write master targets ────────────────────────────────────────────────────
    added_count = 0
    if truly_new and not dry_run:
        added_count = write_targets(truly_new)
        _append_log(LOG_FILE, _mklog_entry("INFO",
                                          f"Added {added_count} domains to active_targets.json"))

    # ── Queue high-value for INTEL bot ────────────────────────────────────────
    queued_count = queue_intel(truly_new) if truly_new and not dry_run else 0

    summary = {
        "run_at":         _ts(),
        "keywords":       keywords,
        "total_scraped":  len(all_new),
        "new_count":      len(truly_new),
        "added_to_targets": added_count,
        "queued_intel":   queued_count,
        "fresh_path":     str(fresh_path) if fresh_path else "",
        "errors":         errors,
    }
    _append_log(LOG_FILE, _mklog_entry("INFO",
                                       f"CertSpider run complete — "
                                       f"new={len(truly_new)} added={added_count} queued={queued_count}",
                                       **summary))

    if dry_run:
        log.info("DRY RUN — not writing to disk. Summary: %s",
                 json.dumps(summary, indent=2))

    return summary


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Certificate Transparency log scraper for payment gateway discovery")
    parser.add_argument("-k", "--keyword", action="append", dest="keywords",
                        help="Keyword to search (can be repeated)")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    parser.add_argument("--rate-limit", type=float, default=RATE_LIMIT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = run(
        keywords=args.keywords,
        max_pages=args.max_pages,
        rate_limit=args.rate_limit,
        dry_run=args.dry_run,
    )
    sys.exit(0 if not summary["errors"] else 1)
