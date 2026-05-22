#!/usr/bin/env python3
"""PCAP analysis utilities for payment protocol traffic."""
import argparse, logging, struct, sys, json
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

try:
    from scapy.all import rdpcap, IP, TCP, Raw
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    logger.warning("scapy not available — running in hex-only mode (pip install scapy to enable pcap parsing)")


def detect_iso8583(data: bytes) -> dict:
    """Attempt to detect ISO8583 message in raw bytes."""
    result = {'detected': False, 'mti': None, 'encoding': None, 'confidence': 0}
    if len(data) < 4:
        return result

    # ASCII MTI check (1987 version)
    try:
        mti_bytes = data[:4]
        mti_str = mti_bytes.decode('ascii')
        if mti_str.isdigit():
            result['mti'] = mti_str
            result['encoding'] = 'ASCII'
            result['detected'] = True
            result['confidence'] = 90
    except ValueError:
        pass

    # Binary MTI check (HISO93)
    if not result['detected'] and len(data) >= 2:
        mti_int = struct.unpack('!H', data[:2])[0]
        if 100 <= (mti_int % 10000) <= 9999:
            result['mti'] = f'{mti_int:04d}'
            result['encoding'] = 'BINARY'
            result['detected'] = True
            result['confidence'] = 75

    return result


def parse_pcap_scapy(pcap_path: str, port_filter: list = None) -> list:
    """Parse PCAP with scapy — extract ISO8583 messages."""
    if port_filter is None:
        port_filter = list(range(7000, 9001))

    messages = []
    try:
        packets = rdpcap(pcap_path)
        logger.info(f"Loaded {len(packets)} packets from {pcap_path}")
    except Exception as e:
        logger.error(f"Failed to read PCAP: {e}")
        return []

    for pkt in packets:
        try:
            if not pkt.haslayer(IP) or not pkt.haslayer(TCP):
                continue
            sport = pkt[TCP].sport
            dport = pkt[TCP].dport

            if sport not in port_filter and dport not in port_filter:
                continue

            if pkt.haslayer(Raw):
                payload = bytes(pkt[Raw].load)
                if len(payload) < 4:
                    continue

                ts = float(pkt.time)
                src = pkt[IP].src
                dst = pkt[IP].dst

                iso_info = detect_iso8583(payload)
                if iso_info['detected']:
                    msg = {
                        'timestamp': ts,
                        'time_str': datetime.fromtimestamp(ts).isoformat(),
                        'src': src,
                        'dst': dst,
                        'sport': sport,
                        'dport': dport,
                        'size': len(payload),
                        'mti': iso_info['mti'],
                        'encoding': iso_info['encoding'],
                        'confidence': iso_info['confidence'],
                        'hex': payload[:128].hex()
                    }
                    messages.append(msg)
                    logger.debug(f"  Found ISO8583: {iso_info['mti']} from {src}:{sport} → {dst}:{dport}")
        except Exception as e:
            logger.warning(f"Failed to parse packet: {e}")
            continue

    return messages


def parse_hex_file(hex_path: str) -> list:
    """Parse a file containing hex-encoded ISO8583 messages."""
    messages = []
    try:
        content = Path(hex_path).read_text()
    except Exception as e:
        logger.error(f"Cannot read file {hex_path}: {e}")
        return []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        hex_clean = line.replace(' ', '').replace('\n', '')
        try:
            data = bytes.fromhex(hex_clean)
            iso_info = detect_iso8583(data)
            if iso_info['detected']:
                messages.append({
                    'source_file': hex_path,
                    'mti': iso_info['mti'],
                    'encoding': iso_info['encoding'],
                    'confidence': iso_info['confidence'],
                    'size': len(data),
                    'hex': data[:128].hex()
                })
        except ValueError:
            continue

    return messages


def count_by_mti(messages: list) -> dict:
    """Count messages by MTI."""
    counts = {}
    for m in messages:
        mti = m.get('mti', 'unknown')
        counts[mti] = counts.get(mti, 0) + 1
    return dict(sorted(counts.items()))


def find_retransmissions(messages: list, window_seconds: float = 30.0) -> list:
    """Find potential retransmissions (same RRN within time window)."""
    rrn_seen = {}
    duplicates = []

    for m in messages:
        rrn = m.get('rrn') or m.get('hex', '')[:12]  # Use first 12 hex chars as fallback RRN
        ts = m.get('timestamp', 0)
        key = rrn

        if key in rrn_seen:
            prev_ts = rrn_seen[key]
            if ts - prev_ts < window_seconds:
                duplicates.append({
                    'rrn': rrn,
                    'first_ts': prev_ts,
                    'second_ts': ts,
                    'interval': ts - prev_ts
                })
        else:
            rrn_seen[key] = ts

    return duplicates


def calculate_timing(messages: list) -> dict:
    """Calculate transaction timing from message timestamps."""
    if len(messages) < 2:
        return {}

    timestamps = [m.get('timestamp', 0) for m in messages if 'timestamp' in m]
    if not timestamps:
        return {}

    intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]

    return {
        'total_messages': len(messages),
        'first_ts': datetime.fromtimestamp(min(timestamps)).isoformat(),
        'last_ts': datetime.fromtimestamp(max(timestamps)).isoformat(),
        'duration_seconds': max(timestamps) - min(timestamps),
        'avg_interval': sum(intervals) / len(intervals) if intervals else 0,
        'max_interval': max(intervals) if intervals else 0,
        'min_interval': min(intervals) if intervals else 0
    }


def export_hex(messages: list, output_path: str):
    """Export messages as hex strings."""
    try:
        with open(output_path, 'w') as f:
            for m in messages:
                f.write(f"# {m.get('time_str', '?')} {m.get('mti', '?')}\n")
                f.write(f"{m.get('hex', '')}\n\n")
        logger.info(f"Exported {len(messages)} messages to {output_path}")
    except Exception as e:
        logger.error(f"Failed to write hex export: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='PCAP analysis utilities for ISO8583 payment traffic',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('input', help='PCAP file or hex text file')
    parser.add_argument('--ports', nargs='+', type=int, default=list(range(7000, 9001)),
                        help='Filter by ports (default: 7000-9000)')
    parser.add_argument('--output', '-o', help='Output file (JSON or hex export)')
    parser.add_argument('--export-hex', action='store_true', help='Export as hex strings')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--find-dupes', action='store_true', help='Find retransmissions')
    parser.add_argument('--timing', action='store_true', help='Calculate timing stats')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Processing: {args.input}")

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"File not found: {args.input}")
        sys.exit(1)

    if input_path.suffix.lower() == '.pcap' or input_path.suffix.lower() == '.pcapng':
        if not SCAPY_AVAILABLE:
            logger.error("scapy required for PCAP parsing. Install: pip install scapy")
            sys.exit(1)
        messages = parse_pcap_scapy(str(input_path), port_filter=args.ports)
    else:
        messages = parse_hex_file(str(input_path))

    if not messages:
        logger.warning("No ISO8583 messages detected")
        sys.exit(0)

    logger.info(f"Found {len(messages)} ISO8583 messages")

    if args.stats:
        counts = count_by_mti(messages)
        print("\n=== MTI Distribution ===")
        for mti, cnt in counts.items():
            print(f"  {mti}: {cnt}")

    if args.find_dupes:
        dupes = find_retransmissions(messages)
        print(f"\n=== Retransmissions Found: {len(dupes)} ===")
        for d in dupes:
            print(f"  RRN {d['rrn']}: {d['interval']:.2f}s interval")

    if args.timing:
        timing = calculate_timing(messages)
        print("\n=== Timing Analysis ===")
        for k, v in timing.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.3f}")
            else:
                print(f"  {k}: {v}")

    if args.output:
        try:
            if args.export_hex:
                export_hex(messages, args.output)
            else:
                with open(args.output, 'w') as f:
                    json.dump(messages, f, indent=2)
                logger.info(f"Wrote {len(messages)} messages to {args.output}")
        except Exception as e:
            logger.error(f"Output failed: {e}")
            sys.exit(1)

    logger.info("Done")


if __name__ == '__main__':
    main()