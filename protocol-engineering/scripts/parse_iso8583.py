#!/usr/bin/env python3
"""ISO8583 HISO93 parser — binary and ASCII dialects."""

import json, struct, argparse, sys
from dataclasses import dataclass, field
from typing import Optional

MTI_NAMES = {
    "0100": "Authorization Request",
    "0110": "Authorization Advice",
    "0120": "Authorization Response",
    "0130": "Authorization Notification",
    "0200": "Financial Transaction Request",
    "0210": "Financial Advice",
    "0220": "Financial Response",
    "0230": "Financial Notification",
    "0400": "Reversal Request",
    "0420": "Reversal Response",
    "0800": "Network Management Request",
    "0810": "Network Management Response",
    "0850": "Network Management Advice",
    "0802": "Cut-Through",
    "0804": "Key Exchange",
}

HISO93_FIELDS = {
    2: ("PAN", "LL", 19),
    3: ("Processing Code", "N", 6),
    4: ("Transaction Amount", "N", 12),
    5: ("Settlement Amount", "N", 12),
    6: ("Cardholder Billing Amount", "N", 12),
    7: ("Transmission Date/Time", "N", 10),
    11: ("STAN", "N", 6),
    12: ("Time, Local Transaction", "N", 6),
    13: ("Date, Local Transaction", "N", 4),
    14: ("Date, Expiration", "N", 4),
    15: ("Date, Settlement", "N", 4),
    18: ("Merchant Type (MCC)", "N", 4),
    22: ("POS Entry Mode", "N", 3),
    24: ("Function Code", "N", 3),
    25: ("Message Reason Code", "N", 2),
    32: ("Acquiring Institution ID", "LL", 11),
    33: ("Forwarding Institution ID", "LL", 11),
    35: ("Track 2 Data", "LL", 37),
    37: ("Retrieval Reference Number", "AN", 12),
    38: ("Authorization ID Response", "AN", 6),
    39: ("Response Code", "A", 2),
    41: ("Terminal ID", "ANS", 8),
    42: ("Card Acceptor ID", "ANS", 15),
    43: ("Card Acceptor Name/Location", "ANS", 40),
    48: ("Additional Data (Private)", "LLL", 999),
    49: ("Currency Code", "A", 3),
    52: ("PIN Block", "BINARY", 8),
    53: ("Security Control Info", "N", 16),
    54: ("Additional Amounts", "LL", 120),
    55: ("ICC Data (EMV)", "LLL", 255),
    57: ("Settlement Category Code", "N", 3),
    60: ("Transaction Life Cycle ID", "AN", 24),
    61: ("POS Data Code", "AN", 12),
    62: ("POS Environment Data", "AN", 24),
    63: ("Acquirer Currency Code", "A", 3),
    64: ("MAC", "BINARY", 8),
    70: ("Date, Action", "N", 4),
    90: ("Original Data Elements", "AN", 42),
    100: ("Receiving Institution ID", "LL", 11),
    102: ("From Account", "LL", 28),
    103: ("To Account", "LL", 28),
    128: ("MAC (Extended)", "BINARY", 8),
}

RESPONSE_CODES = {
    "00": "Approved",
    "01": "Refer to card issuer",
    "04": "Pick-up card",
    "05": "Do not honor",
    "06": "General error",
    "08": "Honor with ID",
    "10": "Partial approval",
    "11": "VIP approval",
    "12": "Invalid transaction",
    "13": "Invalid amount",
    "14": "Invalid card number",
    "15": "No such issuer",
    "19": "Re-enter transaction",
    "21": "No action taken",
    "30": "Message format error",
    "91": "Issuer unavailable",
    "96": "Switch error",
}


@dataclass
class ISO8583Message:
    raw_bytes: bytes = field(default_factory=bytes)
    mti: str = ""
    primary_bitmap: bytes = field(default_factory=bytes)
    secondary_bitmap: Optional[bytes] = None
    fields: dict = field(default_factory=dict)
    dialect: str = "binary"

    def __repr__(self):
        mti_name = MTI_NAMES.get(self.mti, "Unknown")
        return f"ISO8583[{self.mti}] {mti_name} — {len(self.fields)} fields"


def parse_bitmap(data: bytes, dialect: str) -> tuple[bytes, list[int]]:
    """Parse 8-byte primary bitmap and return list of present field numbers."""
    present = []
    for byte_pos, byte_val in enumerate(data):
        for bit in range(8):
            field_num = byte_pos * 8 + bit + 1
            if byte_val & (0x80 >> bit):
                present.append(field_num)
    return data, present


def read_ll(data: bytes, offset: int) -> tuple[bytes, int, int]:
    """Read LL (2-digit length) variable field. Returns (value, new_offset, length)."""
    length = int(data[offset:offset + 2])
    value = data[offset + 2:offset + 2 + length]
    return value, offset + 2 + length, length


def read_lll(data: bytes, offset: int) -> tuple[bytes, int, int]:
    """Read LLL (3-digit length) variable field."""
    length = int(data[offset:offset + 3])
    value = data[offset + 3:offset + 3 + length]
    return value, offset + 3 + length, length


def parse_message(data: bytes, dialect: str = "binary") -> ISO8583Message:
    """Parse raw bytes into an ISO8583Message object."""
    msg = ISO8583Message(raw_bytes=data, dialect=dialect)
    offset = 0

    # MTI: 4 bytes
    if dialect == "binary":
        msg.mti = data[0:2].hex().upper()
        offset = 2
    else:  # ASCII
        msg.mti = data[0:4].decode("ascii")
        offset = 4

    # Primary bitmap: 8 bytes
    bitmap = data[offset:offset + 8]
    offset += 8

    primary_present = []
    for byte_pos, byte_val in enumerate(bitmap):
        for bit in range(8):
            field_num = byte_pos * 8 + bit + 1
            if byte_val & (0x80 >> bit):
                primary_present.append(field_num)

    # Check for secondary bitmap (field 1)
    if 1 in primary_present:
        bitmap2 = data[offset:offset + 8]
        offset += 8
        msg.secondary_bitmap = bitmap2
        for byte_pos, byte_val in enumerate(bitmap2):
            for bit in range(8):
                field_num = 64 + byte_pos * 8 + bit + 1
                if byte_val & (0x80 >> bit):
                    primary_present.append(field_num)

    msg.primary_bitmap = bitmap

    # Parse fields
    for field_num in sorted(primary_present):
        if field_num in HISO93_FIELDS:
            name, fmt, max_len = HISO93_FIELDS[field_num]
            try:
                if fmt == "N" or fmt == "AN" or fmt == "A":
                    length = max_len
                    value = data[offset:offset + length]
                    if dialect == "ascii":
                        value = value.decode("ascii")
                    offset += length
                elif fmt == "LL":
                    value, offset, _ = read_ll(data, offset)
                    if dialect == "ascii":
                        value = value.decode("ascii")
                elif fmt == "LLL":
                    value, offset, _ = read_lll(data, offset)
                    if dialect == "ascii":
                        value = value.decode("ascii")
                elif fmt == "LLL":
                    value, offset, _ = read_ll(data, offset)
                    if dialect == "ascii":
                        value = value.decode("ascii")
                elif fmt == "BINARY":
                    value = data[offset:offset + max_len]
                    offset += max_len
                elif fmt == "ANS":
                    length = max_len
                    value = data[offset:offset + length]
                    if dialect == "ascii":
                        value = value.decode("ascii")
                    offset += length
                else:
                    value = data[offset:offset + max_len]
                    offset += max_len

                msg.fields[field_num] = {"name": name, "value": value, "format": fmt}
            except Exception as e:
                msg.fields[field_num] = {"name": name, "error": str(e)}
        else:
            msg.fields[field_num] = {"name": f"Field {field_num}", "value": data[offset:offset + 8]}
            offset += 8

    return msg


def parse_ascii_message(data: bytes) -> ISO8583Message:
    return parse_message(data, dialect="ascii")


def parse_binary_message(data: bytes) -> ISO8583Message:
    return parse_message(data, dialect="binary")


def build_bitmap(fields: list[int], dialect: str = "binary") -> bytes:
    """Build 8-byte primary bitmap from list of field numbers."""
    bitmap = bytearray(8)
    for f in fields:
        if f > 64:
            continue
        byte_pos = (f - 1) // 8
        bit_pos = (f - 1) % 8
        bitmap[byte_pos] |= 0x80 >> bit_pos
    return bytes(bitmap)


def mti_info(mti: str) -> dict:
    return {
        "mti": mti,
        "name": MTI_NAMES.get(mti, "Unknown"),
        "is_request": mti[0] in ("0", "1", "2", "4"),
        "is_response": mti[0] in ("2", "3", "4"),
    }


def format_message(msg: ISO8583Message) -> str:
    lines = [f"ISO8583 Message — MTI: {msg.mti} ({MTI_NAMES.get(msg.mti, 'Unknown')})"]
    lines.append(f"Dialect: {msg.dialect}")
    lines.append(f"Fields: {len(msg.fields)}")
    for fn, fd in sorted(msg.fields.items()):
        name = fd.get("name", f"Field {fn}")
        val = fd.get("value", fd.get("error", "N/A"))
        if fn == 52:  # PIN block — show as hex
            val = f"<BINARY {len(val)} bytes>"
        elif fn == 64 or fn == 128:  # MAC — show as hex
            val = f"<BINARY {len(val)} bytes>"
        elif fn == 55:  # EMV data — show first 64 chars
            val = f"<ICC DATA {len(val)} bytes>"
        lines.append(f"  [{fn:03d}] {name}: {val}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="ISO8583 HISO93 Parser")
    parser.add_argument("input", help="Input file or hex string")
    parser.add_argument("--dialect", choices=["binary", "ascii"], default="binary", help="Dialect")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--hex", help="Parse hex string directly")
    args = parser.parse_args()

    if args.hex:
        data = bytes.fromhex(args.hex.replace(" ", ""))
    else:
        with open(args.input, "rb") as f:
            data = f.read()

    msg = parse_message(data, dialect=args.dialect)

    if args.json:
        output = {
            "mti": msg.mti,
            "mti_name": MTI_NAMES.get(msg.mti, "Unknown"),
            "fields": {str(k): v for k, v in msg.fields.items()},
            "dialect": msg.dialect,
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_message(msg))


if __name__ == "__main__":
    main()
