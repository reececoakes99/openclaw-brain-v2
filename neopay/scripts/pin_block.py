#!/usr/bin/env python3
"""PIN block calculator — ISO9564 formats 0, 1, 2, 3."""

import argparse, binascii, struct
from dataclasses import dataclass
from typing import Literal

PIN_FORMAT = Literal["F0", "F1", "F2", "F3", "ISO0", "ISO1", "ISO2", "ISO3"]


def format0(pin: str, pan: str) -> bytes:
    """ISO9564 Format 0 — Encrypted PIN block.
    Block = 04 [4-digit PIN in BCD] [F filler] [PAN (13->1) padded]
    """
    pan13 = pan[-13:-1] if len(pan) >= 14 else pan[:-1].rjust(13, "0")
    pin_bcd = _to_bcd(pin, 4)  # 4-byte BCD for 8-char PIN
    pan_bcd = _to_bcd(pan13, 13)

    # Byte 0: 0x04 = format 0
    # Byte 1: PIN length nibble + filler 0xF
    # Bytes 2-5: PIN in BCD (4 bytes)
    # Bytes 6-13: PAN digits 13-1 (padded with 0xF)
    block = bytearray(8)
    block[0] = 0x04
    block[1] = (len(pin) << 4) | 0x0F
    # PIN in BCD (first 4 bytes) — left nibble first
    for i, nibble in enumerate(pin_bcd):
        block[2 + i // 2] |= nibble << (4 if i % 2 == 0 else 0)
    # PAN in BCD (last 14 bytes for 7 BCD pairs, padded with 0xF)
    for i, nibble in enumerate(pan_bcd[:13]):
        pos = 6 + i // 2
        if i < 12:
            block[pos] |= nibble << (4 if i % 2 == 0 else 0)
        else:
            block[pos] |= 0xF << (4 if i % 2 == 0 else 0)

    return bytes(block)


def format1(pin: str, offset: str = None) -> bytes:
    """ISO9564 Format 1 — IBM 3624 offset PIN block."""
    block = bytearray(8)
    block[0] = 0x01
    pin_bcd = _to_bcd(pin, 4)
    for i, nibble in enumerate(pin_bcd):
        block[2 + i // 2] |= nibble << (4 if i % 2 == 0 else 0)
    if offset:
        off_bcd = _to_bcd(offset, 4)
        for i, nibble in enumerate(off_bcd):
            block[2 + i // 2] |= nibble << (4 if i % 2 == 0 else 0)
    return bytes(block)


def format2(pin: str, pan: str) -> bytes:
    """ISO9564 Format 2 — Encrypted PIN block + account."""
    block = bytearray(8)
    block[0] = 0x02
    block[1] = (len(pin) << 4) | 0x0F
    pin_bcd = _to_bcd(pin, 4)
    for i, nibble in enumerate(pin_bcd):
        block[2 + i // 2] |= nibble << (4 if i % 2 == 0 else 0)
    # PAN (account suffix after last digit of card) — 12 digits in BCD
    suffix = pan[-12:]
    suffix_bcd = _to_bcd(suffix, 12)
    for i, nibble in enumerate(suffix_bcd):
        block[4 + i // 2] |= nibble << (4 if i % 2 == 0 else 0)
    block[4] = (block[4] & 0xF0) | (len(pin) & 0x0F)
    return bytes(block)


def format4(pin: str, pan: str) -> bytes:
    """ISO9564 Format 4 — VISA / Docucentrics variant."""
    block = bytearray(8)
    block[0] = 0x04
    block[1] = (len(pin) << 4) | 0x0F
    pin_bcd = _to_bcd(pin, 4)
    for i, nibble in enumerate(pin_bcd):
        block[2 + i // 2] |= nibble << (4 if i % 2 == 0 else 0)
    pan13 = pan[-13:-1]
    pan_bcd = _to_bcd(pan13, 13)
    for i, nibble in enumerate(pan_bcd):
        if i < 12:
            pos = 6 + i // 2
            block[pos] |= nibble << (4 if i % 2 == 0 else 0)
    return bytes(block)


def _to_bcd(value: str, digits: int) -> list[int]:
    """Convert string digits to list of BCD nibbles."""
    padded = value.ljust(digits, "F")
    nibbles = []
    for ch in padded[:digits]:
        nibbles.append(int(ch, 16) if ch.isdigit() else 0xF)
    return nibbles


def pin_block_to_hex(block: bytes) -> str:
    return block.hex().upper()


def hex_to_pin_block(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)


def decrypt_pin_block(block: bytes, kek: bytes) -> str:
    """Decrypt PIN block using DES-ECB (for testing only — use HSM in prod)."""
    from Crypto.Cipher import DES
    try:
        cipher = DES.new(kek, DES.MODE_ECB)
        decrypted = cipher.decrypt(block)
        pin_len = decrypted[1] >> 4
        if pin_len == 0 or pin_len > 12:
            return "INVALID"
        pin_chars = []
        for i in range(pin_len):
            byte = decrypted[2 + i // 2]
            if i % 2 == 0:
                pin_chars.append(str((byte >> 4) & 0x0F))
            else:
                pin_chars.append(str(byte & 0x0F))
        return "".join(pin_chars)
    except Exception as e:
        return f"ERROR: {e}"


def translate_pin_block(block: bytes, in_fmt: str, out_fmt: str, pan: str) -> bytes:
    """Translate PIN block between formats using PAN."""
    if in_fmt in ("F0", "ISO0"):
        pin = "PARSED_PIN"  # In real impl, decrypt first
        pass
    if out_fmt in ("F0", "ISO0"):
        return format0(pin, pan)
    elif out_fmt in ("F2", "ISO2"):
        return format2(pin, pan)
    raise ValueError(f"Unsupported format: {out_fmt}")


@dataclass
class PINBlockResult:
    pin: str
    pan: str
    format: str
    block_hex: str
    block_bytes: bytes


def calculate(pin: str, pan: str, fmt: PIN_FORMAT) -> PINBlockResult:
    fmt = fmt.upper()
    if fmt in ("F0", "ISO0"):
        block = format0(pin, pan)
    elif fmt in ("F1", "ISO1"):
        block = format1(pin, "")
    elif fmt in ("F2", "ISO2"):
        block = format2(pin, pan)
    elif fmt in ("F3", "ISO3"):
        block = format4(pin, pan)
    else:
        raise ValueError(f"Unknown PIN format: {fmt}")

    return PINBlockResult(
        pin=pin,
        pan=pan,
        format=fmt,
        block_hex=pin_block_to_hex(block),
        block_bytes=block,
    )


def main():
    parser = argparse.ArgumentParser(description="ISO9564 PIN Block Calculator")
    parser.add_argument("--pin", required=True, help="PIN (4-12 digits)")
    parser.add_argument("--pan", required=True, help="PAN or account number")
    parser.add_argument("--format", default="F0",
                        choices=["F0", "F1", "F2", "F3", "ISO0", "ISO1", "ISO2", "ISO3"],
                        help="PIN block format")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = calculate(args.pin, args.pan, args.format)

    if args.json:
        import json
        print(json.dumps({
            "pin": result.pin,
            "pan_masked": result.pan[:6] + "******" + result.pan[-4:],
            "format": result.format,
            "block_hex": result.block_hex,
        }, indent=2))
    else:
        print(f"PIN Block Calculator — ISO9564 Format {result.format}")
        print(f"PIN: {'*' * len(result.pin)}")
        print(f"PAN: {result.pan[:6]}...{result.pan[-4:]}")
        print(f"Block (hex): {result.block_hex}")
        print(f"Block (bytes): {result.block_bytes.hex()}")


if __name__ == "__main__":
    main()
