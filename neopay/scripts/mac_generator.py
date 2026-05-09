#!/usr/bin/env python3
"""MAC generator/verifier — ISO9797-1 M1/M2/M3."""

import argparse
from dataclasses import dataclass

from Crypto.Cipher import DES


def _pad_data(data: bytes, block_size: int = 8) -> bytes:
    """ISO9797-1 Padding Method 1: append 0x80, then 0x00... to block boundary."""
    padded = bytearray(data)
    padded.append(0x80)
    while len(padded) % block_size != 0:
        padded.append(0x00)
    return bytes(padded)


def _xor_blocks(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _des_cbc(key: bytes, data: bytes, iv: bytes) -> bytes:
    cipher = DES.new(key, DES.MODE_CBC, iv)
    return cipher.encrypt(data)


def mac_iso9797_m1(key: bytes, data: bytes) -> bytes:
    """ISO9797-1 Method 1 — DES CBC with zero IV, single-length key."""
    padded = _pad_data(data)
    iv = b'\x00' * 8
    for i in range(0, len(padded), 8):
        block = padded[i:i + 8]
        iv = _des_cbc(key, block, iv)
    return iv


def mac_iso9797_m2(key: bytes, data: bytes) -> bytes:
    """ISO9797-1 Method 2 — DES CBC with zero IV, double-length key."""
    k1 = key[:8]
    k2 = key[8:16]
    padded = _pad_data(data)
    iv = b'\x00' * 8
    for i in range(0, len(padded), 8):
        block = padded[i:i + 8]
        iv = _des_cbc(k1, block, iv)
    iv = _xor_blocks(iv, k2)
    iv = _des_cbc(k1, iv, b'\x00' * 8)
    return iv


def mac_iso9797_m3(key: bytes, data: bytes) -> bytes:
    """ISO9797-1 Method 3 — ANSI X9.19 (visa variant) — DES encrypt/decrypt."""
    k1 = key[:8]
    k2 = key[8:16]
    padded = _pad_data(data)
    iv = b'\x00' * 8
    for i in range(0, len(padded), 8):
        block = padded[i:i + 8]
        iv = _des_cbc(k1, block, iv)
    result = _xor_blocks(iv, k2)
    cipher = DES.new(k1, DES.MODE_ECB)
    return cipher.encrypt(result)


ALGORITHMS = {
    "M1": mac_iso9797_m1,
    "M2": mac_iso9797_m2,
    "M3": mac_iso9797_m3,
}


def generate_mac(key_hex: str, data: bytes, algorithm: str = "M1") -> bytes:
    key = bytes.fromhex(key_hex)
    fn = ALGORITHMS.get(algorithm, mac_iso9797_m1)
    return fn(key, data)


def verify_mac(key_hex: str, data: bytes, mac: bytes, algorithm: str = "M1") -> bool:
    computed = generate_mac(key_hex, data, algorithm)
    return computed == mac


@dataclass
class MACResult:
    algorithm: str
    key_masked: str
    data_length: int
    mac_hex: str
    mac_bytes: bytes


def main():
    parser = argparse.ArgumentParser(description="ISO9797-1 MAC Generator")
    parser.add_argument("--key", required=True, help="MAC key (hex, 8 or 16 bytes)")
    parser.add_argument("--data", required=True, help="Data to MAC (hex)")
    parser.add_argument("--algorithm", default="M1",
                        choices=["M1", "M2", "M3"], help="MAC algorithm")
    parser.add_argument("--verify", help="Expected MAC to verify against (hex)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    data = bytes.fromhex(args.data.replace(" ", ""))
    mac = generate_mac(args.key.replace(" ", ""), data, args.algorithm)

    if args.verify:
        expected = bytes.fromhex(args.verify.replace(" ", ""))
        match = mac == expected
        if args.json:
            import json
            print(json.dumps({
                "valid": match,
                "computed": mac.hex().upper(),
                "expected": args.verify.upper(),
            }, indent=2))
        else:
            print(f"MAC Verification: {'PASS' if match else 'FAIL'}")
            print(f"Computed: {mac.hex().upper()}")
            print(f"Expected: {args.verify.upper()}")
    else:
        if args.json:
            import json
            print(json.dumps({
                "algorithm": args.algorithm,
                "key_masked": args.key[:4] + "..." + args.key[-4:],
                "data_length": len(data),
                "mac_hex": mac.hex().upper(),
            }, indent=2))
        else:
            print(f"MAC Generator — ISO9797-1 Algorithm {args.algorithm}")
            print(f"Key (masked): {args.key[:4]}...{args.key[-4:]}")
            print(f"Data length: {len(data)} bytes")
            print(f"MAC: {mac.hex().upper()}")


if __name__ == "__main__":
    main()
