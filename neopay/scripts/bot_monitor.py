#!/usr/bin/env python3
"""Bot monitoring dashboard for payment switch operations."""
import redis, time, sys, argparse

ALERT_THRESHOLDS = {
    'error_rate': 0.01,
    'avg_time': 5.0,
    'queue_depth': 100
}

def format_num(n):
    if n >= 1000000: return f"{n/1e6:.1f}M"
    if n >= 1000: return f"{n/1e3:.1f}K"
    return str(n)

def monitor(redis_host='localhost', redis_port=6379, refresh=5):
    try:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        r.ping()
    except redis.ConnectionError as e:
        print(f"✗ Redis connection failed: {e}")
        sys.exit(1)

    print("=== Payment Switch Bot Monitor ===")
    print(f"Redis: {redis_host}:{redis_port}  |  Refresh: {refresh}s")
    print("-" * 70)

    while True:
        try:
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            errors = alerts = 0
            
            # Scan payment keys
            active = 0; queued = 0; total_time = 0.0; count = 0
            error_codes = {}
            
            for key in r.scan_iter('payment:*:status', count=200):
                active += 1
            
            for key in r.scan_iter('payment:*:queued', count=200):
                queued += 1
            
            for key in r.scan_iter('switch:*:txn:*', count=500):
                try:
                    t = r.hget(key, 'processing_time')
                    if t: total_time += float(t); count += 1
                    ec = r.hget(key, 'error_code')
                    if ec: error_codes[ec] = error_codes.get(ec, 0) + 1
                except: pass
            
            avg_time = total_time / count if count > 0 else 0
            error_rate = errors / max(active, 1)
            
            alerts_now = []
            if avg_time > ALERT_THRESHOLDS['avg_time']:
                alerts_now.append(f"⚠ AVG TIME {avg_time:.1f}s > {ALERT_THRESHOLDS['avg_time']}s")
            if queued > ALERT_THRESHOLDS['queue_depth']:
                alerts_now.append(f"⚠ QUEUE {queued} > {ALERT_THRESHOLDS['queue_depth']}")
            
            top_errors = sorted(error_codes.items(), key=lambda x: -x[1])[:5]
            
            print(f"\n[{ts}]")
            print(f"  Active: {format_num(active)}  Queued: {format_num(queued)}  "
                  f"Avg time: {avg_time:.2f}s  Errors: {error_rate:.1%}")
            if top_errors:
                print(f"  Top errors: {', '.join(f'{ec}({cnt})' for ec, cnt in top_errors)}")
            for a in alerts_now:
                print(f"  {a}")
            
            sys.stdout.flush()
            time.sleep(refresh)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(refresh)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-h', '--host', default='localhost')
    ap.add_argument('-p', '--port', type=int, default=6379)
    ap.add_argument('-r', '--refresh', type=int, default=5)
    args = ap.parse_args()
    monitor(args.host, args.port, args.refresh)
