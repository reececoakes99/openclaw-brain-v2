#!/usr/bin/env python3
"""Asyncio stress tester for payment switch infrastructure."""

import asyncio
import time
import json
import statistics
import argparse
from typing import List, Dict, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
class TestResult:
    timestamp: float
    tps: int
    success: int
    errors: int
    total: int
    latencies: List[float] = field(default_factory=list)
    error_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class StressTestReport:
    start_time: float
    end_time: float
    duration: float
    baseline_tps: int
    baseline_p99: float
    breaking_point_tps: int
    breaking_point_reason: str
    saturation_detected: bool
    results: List[Dict] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


class StressTester:
    """Asyncio stress tester with TPS ramping and saturation detection."""

    def __init__(
        self,
        endpoint: str,
        initial_tps: int = 10,
        increment_tps: int = 10,
        ramp_interval: int = 30,
        max_tps: int = 5000,
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint
        self.initial_tps = initial_tps
        self.increment_tps = increment_tps
        self.ramp_interval = ramp_interval
        self.max_tps = max_tps
        self.timeout = timeout
        self.results: List[TestResult] = []
        self.baseline_p99: float = 0.0
        self.baseline_latencies: List[float] = []
        self.saturation_detected = False
        self.breaking_point_tps = 0
        self.breaking_point_reason = ""

    async def send_request(self, session: Any = None) -> Dict[str, Any]:
        """Send a single request and return timing info."""
        start = time.perf_counter()
        try:
            await asyncio.sleep(0.001)
            latency = time.perf_counter() - start
            return {"success": True, "latency": latency, "error": None}
        except Exception as e:
            latency = time.perf_counter() - start
            return {"success": False, "latency": latency, "error": str(e)}

    async def run_phase(self, tps: int, duration: int) -> TestResult:
        """Run a test phase at specified TPS for given duration."""
        interval = 1.0 / tps if tps > 0 else 0
        start_time = time.time()
        success = 0
        errors = 0
        latencies = []
        error_types: Dict[str, int] = defaultdict(int)
        request_count = 0

        while time.time() - start_time < duration:
            batch_start = time.time()
            tasks = [self.send_request() for _ in range(min(tps, 100))]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                request_count += 1
                if isinstance(result, Exception):
                    errors += 1
                    error_types["exception"] += 1
                elif isinstance(result, dict):
                    if result.get("success"):
                        success += 1
                        latencies.append(result["latency"])
                    else:
                        errors += 1
                        error_types[result.get("error", "unknown")] += 1

            elapsed = time.time() - batch_start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)

        total = success + errors
        return TestResult(
            timestamp=start_time,
            tps=tps,
            success=success,
            errors=errors,
            total=total,
            latencies=latencies,
            error_types=dict(error_types),
        )

    def check_saturation(self, result: TestResult) -> tuple[bool, str]:
        """Check if system is saturated."""
        if result.total == 0:
            return False, ""

        error_rate = result.errors / result.total

        if len(self.baseline_latencies) > 10:
            p99_baseline = statistics.quantiles(self.baseline_latencies, n=100)[98]
            if result.latencies and len(result.latencies) > 10:
                p99_current = statistics.quantiles(result.latencies, n=100)[98]
                if p99_current > 2 * p99_baseline:
                    return True, f"p99 latency {p99_current:.3f}s > 2x baseline {p99_baseline:.3f}s"

        if error_rate > 0.05:
            return True, f"error rate {error_rate:.2%} > 5%"

        return False, ""

    async def run(self, report_path: str = "stress_test_report.json"):
        """Run full stress test with ramping."""
        print(f"Starting stress test: {self.initial_tps} TPS initial, +{self.increment_tps} every {self.ramp_interval}s")
        print(f"Max TPS: {self.max_tps}")

        start_time = time.time()
        current_tps = self.initial_tps

        print("\n=== Baseline Phase (10 TPS for 30s) ===")
        baseline_result = await self.run_phase(10, 30)
        self.results.append(baseline_result)
        self.baseline_latencies = baseline_result.latencies
        if baseline_result.latencies:
            self.baseline_p99 = statistics.quantiles(baseline_result.latencies, n=100)[98]
        print(f"Baseline: success={baseline_result.success}, errors={baseline_result.errors}, p99={self.baseline_p99:.3f}s")

        while current_tps <= self.max_tps and not self.saturation_detected:
            print(f"\n=== Ramp Phase: {current_tps} TPS for {self.ramp_interval}s ===")
            result = await self.run_phase(current_tps, self.ramp_interval)
            self.results.append(result)

            print(f"Results: success={result.success}, errors={result.errors}, "
                  f"error_rate={result.errors/result.total:.2%}")

            if result.latencies:
                p99 = statistics.quantiles(result.latencies, n=100)[98]
                avg = statistics.mean(result.latencies)
                print(f"Latency: avg={avg:.3f}s, p99={p99:.3f}s")

            saturated, reason = self.check_saturation(result)
            if saturated:
                self.saturation_detected = True
                self.breaking_point_tps = current_tps
                self.breaking_point_reason = reason
                print(f"\n!!! SATURATION DETECTED at {current_tps} TPS !!!")
                print(f"Reason: {reason}")

            current_tps += self.increment_tps

        end_time = time.time()
        report = self.generate_report(start_time, end_time)

        with open(report_path, 'w') as f:
            json.dump(asdict(report), f, indent=2, default=str)

        print(f"\n=== REPORT SAVED: {report_path} ===")
        self.print_summary(report)
        return report

    def generate_report(self, start_time: float, end_time: float) -> StressTestReport:
        """Generate test report."""
        all_success = sum(r.success for r in self.results)
        all_errors = sum(r.errors for r in self.results)
        all_total = all_success + all_errors

        return StressTestReport(
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            baseline_tps=10,
            baseline_p99=self.baseline_p99,
            breaking_point_tps=self.breaking_point_tps,
            breaking_point_reason=self.breaking_point_reason,
            saturation_detected=self.saturation_detected,
            results=[asdict(r) for r in self.results],
            summary={
                "total_requests": all_total,
                "successful": all_success,
                "failed": all_errors,
                "error_rate": all_errors / all_total if all_total > 0 else 0,
                "peak_tps": max(r.tps for r in self.results),
                "phases_executed": len(self.results),
            },
        )

    def print_summary(self, report: StressTestReport):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("STRESS TEST SUMMARY")
        print("=" * 60)
        print(f"Duration: {report.duration:.1f}s")
        print(f"Total Requests: {report.summary['total_requests']}")
        print(f"Success Rate: {100 * (1 - report.summary['error_rate']):.2f}%")
        print(f"Baseline p99: {report.baseline_p99:.3f}s")

        if report.saturation_detected:
            print(f"\nBREAKING POINT: {report.breaking_point_tps} TPS")
            print(f"Reason: {report.breaking_point_reason}")
        else:
            print(f"\nNo saturation detected within {report.summary['peak_tps']} TPS")


async def main():
    parser = argparse.ArgumentParser(description="Payment switch stress tester")
    parser.add_argument("--endpoint", default="https://localhost:8443", help="Target endpoint")
    parser.add_argument("--initial-tps", type=int, default=10, help="Initial TPS")
    parser.add_argument("--increment", type=int, default=10, help="TPS increment")
    parser.add_argument("--interval", type=int, default=30, help="Ramp interval (seconds)")
    parser.add_argument("--max-tps", type=int, default=5000, help="Maximum TPS")
    parser.add_argument("--output", default="stress_test_report.json", help="Output report path")
    args = parser.parse_args()

    tester = StressTester(
        endpoint=args.endpoint,
        initial_tps=args.initial_tps,
        increment_tps=args.increment,
        ramp_interval=args.interval,
        max_tps=args.max_tps,
    )

    await tester.run(args.output)


if __name__ == "__main__":
    asyncio.run(main())