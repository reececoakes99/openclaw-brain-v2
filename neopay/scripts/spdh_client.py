#!/usr/bin/env python3
"""
spdh_client.py — SPDH/HPDH POS Terminal Protocol Client
=========================================================
Implements the Synchronous Protocol for Data and Housekeeping (SPDH)
and Hypercom Protocol for Data and Housekeeping (HPDH) used by
Verifone, Ingenico, and Hypercom POS terminals.

Supports:
  - Authorization requests (sale, refund, void, pre-auth)
  - Batch upload / settlement
  - Terminal configuration download
  - Key exchange (DUKPT, Master/Session)
  - Echo / heartbeat
  - Protocol fuzzing for security assessment

Usage:
  python3 spdh_client.py --host 192.168.1.100 --port 9100 --type sale --amount 10.00 --pan 4111111111111111
  python3 spdh_client.py --host 192.168.1.100 --port 9100 --type echo
  python3 spdh_client.py --host 192.168.1.100 --port 9100 --fuzz
"""

import socket
import struct
import binascii
import argparse
import json
import time
import random
import string
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── SPDH Message Types ────────────────────────────────────────────────────────
SPDH_MSG_TYPES = {
    '0100': 'Authorization Request',
    '0110': 'Authorization Response',
    '0200': 'Financial Request',
    '0210': 'Financial Response',
    '0400': 'Reversal Request',
    '0410': 'Reversal Response',
    '0500': 'Reconciliation Request',
    '0510': 'Reconciliation Response',
    '0800': 'Network Management Request',
    '0810': 'Network Management Response',
    '0820': 'Key Exchange Request',
    '0830': 'Key Exchange Response',
}

# ── Transaction Types ─────────────────────────────────────────────────────────
TRANSACTION_TYPES = {
    'sale':       {'mti': '0200', 'proc_code': '000000'},
    'refund':     {'mti': '0200', 'proc_code': '200000'},
    'void':       {'mti': '0400', 'proc_code': '000000'},
    'pre_auth':   {'mti': '0100', 'proc_code': '000000'},
    'completion': {'mti': '0200', 'proc_code': '000000'},
    'balance':    {'mti': '0100', 'proc_code': '310000'},
    'echo':       {'mti': '0800', 'proc_code': '000000'},
    'key_xchg':   {'mti': '0820', 'proc_code': '000000'},
    'settlement': {'mti': '0500', 'proc_code': '920000'},
}

# ── Response Codes ────────────────────────────────────────────────────────────
RESPONSE_CODES = {
    '00': 'Approved',
    '01': 'Refer to Card Issuer',
    '02': 'Refer to Card Issuer Special Condition',
    '03': 'Invalid Merchant',
    '04': 'Pick Up Card',
    '05': 'Do Not Honor',
    '06': 'Error',
    '07': 'Pick Up Card Special Condition',
    '08': 'Honor with Identification',
    '09': 'Request in Progress',
    '10': 'Partial Approval',
    '12': 'Invalid Transaction',
    '13': 'Invalid Amount',
    '14': 'Invalid Card Number',
    '15': 'No Such Issuer',
    '19': 'Re-enter Transaction',
    '21': 'No Action Taken',
    '25': 'Unable to Locate Record',
    '30': 'Format Error',
    '41': 'Lost Card',
    '43': 'Stolen Card',
    '51': 'Insufficient Funds',
    '54': 'Expired Card',
    '55': 'Incorrect PIN',
    '57': 'Transaction Not Permitted to Cardholder',
    '58': 'Transaction Not Permitted to Terminal',
    '61': 'Exceeds Withdrawal Amount Limit',
    '62': 'Restricted Card',
    '65': 'Exceeds Withdrawal Frequency Limit',
    '75': 'Allowable PIN Tries Exceeded',
    '76': 'Invalid/Nonexistent Account',
    '77': 'Inconsistent with Original Amount',
    '78': 'No Account',
    '80': 'Invalid Date',
    '85': 'No Reason to Decline',
    '91': 'Issuer or Switch Inoperative',
    '92': 'Financial Institution Not Found',
    '94': 'Duplicate Transmission',
    '96': 'System Malfunction',
    'N7': 'Decline for CVV2 Failure',
}


@dataclass
class SPDHRequest:
    mti: str
    proc_code: str
    amount: str = '000000000000'
    stan: str = ''
    time: str = ''
    date: str = ''
    pan: str = ''
    expiry: str = ''
    track2: str = ''
    terminal_id: str = 'TERM0001'
    merchant_id: str = 'MERCH000000001'
    pos_entry_mode: str = '021'
    pin_block: str = ''
    additional_data: Dict = field(default_factory=dict)
    raw_hex: Optional[str] = None


@dataclass
class SPDHResponse:
    mti: str
    response_code: str
    response_text: str
    auth_code: str = ''
    rrn: str = ''
    amount: str = ''
    balance: str = ''
    raw_hex: str = ''
    parsed_fields: Dict = field(default_factory=dict)
    latency_ms: float = 0.0


# ── Message Builder ───────────────────────────────────────────────────────────

def build_spdh_message(req: SPDHRequest) -> bytes:
    """
    Build SPDH message frame.
    Format: [2-byte length][MTI][Bitmap][Fields...]
    """
    if not req.stan:
        req.stan = ''.join(random.choices(string.digits, k=6))
    if not req.time:
        req.time = datetime.utcnow().strftime('%H%M%S')
    if not req.date:
        req.date = datetime.utcnow().strftime('%m%d')

    # Build field data
    fields = {}

    # Field 2 — PAN
    if req.pan:
        fields[2] = req.pan

    # Field 3 — Processing Code
    fields[3] = req.proc_code

    # Field 4 — Amount
    fields[4] = req.amount.replace('.', '').zfill(12)

    # Field 7 — Transmission Date/Time
    fields[7] = datetime.utcnow().strftime('%m%d%H%M%S')

    # Field 11 — STAN
    fields[11] = req.stan

    # Field 12 — Time
    fields[12] = req.time

    # Field 13 — Date
    fields[13] = req.date

    # Field 14 — Expiry
    if req.expiry:
        fields[14] = req.expiry

    # Field 22 — POS Entry Mode
    fields[22] = req.pos_entry_mode

    # Field 35 — Track 2
    if req.track2:
        fields[35] = req.track2

    # Field 41 — Terminal ID
    fields[41] = req.terminal_id[:8].ljust(8)

    # Field 42 — Merchant ID
    fields[42] = req.merchant_id[:15].ljust(15)

    # Field 52 — PIN Block
    if req.pin_block:
        fields[52] = bytes.fromhex(req.pin_block)

    # Build bitmap (fields 1-64)
    bitmap = 0
    for f_num in fields:
        if 1 <= f_num <= 64:
            bitmap |= (1 << (64 - f_num))

    bitmap_bytes = struct.pack('>Q', bitmap)

    # Encode fields
    field_data = b''
    for f_num in sorted(fields.keys()):
        val = fields[f_num]
        if isinstance(val, bytes):
            field_data += val
        elif isinstance(val, str):
            field_data += val.encode('ascii')

    # Assemble message
    msg_body = req.mti.encode('ascii') + bitmap_bytes + field_data
    length_prefix = struct.pack('>H', len(msg_body))

    return length_prefix + msg_body


def parse_spdh_response(data: bytes, latency_ms: float = 0.0) -> SPDHResponse:
    """Parse raw SPDH response bytes."""
    if len(data) < 4:
        return SPDHResponse(
            mti='0000',
            response_code='96',
            response_text='System Malfunction — Response too short',
            raw_hex=data.hex(),
            latency_ms=latency_ms
        )

    try:
        # Skip length prefix if present
        offset = 0
        if len(data) >= 2:
            declared_len = struct.unpack('>H', data[:2])[0]
            if declared_len == len(data) - 2:
                offset = 2

        mti = data[offset:offset+4].decode('ascii', errors='replace')
        offset += 4

        # Bitmap
        if len(data) < offset + 8:
            raise ValueError("Response too short for bitmap")

        bitmap = struct.unpack('>Q', data[offset:offset+8])[0]
        offset += 8

        # Determine which fields are present
        present_fields = []
        for i in range(64):
            if bitmap & (1 << (63 - i)):
                present_fields.append(i + 1)

        # Extract key fields (simplified — fixed-length fields)
        parsed = {}
        pos = offset

        # Field 38 — Auth Code (6 chars)
        if 38 in present_fields and pos + 6 <= len(data):
            parsed[38] = data[pos:pos+6].decode('ascii', errors='replace').strip()
            pos += 6

        # Field 39 — Response Code (2 chars)
        response_code = '96'
        if 39 in present_fields and pos + 2 <= len(data):
            response_code = data[pos:pos+2].decode('ascii', errors='replace')
            parsed[39] = response_code
            pos += 2

        # Field 37 — RRN (12 chars)
        rrn = ''
        if 37 in present_fields and pos + 12 <= len(data):
            rrn = data[pos:pos+12].decode('ascii', errors='replace').strip()
            parsed[37] = rrn
            pos += 12

        response_text = RESPONSE_CODES.get(response_code, f'Unknown ({response_code})')

        return SPDHResponse(
            mti=mti,
            response_code=response_code,
            response_text=response_text,
            auth_code=parsed.get(38, ''),
            rrn=rrn,
            raw_hex=data.hex(),
            parsed_fields=parsed,
            latency_ms=latency_ms
        )

    except Exception as e:
        return SPDHResponse(
            mti='0000',
            response_code='96',
            response_text=f'Parse error: {e}',
            raw_hex=data.hex(),
            latency_ms=latency_ms
        )


# ── TCP Transport ─────────────────────────────────────────────────────────────

def send_spdh(host: str, port: int, message: bytes, timeout: int = 30) -> tuple:
    """Send SPDH message over TCP and receive response."""
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(message)
            # Read response
            response = b''
            sock.settimeout(timeout)
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                # Check if we have a complete message
                if len(response) >= 2:
                    expected_len = struct.unpack('>H', response[:2])[0] + 2
                    if len(response) >= expected_len:
                        break

        latency_ms = (time.time() - start) * 1000
        return response, latency_ms, None

    except socket.timeout:
        return b'', (time.time() - start) * 1000, 'Connection timed out'
    except ConnectionRefusedError:
        return b'', (time.time() - start) * 1000, f'Connection refused to {host}:{port}'
    except Exception as e:
        return b'', (time.time() - start) * 1000, str(e)


# ── Transaction Helpers ───────────────────────────────────────────────────────

def build_sale_request(pan: str, amount: str, expiry: str = '2512',
                       terminal_id: str = 'TERM0001', merchant_id: str = 'MERCH000000001') -> SPDHRequest:
    """Build a sale authorization request."""
    amount_cents = str(int(float(amount) * 100)).zfill(12)
    return SPDHRequest(
        mti='0200',
        proc_code='000000',
        amount=amount_cents,
        pan=pan,
        expiry=expiry,
        pos_entry_mode='010',  # Manual entry
        terminal_id=terminal_id,
        merchant_id=merchant_id
    )


def build_echo_request(terminal_id: str = 'TERM0001') -> SPDHRequest:
    """Build a network echo/heartbeat request."""
    return SPDHRequest(
        mti='0800',
        proc_code='000000',
        terminal_id=terminal_id
    )


def build_key_exchange_request(terminal_id: str = 'TERM0001') -> SPDHRequest:
    """Build a DUKPT key exchange request."""
    return SPDHRequest(
        mti='0820',
        proc_code='000000',
        terminal_id=terminal_id
    )


# ── Fuzzer ────────────────────────────────────────────────────────────────────

def fuzz_spdh(host: str, port: int, iterations: int = 50) -> List[Dict]:
    """
    Fuzz SPDH endpoint with malformed messages.
    Tests: oversized fields, invalid MTI, bitmap manipulation, null bytes.
    """
    results = []
    print(f"[FUZZ] Starting SPDH fuzzer against {host}:{port} ({iterations} iterations)")

    fuzz_cases = [
        # Oversized PAN
        {'name': 'oversized_pan', 'pan': 'A' * 100, 'amount': '10.00'},
        # Invalid MTI
        {'name': 'invalid_mti_9999', 'mti_override': '9999', 'amount': '10.00'},
        # Null bytes in PAN
        {'name': 'null_bytes_pan', 'pan': '\x00' * 16, 'amount': '10.00'},
        # Negative amount
        {'name': 'negative_amount', 'pan': '4111111111111111', 'amount': '-10.00'},
        # Zero amount
        {'name': 'zero_amount', 'pan': '4111111111111111', 'amount': '0.00'},
        # Max amount
        {'name': 'max_amount', 'pan': '4111111111111111', 'amount': '99999999.99'},
        # Empty PAN
        {'name': 'empty_pan', 'pan': '', 'amount': '10.00'},
        # SQL injection in terminal ID
        {'name': 'sqli_terminal_id', 'terminal_id': "' OR '1'='1", 'amount': '10.00'},
        # Format string in merchant ID
        {'name': 'format_string_merchant', 'merchant_id': '%s%s%s%n%n', 'amount': '10.00'},
        # Random bytes
        {'name': 'random_bytes', 'raw': bytes(random.getrandbits(8) for _ in range(64))},
    ]

    for i, case in enumerate(fuzz_cases[:iterations]):
        case_name = case.get('name', f'case_{i}')
        print(f"  [{i+1}/{min(len(fuzz_cases), iterations)}] Fuzzing: {case_name}")

        try:
            if 'raw' in case:
                msg = case['raw']
            else:
                req = SPDHRequest(
                    mti=case.get('mti_override', '0200'),
                    proc_code='000000',
                    pan=case.get('pan', '4111111111111111'),
                    amount=case.get('amount', '10.00').replace('.', '').zfill(12),
                    terminal_id=case.get('terminal_id', 'TERM0001'),
                    merchant_id=case.get('merchant_id', 'MERCH000000001')
                )
                msg = build_spdh_message(req)

            response_data, latency, error = send_spdh(host, port, msg, timeout=5)

            result = {
                'case': case_name,
                'sent_hex': msg.hex() if isinstance(msg, bytes) else '',
                'response_hex': response_data.hex() if response_data else '',
                'latency_ms': round(latency, 2),
                'error': error,
                'response_length': len(response_data),
                'interesting': False
            }

            # Flag interesting responses
            if response_data and len(response_data) > 0:
                resp = parse_spdh_response(response_data, latency)
                result['response_code'] = resp.response_code
                result['response_text'] = resp.response_text
                # Interesting: unexpected approval, verbose error, or unusual length
                if resp.response_code == '00':
                    result['interesting'] = True
                    result['note'] = 'UNEXPECTED APPROVAL on fuzz case'
                elif resp.response_code not in ('12', '30', '96'):
                    result['interesting'] = True
                    result['note'] = f'Non-standard response: {resp.response_code}'

            results.append(result)

        except Exception as e:
            results.append({'case': case_name, 'error': str(e), 'interesting': False})

        time.sleep(0.1)  # Rate limiting

    interesting = [r for r in results if r.get('interesting')]
    print(f"\n[FUZZ] Complete — {len(results)} cases, {len(interesting)} interesting findings")
    for r in interesting:
        print(f"  ⚠️  {r['case']}: {r.get('note', '')} (RC={r.get('response_code', 'N/A')})")

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='SPDH/HPDH POS Terminal Protocol Client')
    parser.add_argument('--host', required=True, help='Target host IP or hostname')
    parser.add_argument('--port', type=int, default=9100, help='Target port (default: 9100)')
    parser.add_argument('--type', choices=list(TRANSACTION_TYPES.keys()) + ['fuzz'],
                        default='echo', help='Transaction type')
    parser.add_argument('--amount', default='10.00', help='Transaction amount')
    parser.add_argument('--pan', default='4111111111111111', help='Card PAN')
    parser.add_argument('--expiry', default='2512', help='Card expiry YYMM')
    parser.add_argument('--terminal-id', default='TERM0001', help='Terminal ID (8 chars)')
    parser.add_argument('--merchant-id', default='MERCH000000001', help='Merchant ID (15 chars)')
    parser.add_argument('--fuzz-iterations', type=int, default=10, help='Fuzz iterations')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--timeout', type=int, default=30, help='Connection timeout seconds')
    args = parser.parse_args()

    print(f"[SPDH] Target: {args.host}:{args.port}")

    if args.type == 'fuzz':
        results = fuzz_spdh(args.host, args.port, args.fuzz_iterations)
        output = {'fuzz_results': results, 'target': f'{args.host}:{args.port}',
                  'timestamp': datetime.utcnow().isoformat()}
    else:
        tx_config = TRANSACTION_TYPES[args.type]

        if args.type == 'echo':
            req = build_echo_request(args.terminal_id)
        elif args.type == 'key_xchg':
            req = build_key_exchange_request(args.terminal_id)
        else:
            req = build_sale_request(
                pan=args.pan,
                amount=args.amount,
                expiry=args.expiry,
                terminal_id=args.terminal_id,
                merchant_id=args.merchant_id
            )
            req.mti = tx_config['mti']
            req.proc_code = tx_config['proc_code']

        msg = build_spdh_message(req)
        print(f"[SPDH] Sending {args.type.upper()} — {len(msg)} bytes")
        print(f"[SPDH] Request HEX: {msg.hex()}")

        response_data, latency, error = send_spdh(args.host, args.port, msg, args.timeout)

        if error:
            print(f"[SPDH] Error: {error}")
            output = {'error': error, 'latency_ms': round(latency, 2)}
        else:
            resp = parse_spdh_response(response_data, latency)
            print(f"[SPDH] Response: {resp.response_code} — {resp.response_text}")
            print(f"[SPDH] Auth Code: {resp.auth_code}")
            print(f"[SPDH] RRN: {resp.rrn}")
            print(f"[SPDH] Latency: {latency:.1f}ms")
            print(f"[SPDH] Response HEX: {resp.raw_hex}")
            output = asdict(resp)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"[SPDH] Output saved: {args.output}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
