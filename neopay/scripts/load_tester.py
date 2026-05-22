#!/usr/bin/env python3
"""
Load tester for payment switch infrastructure.
Spawns configurable concurrent ISO8583 message sends and tracks TPS, latency, error rates.
"""

import asyncio
import socket
import ssl
import struct
import time
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import argparse


@dataclass
class LatencyStats:
    values: List[float] = field(default_factory=list)
    
    def add(self, value: float):
        self.values.append(value)
    
    def get_percentile(self, p: float) -> float:
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = int(len(sorted_vals) * p / 100)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]
    
    def reset(self):
        self.values.clear()


@dataclass
class Metrics:
    total_sent: int = 0
    total_success: int = 0
    total_errors: int = 0
    total_timeouts: int = 0
    latency: LatencyStats = field(default_factory=LatencyStats)
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    def reset(self):
        self.total_sent = 0
        self.total_success = 0
        self.total_errors = 0
        self.total_timeouts = 0
        self.latency.reset()
        self.errors_by_type.clear()


class LoadTester:
    def __init__(
        self,
        host: str,
        port: int,
        use_tls: bool = False,
        concurrency: int = 10,
        duration: int = 60,
        timeout: float = 30.0,
        message_templates: Optional[Dict[str, str]] = None,
    ):
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.concurrency = concurrency
        self.duration = duration
        self.timeout = timeout
        self.message_templates = message_templates or self._default_templates()
        self.running = True
        self.metrics = Metrics()
        self.start_time = None
        self._lock = asyncio.Lock()
    
    def _default_templates(self) -> Dict[str, str]:
        """Default HISO93 binary message templates per MTI."""
        return {
            "0100": "0200A0000002040000000010000000000000000000000016010112345678901234500000000000000010112345678901234F600000100000100060301234567",
            "0120": "0200A0000002040000000010000000000000000000000016010112345678901234500000000000000010112345678901234F600000100000100060301234567",
            "0200": "0200A0000002040000000010000000000000000000000016010112345678901234500000000000000010112345678901234F600000100000100060301234567",
            "0210": "0200A0000002040000000010000000000000000000000016010112345678901234500000000000000010112345678901234F600000100000100060301234567",
            "0400": "0200A0000002040000000010000000000000000000000016010112345678901234500000000000000010112345678901234F600000100000100060301234567",
            "0420": "0200A0000002040000000010000000000000000000000016010112345678901234500000000000000010112345678901234F600000100000100060301234567",
        }
    
    def hex_to_bytes(self, hex_str: str) -> bytes:
        """Convert hex string to bytes, optionally with length prefix for ASCII mode."""
        clean_hex = hex_str.replace(" ", "").replace("\n", "")
        return bytes.fromhex(clean_hex)
    
    async def send_message_raw(self, message: bytes) -> tuple[bool, float, str]:
        """Send message via raw TCP socket."""
        start_time = time.time()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout
            )
            
            writer.write(message)
            await writer.drain()
            
            response = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
            latency = time.time() - start_time
            
            writer.close()
            await writer.wait_closed()
            
            if response:
                return True, latency, ""
            return False, latency, "No response received"
        except asyncio.TimeoutError:
            latency = time.time() - start_time
            return False, latency, "Timeout"
        except Exception as e:
            latency = time.time() - start_time
            return False, latency, str(e)
    
    async def send_message_tls(self, message: bytes) -> tuple[bool, float, str]:
        """Send message via TLS connection."""
        start_time = time.time()
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, ssl=context),
                timeout=self.timeout
            )
            
            writer.write(message)
            await writer.drain()
            
            response = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
            latency = time.time() - start_time
            
            writer.close()
            await writer.wait_closed()
            
            if response:
                return True, latency, ""
            return False, latency, "No response received"
        except asyncio.TimeoutError:
            latency = time.time() - start_time
            return False, latency, "Timeout"
        except Exception as e:
            latency = time.time() - start_time
            return False, latency, str(e)
    
    async def worker(self, worker_id: int, mti: str):
        """Worker coroutine that sends messages continuously."""
        message = self.hex_to_bytes(self.message_templates.get(mti, self.message_templates["0100"]))
        send_func = self.send_message_tls if self.use_tls else self.send_message_raw
        
        while self.running:
            success, latency, error = await send_func(message)
            
            async with self._lock:
                self.metrics.total_sent += 1
                self.metrics.latency.add(latency * 1000)  # Convert to ms
                
                if success:
                    self.metrics.total_success += 1
                elif "Timeout" in error:
                    self.metrics.total_timeouts += 1
                    self.metrics.errors_by_type["timeout"] += 1
                else:
                    self.metrics.total_errors += 1
                    self.metrics.errors_by_type[error[:50]] += 1
            
            await asyncio.sleep(0.01)  # Brief pause between sends
    
    def print_stats(self):
        """Print real-time statistics."""
        elapsed = time.time() - self.start_time
        tps = self.metrics.total_sent / elapsed if elapsed > 0 else 0
        
        error_rate = (self.metrics.total_errors + self.metrics.total_timeouts) / self.metrics.total_sent * 100 if self.metrics.total_sent > 0 else 0
        timeout_rate = self.metrics.total_timeouts / self.metrics.total_sent * 100 if self.metrics.total_sent > 0 else 0
        
        p50 = self.metrics.latency.get_percentile(50)
        p95 = self.metrics.latency.get_percentile(95)
        p99 = self.metrics.latency.get_percentile(99)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(
            f"[{timestamp}] "
            f"TPS: {tps:7.1f} | "
            f"Sent: {self.metrics.total_sent:6d} | "
            f"OK: {self.metrics.total_success:6d} | "
            f"Err: {self.metrics.total_errors:4d} | "
            f"TO: {self.metrics.total_timeouts:4d} | "
            f"Err%: {error_rate:5.2f}% | "
            f"Latency p50/p95/p99: {p50:6.1f}/{p95:6.1f}/{p99:6.1f}ms",
            flush=True
        )
    
    async def run(self):
        """Main execution loop."""
        mtis = list(self.message_templates.keys())
        workers = [
            asyncio.create_task(self.worker(i, mtis[i % len(mtis)]))
            for i in range(self.concurrency)
        ]
        
        self.start_time = time.time()
        last_print = self.start_time
        
        print(f"\n{'='*100}")
        print(f"Load Tester Started - Target: {self.host}:{self.port} ({'TLS' if self.use_tls else 'RAW'})")
        print(f"Concurrency: {self.concurrency} | Duration: {self.duration}s | MTIs: {mtis}")
        print(f"{'='*100}\n")
        
        while self.running and (time.time() - self.start_time) < self.duration:
            await asyncio.sleep(0.1)
            
            if time.time() - last_print >= 1.0:
                self.print_stats()
                last_print = time.time()
        
        self.running = False
        await asyncio.gather(*workers, return_exceptions=True)
        
        # Final stats
        print(f"\n{'='*100}")
        print("FINAL RESULTS")
        print(f"{'='*100}")
        self.print_stats()
        
        if self.metrics.errors_by_type:
            print("\nError Breakdown:")
            for error_type, count in sorted(self.metrics.errors_by_type.items(), key=lambda x: -x[1]):
                print(f"  {error_type}: {count}")
        
        return {
            "total_sent": self.metrics.total_sent,
            "total_success": self.metrics.total_success,
            "total_errors": self.metrics.total_errors,
            "total_timeouts": self.metrics.total_timeouts,
            "error_rate": error_rate,
            "tps": tps,
            "latency_p50": p50,
            "latency_p95": p95,
            "latency_p99": p99,
        }


async def main():
    parser = argparse.ArgumentParser(description="ISO8583 Load Tester")
    parser.add_argument("--host", default="localhost", help="Target host")
    parser.add_argument("--port", type=int, default=7000, help="Target port")
    parser.add_argument("--tls", action="store_true", help="Use TLS")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent connections")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout")
    parser.add_argument("--templates", type=str, help="JSON file with message templates")
    
    args = parser.parse_args()
    
    templates = None
    if args.templates:
        with open(args.templates) as f:
            templates = json.load(f)
    
    tester = LoadTester(
        host=args.host,
        port=args.port,
        use_tls=args.tls,
        concurrency=args.concurrency,
        duration=args.duration,
        timeout=args.timeout,
        message_templates=templates,
    )
    
    results = await tester.run()
    
    with open("load_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to load_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())
