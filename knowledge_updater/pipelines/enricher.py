#!/usr/bin/env python3
"""Enrichment pipeline for CVE, MITRE ATT&CK, and threat-intel correlation."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set
from urllib.parse import quote
from urllib.request import Request, urlopen

Record = Dict[str, Any]
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
IOC_RE = re.compile(r"\b(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64}|(?:\d{1,3}\.){3}\d{1,3}|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b")
TECH_TO_CPE_HINTS = {
    "apache": ["apache:http_server"],
    "nginx": ["nginx:nginx"],
    "openssl": ["openssl:openssl"],
    "tomcat": ["apache:tomcat"],
    "struts": ["apache:struts"],
    "spring": ["vmware:spring_framework", "pivotal:spring_framework"],
    "wordpress": ["wordpress:wordpress"],
    "drupal": ["drupal:drupal"],
    "jquery": ["jquery:jquery"],
    "log4j": ["apache:log4j"],
}
MITRE_KEYWORDS = {
    "credential": ["T1110", "T1555", "T1003"],
    "phishing": ["T1566"],
    "persistence": ["T1053", "T1547"],
    "web": ["T1190", "T1059"],
    "exfiltration": ["T1041", "T1567"],
    "discovery": ["T1595", "T1590"],
    "lateral": ["T1021"],
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def fetch_json(url: str, timeout: float = 15.0) -> Any:
    request = Request(url, headers={"User-Agent": "OpenClaw-Knowledge-Enricher/1.0"})
    with urlopen(request, timeout=timeout) as response:  # nosec: runtime operator controls URL constants
        return json.loads(response.read().decode("utf-8"))


def extract_cves(record: Mapping[str, Any]) -> Set[str]:
    text = json.dumps(record, sort_keys=True, ensure_ascii=False)
    explicit = record.get("cve_id") or record.get("cve")
    cves = {match.upper() for match in CVE_RE.findall(text)}
    if isinstance(explicit, str):
        cves.update(match.upper() for match in CVE_RE.findall(explicit))
    return cves


def extract_iocs(record: Mapping[str, Any]) -> Set[str]:
    text = json.dumps(record, sort_keys=True, ensure_ascii=False)
    found = {match.lower() for match in IOC_RE.findall(text)}
    return {item for item in found if not item.startswith("cve-") and len(item) > 3}


def normalize_tech(record: Mapping[str, Any]) -> List[str]:
    values: List[str] = []
    for key in ("technology", "technologies", "tech_stack", "product", "service", "banner"):
        value = record.get(key)
        if isinstance(value, str):
            values.extend(re.split(r"[,;/|]", value))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            values.extend(str(item) for item in value)
    normalized = []
    for value in values:
        clean = re.sub(r"\s+", " ", value.strip().lower())
        if clean and clean not in normalized:
            normalized.append(clean)
    return normalized


def score_cvss(metrics: Mapping[str, Any]) -> float:
    for key in ("cvss_score", "baseScore", "score"):
        value = metrics.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


@dataclass
class EnrichmentContext:
    repo_root: Path
    cve_cache: Dict[str, Any] = field(default_factory=dict)
    mitre_cache: Dict[str, Any] = field(default_factory=dict)
    threat_cache: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, repo_root: Path) -> "EnrichmentContext":
        return cls(
            repo_root=repo_root,
            cve_cache=load_json(repo_root / "knowledge/cve_tracker/tracker.json", {}),
            mitre_cache=load_json(repo_root / "knowledge/threat_intel/mitre_attack.json", {}),
            threat_cache=load_json(repo_root / "knowledge/threat_intel/ioc_feeds.json", {}),
        )

    def lookup_cve_local(self, cve_id: str) -> Optional[Record]:
        candidates = self.cve_cache.get("cves", []) if isinstance(self.cve_cache, dict) else []
        for item in candidates:
            if str(item.get("cve_id", item.get("id", ""))).upper() == cve_id.upper():
                return dict(item)
        return None

    def lookup_cve_nvd(self, cve_id: str) -> Optional[Record]:
        try:
            data = fetch_json(f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={quote(cve_id)}")
            vulnerabilities = data.get("vulnerabilities", [])
            if not vulnerabilities:
                return None
            cve = vulnerabilities[0].get("cve", {})
            metrics = cve.get("metrics", {})
            scores = []
            for metric_values in metrics.values():
                if isinstance(metric_values, list):
                    for metric in metric_values:
                        cvss = metric.get("cvssData", {}) if isinstance(metric, dict) else {}
                        score = score_cvss(cvss)
                        if score:
                            scores.append(score)
            descriptions = cve.get("descriptions", [])
            english = next((d.get("value") for d in descriptions if d.get("lang") == "en"), "")
            return {
                "cve_id": cve_id.upper(),
                "description": english,
                "published": cve.get("published"),
                "last_modified": cve.get("lastModified"),
                "cvss_score": max(scores) if scores else 0.0,
                "references": [ref.get("url") for ref in cve.get("references", {}).get("referenceData", []) if ref.get("url")],
                "source": "nvd",
            }
        except Exception as exc:
            return {"cve_id": cve_id.upper(), "lookup_error": str(exc), "source": "nvd"}

    def correlate_mitre(self, record: Mapping[str, Any]) -> List[Record]:
        text = json.dumps(record, sort_keys=True).lower()
        techniques: List[Record] = []
        cache_items = self.mitre_cache.get("techniques", []) if isinstance(self.mitre_cache, dict) else []
        for keyword, technique_ids in MITRE_KEYWORDS.items():
            if keyword not in text:
                continue
            for technique_id in technique_ids:
                cached = next((item for item in cache_items if item.get("id") == technique_id), None)
                techniques.append(cached or {"id": technique_id, "matched_keyword": keyword})
        unique: Dict[str, Record] = {}
        for item in techniques:
            unique[item.get("id", json.dumps(item, sort_keys=True))] = item
        return list(unique.values())

    def correlate_ioc(self, ioc: str) -> Optional[Record]:
        feeds = self.threat_cache.get("iocs", []) if isinstance(self.threat_cache, dict) else []
        for item in feeds:
            if str(item.get("ioc", item.get("indicator", ""))).lower() == ioc.lower():
                return dict(item)
        return None


class Enricher:
    def __init__(self, context: EnrichmentContext, live_nvd: bool = False) -> None:
        self.context = context
        self.live_nvd = live_nvd

    def enrich_record(self, record: Mapping[str, Any]) -> Record:
        enriched: Record = dict(record)
        cve_ids = sorted(extract_cves(record))
        tech = normalize_tech(record)
        for technology in tech:
            for hint, cpes in TECH_TO_CPE_HINTS.items():
                if hint in technology:
                    enriched.setdefault("cpe_hints", [])
                    for cpe in cpes:
                        if cpe not in enriched["cpe_hints"]:
                            enriched["cpe_hints"].append(cpe)

        cve_details = []
        for cve_id in cve_ids:
            detail = self.context.lookup_cve_local(cve_id)
            if detail is None and self.live_nvd:
                detail = self.context.lookup_cve_nvd(cve_id)
            if detail:
                cve_details.append(detail)
        if cve_ids:
            enriched["cves"] = cve_ids
        if cve_details:
            enriched["cve_details"] = cve_details
            enriched["max_cvss"] = max((float(item.get("cvss_score") or 0) for item in cve_details), default=0.0)

        iocs = sorted(extract_iocs(record))
        ioc_details = [self.context.correlate_ioc(ioc) for ioc in iocs]
        ioc_details = [item for item in ioc_details if item]
        if iocs:
            enriched["iocs"] = iocs[:100]
        if ioc_details:
            enriched["ioc_details"] = ioc_details

        mitre = self.context.correlate_mitre(enriched)
        if mitre:
            enriched["mitre_attack"] = mitre

        enriched["priority"] = self.priority(enriched)
        enriched["enriched_at"] = now()
        return enriched

    def priority(self, record: Mapping[str, Any]) -> str:
        max_cvss = float(record.get("max_cvss") or record.get("cvss_score") or 0)
        confidence = float(record.get("confidence") or 50)
        ioc_count = len(record.get("ioc_details", [])) if isinstance(record.get("ioc_details"), list) else 0
        if max_cvss >= 9 or ioc_count >= 3 or confidence >= 90:
            return "P1"
        if max_cvss >= 7 or ioc_count or confidence >= 70:
            return "P2"
        return "P3"

    def enrich_many(self, records: Iterable[Mapping[str, Any]]) -> List[Record]:
        return [self.enrich_record(record) for record in records]


def load_records(path: Path) -> List[Record]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "findings", "items", "targets", "cves", "iocs"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    raise ValueError(f"Unsupported JSON input: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich OpenClaw records with CVE, MITRE, and threat intelligence context")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--live-nvd", action="store_true", help="Query NVD for CVEs missing from local cache")
    args = parser.parse_args()
    context = EnrichmentContext.load(args.repo_root)
    records = Enricher(context, live_nvd=args.live_nvd).enrich_many(load_records(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"generated_at": now(), "records": records}, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"enriched": len(records), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
