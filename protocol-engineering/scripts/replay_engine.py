#!/usr/bin/env python3
"""Replay engine for ISO8583 message sequences with diff capabilities."""

import json
import asyncio
import time
import argparse
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from copy import deepcopy


@dataclass
class MessageSpec:
    """Specification for a single message."""
    mti: str
    fields: Dict[int, str] = field(default_factory=dict)
    raw: Optional[str] = None
    description: str = ""


@dataclass
class ReplayResult:
    """Result of a single message replay."""
    sequence_id: str
    message_id: str
    sent_at: float
    received_at: Optional[float]
    request: Dict
    response: Optional[Dict]
    latency_ms: Optional[float]
    success: bool
    error: Optional[str] = None
    field_diffs: List[Dict] = field(default_factory=list)


@dataclass
class ReplayReport:
    """Complete replay test report."""
    start_time: float
    end_time: float
    scenario_name: str
    total_messages: int
    successful: int
    failed: int
    results: List[Dict] = field(default_factory=list)
    field_changes: Dict[str, List[Dict]] = field(default_factory=dict)


class ReplayEngine:
    """Engine for replaying ISO8583 message sequences."""

    def __init__(
        self,
        endpoint: str,
        concurrency: int = 1,
        repeat: int = 1,
        delay_ms: int = 0,
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint
        self.concurrency = concurrency
        self.repeat = repeat
        self.delay_ms = delay_ms
        self.timeout = timeout
        self.results: List[ReplayResult] = []

    async def send_message(self, message: MessageSpec) -> Dict:
        """Send a single ISO8583 message (stub - replace with actual client)."""
        await asyncio.sleep(0.001)
        return {
            "success": True,
            "mti": self._response_mti(message.mti),
            "fields": deepcopy(message.fields),
        }

    def _response_mti(self, request_mti: str) -> str:
        """Generate expected response MTI."""
        if len(request_mti) == 4:
            response_mti = request_mti[:2] + "1" + request_mti[3]
            return response_mti
        return "0110"

    async def replay_sequence(
        self,
        messages: List[MessageSpec],
        sequence_id: str,
    ) -> List[ReplayResult]:
        """Replay a sequence of messages."""
        results = []
        for i, msg in enumerate(messages):
            msg_id = f"{sequence_id}_{i+1}"

            sent_at = time.time()
            response = None
            error = None

            try:
                response = await asyncio.wait_for(
                    self.send_message(msg),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                error = "Timeout"
            except Exception as e:
                error = str(e)

            received_at = time.time() if error is None else None
            latency = (received_at - sent_at) * 1000 if received_at else None

            field_diffs = []
            if response:
                field_diffs = self._compare_fields(msg.fields, response.get("fields", {}))

            result = ReplayResult(
                sequence_id=sequence_id,
                message_id=msg_id,
                sent_at=sent_at,
                received_at=received_at,
                request={"mti": msg.mti, "fields": msg.fields},
                response=response,
                latency_ms=latency,
                success=error is None,
                error=error,
                field_diffs=field_diffs,
            )

            results.append(result)
            self.results.append(result)

            if self.delay_ms > 0:
                await asyncio.sleep(self.delay_ms / 1000.0)

        return results

    def _compare_fields(
        self,
        expected: Dict[int, str],
        actual: Dict[int, str],
    ) -> List[Dict]:
        """Compare expected vs actual fields and return diffs."""
        diffs = []

        all_keys = set(expected.keys()) | set(actual.keys())

        for key in sorted(all_keys):
            exp_val = expected.get(key, "")
            act_val = actual.get(key, "")

            if exp_val != act_val:
                diffs.append({
                    "field": key,
                    "expected": exp_val,
                    "actual": act_val,
                    "change_type": self._classify_change(exp_val, act_val),
                })

        return diffs

    def _classify_change(self, expected: str, actual: str) -> str:
        """Classify the type of field change."""
        if not expected and actual:
            return "added"
        if expected and not actual:
            return "removed"
        if expected != actual:
            return "modified"
        return "unchanged"

    async def run_scenario(self, scenario: Dict) -> ReplayReport:
        """Run a complete replay scenario."""
        start_time = time.time()
        scenario_name = scenario.get("name", "Unnamed")

        messages = []
        for msg_spec in scenario.get("messages", []):
            messages.append(MessageSpec(
                mti=msg_spec["mti"],
                fields=msg_spec.get("fields", {}),
                raw=msg_spec.get("raw"),
                description=msg_spec.get("description", ""),
            ))

        all_results = []

        for iteration in range(self.repeat):
            seq_id = f"{scenario_name}_{iteration + 1}"
            results = await self.replay_sequence(messages, seq_id)
            all_results.extend(results)

            if self.concurrency > 1 and iteration < self.repeat - 1:
                await asyncio.sleep(0.01)

        end_time = time.time()

        field_changes = self._aggregate_field_changes(all_results)

        report = ReplayReport(
            start_time=start_time,
            end_time=end_time,
            scenario_name=scenario_name,
            total_messages=len(all_results),
            successful=sum(1 for r in all_results if r.success),
            failed=sum(1 for r in all_results if not r.success),
            results=[asdict(r) for r in all_results],
            field_changes=field_changes,
        )

        return report

    def _aggregate_field_changes(self, results: List[ReplayResult]) -> Dict[str, List[Dict]]:
        """Aggregate field changes across all results."""
        changes: Dict[str, List[Dict]] = defaultdict(list)

        for result in results:
            for diff in result.field_diffs:
                field_key = str(diff["field"])
                changes[field_key].append({
                    "message_id": result.message_id,
                    "change_type": diff["change_type"],
                    "expected": diff["expected"],
                    "actual": diff["actual"],
                })

        return dict(changes)

    def export_diff(
        self,
        result: ReplayResult,
        format: str = "json",
    ) -> Dict:
        """Export diff between request and response."""
        if not result.response:
            return {"error": "No response to diff"}

        return {
            "message_id": result.message_id,
            "request": {
                "mti": result.request["mti"],
                "fields": result.request["fields"],
            },
            "response": result.response,
            "field_diffs": result.field_diffs,
            "summary": {
                "added": sum(1 for d in result.field_diffs if d["change_type"] == "added"),
                "removed": sum(1 for d in result.field_diffs if d["change_type"] == "removed"),
                "modified": sum(1 for d in result.field_diffs if d["change_type"] == "modified"),
            },
        }


def load_scenarios(path: str) -> List[Dict]:
    """Load replay scenarios from JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and "scenarios" in data:
        return data["scenarios"]
    else:
        return [data]


def print_report(report: ReplayReport):
    """Print replay report summary."""
    duration = report.end_time - report.start_time
    success_rate = (report.successful / report.total_messages * 100) if report.total_messages > 0 else 0

    print("\n" + "=" * 60)
    print(f"REPLAY REPORT: {report.scenario_name}")
    print("=" * 60)

    print(f"\nDuration: {duration:.2f}s")
    print(f"Total Messages: {report.total_messages}")
    print(f"Successful: {report.successful}")
    print(f"Failed: {report.failed}")
    print(f"Success Rate: {success_rate:.1f}%")

    if report.field_changes:
        print(f"\n--- Field Changes ---")
        for field_num, changes in sorted(report.field_changes.items(), key=lambda x: int(x[0])):
            change_types = defaultdict(int)
            for change in changes:
                change_types[change["change_type"]] += 1
            print(f"  Field {field_num}: {dict(change_types)}")

    print(f"\n--- Message Details ---")
    for result in report.results[:10]:
        status = "OK" if result.success else "FAIL"
        lat = f"{result.latency_ms:.1f}ms" if result.latency_ms else "N/A"
        diffs = len(result.field_diffs)
        print(f"  [{status}] {result.message_id}: lat={lat}, diffs={diffs}")


async def main():
    parser = argparse.ArgumentParser(description="ISO8583 replay engine")
    parser.add_argument("--scenarios", required=True, help="Path to scenarios JSON")
    parser.add_argument("--endpoint", default="https://localhost:8443", help="Target endpoint")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent sequences")
    parser.add_argument("--repeat", type=int, default=1, help="Number of repetitions")
    parser.add_argument("--delay", type=int, default=0, help="Delay between messages (ms)")
    parser.add_argument("--output", default="replay_report.json", help="Output report path")
    args = parser.parse_args()

    scenarios = load_scenarios(args.scenarios)

    engine = ReplayEngine(
        endpoint=args.endpoint,
        concurrency=args.concurrency,
        repeat=args.repeat,
        delay_ms=args.delay,
    )

    all_reports = []

    for scenario in scenarios:
        print(f"\nReplaying scenario: {scenario.get('name', 'Unnamed')}")
        report = await engine.run_scenario(scenario)
        all_reports.append(asdict(report))
        print_report(report)

    with open(args.output, 'w') as f:
        json.dump({
            "reports": all_reports,
            "summary": {
                "total_scenarios": len(all_reports),
                "total_messages": sum(r["total_messages"] for r in all_reports),
                "total_successful": sum(r["successful"] for r in all_reports),
                "total_failed": sum(r["failed"] for r in all_reports),
            },
        }, f, indent=2)

    print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())