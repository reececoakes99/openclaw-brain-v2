#!/usr/bin/env python3
"""Prefect orchestration for OpenClaw knowledge updates.

This module defines a real Prefect flow when Prefect is installed and also
provides an equivalent synchronous CLI fallback so the updater remains usable in
minimal environments. Source clients are intentionally generic HTTP clients that
read authentication and rate-limit configuration from sources.yaml.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urlencode

try:
    import httpx
except ImportError:  # pragma: no cover - dependency is runtime-installed by operators
    httpx = None  # type: ignore

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

try:
    from prefect import flow, task, get_run_logger
except Exception:  # pragma: no cover
    flow = None  # type: ignore
    task = None  # type: ignore

    def get_run_logger():  # type: ignore
        class Logger:
            def info(self, message: str, *args: Any) -> None:
                print(message % args if args else message)

            def warning(self, message: str, *args: Any) -> None:
                print("WARNING: " + (message % args if args else message))

            def error(self, message: str, *args: Any) -> None:
                print("ERROR: " + (message % args if args else message))

        return Logger()

from knowledge_updater.pipelines.deduplicator import Deduplicator
from knowledge_updater.pipelines.enricher import EnrichmentContext, Enricher

ROOT = Path(__file__).resolve().parents[2]
SOURCES_PATH = ROOT / "knowledge_updater/config/sources.yaml"
SCHEDULE_PATH = ROOT / "knowledge_updater/config/schedule.yaml"
OUTPUT_ROOT = ROOT / "knowledge/updater_fresh"
STATE_PATH = ROOT / "knowledge/bot_queue/knowledge_updater_state.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load updater configuration")
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in {path}")
    return loaded


def prefect_task(fn):
    return task(fn) if task else fn


def prefect_flow(fn):
    return flow(name="openclaw-knowledge-update")(fn) if flow else fn


@dataclass
class SourceResult:
    source: str
    status: str
    records: List[Dict[str, Any]]
    error: Optional[str] = None


class RateLimiter:
    def __init__(self, requests_per_minute: int, burst: int) -> None:
        self.delay = 60.0 / max(1, requests_per_minute)
        self.burst = max(1, burst)
        self.calls: List[float] = []

    async def wait(self) -> None:
        current = time.monotonic()
        self.calls = [item for item in self.calls if current - item < 60]
        if len(self.calls) >= self.burst:
            await asyncio.sleep(self.delay)
        self.calls.append(time.monotonic())


class SourceClient:
    def __init__(self, name: str, config: Mapping[str, Any], dry_run: bool = False) -> None:
        self.name = name
        self.config = config
        self.dry_run = dry_run
        limit = config.get("rate_limit", {}) if isinstance(config.get("rate_limit"), dict) else {}
        self.limiter = RateLimiter(int(limit.get("requests_per_minute", 60)), int(limit.get("burst", 5)))

    def auth_headers(self) -> Dict[str, str]:
        auth = self.config.get("auth", {}) if isinstance(self.config.get("auth"), dict) else {}
        auth_type = auth.get("type")
        headers: Dict[str, str] = {"User-Agent": "OpenClaw-Knowledge-Updater/1.0"}
        if auth_type == "bearer" and os.getenv(str(auth.get("token_env"))):
            headers["Authorization"] = f"Bearer {os.environ[str(auth['token_env'])]}"
        elif auth_type == "header" and os.getenv(str(auth.get("token_env"))):
            headers[str(auth.get("header", "X-API-Key"))] = os.environ[str(auth["token_env"])]
        return headers

    def query_auth_params(self) -> Dict[str, str]:
        auth = self.config.get("auth", {}) if isinstance(self.config.get("auth"), dict) else {}
        params: Dict[str, str] = {}
        if auth.get("type") == "query_param":
            token = os.getenv(str(auth.get("token_env")))
            if token:
                params[str(auth.get("param", "key"))] = token
        elif auth.get("type") == "query_params":
            for env_key, param in (("email_env", "email"), ("key_env", "key")):
                value = os.getenv(str(auth.get(env_key)))
                if value:
                    params[param] = value
        return params

    async def collect(self, category_filter: Iterable[str]) -> SourceResult:
        categories = set(category_filter)
        source_categories = set(self.config.get("categories", []))
        if categories and not categories.intersection(source_categories):
            return SourceResult(self.name, "skipped", [])
        if self.dry_run:
            return SourceResult(self.name, "dry_run", [self.metadata_record("dry_run")])
        if httpx is None:
            return SourceResult(self.name, "error", [], "httpx is required for live collection")

        base_url = str(self.config.get("base_url", "")).rstrip("/")
        endpoints = self.config.get("endpoints", {}) if isinstance(self.config.get("endpoints"), dict) else {}
        records: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30.0, headers=self.auth_headers()) as client:
            for endpoint_name, endpoint in endpoints.items():
                if "{" in str(endpoint):
                    continue
                await self.limiter.wait()
                params = self.query_auth_params()
                url = f"{base_url}{endpoint}"
                try:
                    response = await client.get(url, params=params)
                    if response.status_code in (401, 403):
                        records.append(self.metadata_record("auth_required", endpoint_name, response.status_code))
                        continue
                    if response.status_code == 429:
                        records.append(self.metadata_record("rate_limited", endpoint_name, response.status_code))
                        continue
                    response.raise_for_status()
                    body = response.json() if response.content else {}
                    records.append({
                        "source": self.name,
                        "endpoint": endpoint_name,
                        "category": sorted(source_categories),
                        "collected_at": now(),
                        "status_code": response.status_code,
                        "data": body,
                    })
                except Exception as exc:
                    records.append(self.metadata_record("collection_error", endpoint_name, error=str(exc)))
        return SourceResult(self.name, "ok", records)

    def metadata_record(self, status: str, endpoint: str = "metadata", status_code: Optional[int] = None, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "source": self.name,
            "endpoint": endpoint,
            "status": status,
            "status_code": status_code,
            "error": error,
            "categories": self.config.get("categories", []),
            "collected_at": now(),
            "confidence": 30 if error else 50,
        }


@prefect_task
def load_configs(cadence: str) -> Dict[str, Any]:
    sources = load_yaml(SOURCES_PATH)
    schedule = load_yaml(SCHEDULE_PATH)
    cadence_config = schedule.get("cadences", {}).get(cadence)
    if not cadence_config:
        raise ValueError(f"Unknown cadence: {cadence}")
    return {"sources": sources, "schedule": schedule, "cadence": cadence_config}


@prefect_task
async def collect_sources(configs: Mapping[str, Any], cadence: str, dry_run: bool = False) -> List[Dict[str, Any]]:
    logger = get_run_logger()
    source_registry = configs["sources"].get("sources", {})
    cadence_config = configs["cadence"]
    categories = cadence_config.get("categories", [])
    selected = cadence_config.get("sources", [])
    jitter = int(cadence_config.get("jitter_seconds", 0) or 0)
    if jitter and not dry_run:
        await asyncio.sleep(random.randint(0, min(jitter, 30)))
    tasks = []
    for name in selected:
        source_config = source_registry.get(name, {})
        if not source_config.get("enabled", False):
            logger.info("Skipping disabled source %s", name)
            continue
        tasks.append(SourceClient(name, source_config, dry_run=dry_run).collect(categories))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    records: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("Source collection failure: %s", result)
            continue
        logger.info("Source %s returned %s records", result.source, len(result.records))
        records.extend(result.records)
    return records


@prefect_task
def process_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    dedup_report = Deduplicator(fuzzy_threshold=0.88).deduplicate(records)
    context = EnrichmentContext.load(ROOT)
    enriched = Enricher(context, live_nvd=False).enrich_many(dedup_report.records)
    return {
        "input_count": dedup_report.input_count,
        "deduplicated_count": dedup_report.output_count,
        "exact_duplicates": dedup_report.exact_duplicates,
        "fuzzy_duplicates": dedup_report.fuzzy_duplicates,
        "identity_collisions": dedup_report.identity_collisions,
        "records": enriched,
    }


@prefect_task
def persist_results(cadence: str, payload: Mapping[str, Any]) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = OUTPUT_ROOT / cadence
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"knowledge_update_{run_id}.json"
    output_path.write_text(json.dumps({"cadence": cadence, "generated_at": now(), **payload}, indent=2, sort_keys=True), encoding="utf-8")
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({
        "last_run_at": now(),
        "cadence": cadence,
        "output_path": str(output_path.relative_to(ROOT)),
        "record_count": len(payload.get("records", [])),
    }, indent=2), encoding="utf-8")
    return output_path


@prefect_flow
def knowledge_update_flow(cadence: str = "standard", dry_run: bool = False) -> str:
    configs = load_configs(cadence)
    records = asyncio.run(collect_sources(configs, cadence, dry_run=dry_run))
    processed = process_records(records)
    output_path = persist_results(cadence, processed)
    return str(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenClaw knowledge updater orchestration")
    parser.add_argument("--cadence", choices=("critical", "standard", "deep"), default="standard")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    output = knowledge_update_flow(cadence=args.cadence, dry_run=args.dry_run)
    print(json.dumps({"output": output}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
