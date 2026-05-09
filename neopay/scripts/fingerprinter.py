#!/usr/bin/env python3
"""ISO8583 dialect fingerprinter - detects HISO93 vs HISO87 vs custom formats."""

import re
import sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class Dialect(Enum):
    HISO93_BINARY = "HISO93 Binary"
    HISO93_ASCII = "HISO93 ASCII"
    HISO87_BINARY = "HISO87 Binary"
    HISO87_ASCII = "HISO87 ASCII"
    VISA_BASE1 = "Visa BASE I"
    MASTERCARD_3600 = "MasterCard 3600"
    CUSTOM = "Custom/Unknown"


class BitmapFormat(Enum):
    BINARY = "Binary (64 or 128 bytes)"
    HEX_ASCII = "Hex ASCII (128 or 256 chars)"
    BCD = "BCD (32 or 64 bytes)"


@dataclass
class DialectAnalysis:
    dialect: Dialect
    confidence: float
    mti_version: str
    bitmap_format: BitmapFormat
    is_binary: bool
    is_ascii: bool
    has_length_prefix: bool
    primary_bitmap: str
    secondary_bitmap: Optional[str]
    card_type: Optional[str]
    card_name: str
    notes: List[str]


# Card range definitions
CARD_RANGES = [
    (r"^4[0-9]{12,15}$", "Visa", 4, "4"),
    (r"^5[1-5][0-9]{14}$", "MasterCard", 51, "51-55"),
    (r"^34[0-9]{13}$", "American Express", 34, "34"),
    (r"^37[0-9]{13}$", "American Express", 37, "37"),
    (r"^6011[0-9]{12}$", "Discover", 6011, "6011"),
    (r"^64[4-9][0-9]{13}$", "Discover", 64, "644-649"),
    (r"^65[0-9]{14}$", "Discover", 65, "65"),
    (r"^36[0-9]{12}$", "Diners Club", 36, "36"),
    (r"^38[0-9]{12}$", "Diners Club", 38, "38"),
    (r"^352[0-9]{13}$", "JCB", 352, "3520-3589"),
    (r"^353[0-9]{13}$", "JCB", 353, "3530-3589"),
    (r"^354[0-9]{13}$", "JCB", 354, "3540-3589"),
    (r"^355[0-9]{13}$", "JCB", 355, "3550-3589"),
    (r"^356[0-9]{13}$", "JCB", 356, "3560-3589"),
    (r"^357[0-9]{13}$", "JCB", 357, "3570-3589"),
    (r"^358[0-9]{13}$", "JCB", 358, "3580-3589"),
    (r"^62[0-9]{14,17}$", "UnionPay", 62, "62"),
]


def classify_card(pan: str) -> Tuple[Optional[str], str]:
    """Classify card type from PAN."""
    clean_pan = re.sub(r'[^0-9]', '', pan)
    for pattern, name, iin, bin_range in CARD_RANGES:
        if re.match(pattern, clean_pan):
            return name, bin_range
    return None, "Unknown"


def hex_to_bytes(hex_str: str) -> bytes:
    """Convert hex string to bytes."""
    hex_str = hex_str.replace(" ", "").replace(":", "")
    return bytes.fromhex(hex_str)


def analyze_mti(raw_mti: str, is_binary: bool) -> Dict:
    """Analyze Message Type Indicator."""
    if is_binary:
        if len(raw_mti) >= 2:
            mti_bytes = raw_mti[:2] if isinstance(raw_mti, bytes) else bytes.fromhex(raw_mti[:4])
            mti_val = int.from_bytes(mti_bytes, 'big')
        else:
            mti_val = 0
    else:
        mti_val = int(raw_mti[:4])

    mti_str = str(mti_val).zfill(4)
    version = mti_str[0]
    mti_class = mti_str[1]
    mti_function = mti_str[2]
    mti_origin = mti_str[3]

    version_map = {
        "0": "ISO/IEC 8583-1:1993",
        "1": "HISO93 (MasterCard)",
        "2": "HISO87 (Visa)",
        "3": "Extended",
    }
    class_map = {
        "0": "Authorization",
        "1": "Financial",
        "2": "File Actions",
        "3": "Reversal/Admin",
        "4": "Reconciliation",
        "5": "Network Management",
        "6": "Reserved",
        "7": "Reserved",
        "8": "Reserved",
        "9": "Internal/Testing",
    }
    function_map = {
        "0": "Request",
        "1": "Request Response",
        "2": "Advice",
        "3": "Advice Response",
        "4": "Notification",
        "5": "Notification Acknowledgment",
        "6": "Instruction",
        "7": "Instruction Acknowledgment",
        "8": "Reserved",
        "9": "Response",
    }

    return {
        "mti": mti_str,
        "version": version,
        "version_name": version_map.get(version, "Unknown"),
        "class": mti_class,
        "class_name": class_map.get(mti_class, "Unknown"),
        "function": mti_function,
        "function_name": function_map.get(mti_function, "Unknown"),
    }


def detect_bitmap_format(data: bytes) -> Tuple[BitmapFormat, int, Optional[bytes]]:
    """Detect bitmap format and return format, primary bitmap, and secondary bitmap."""
    if len(data) < 8:
        return BitmapFormat.HEX_ASCII, 0, None

    primary = data[:8]

    if all(b in (0, 1) for b in primary):
        return BitmapFormat.BINARY, 64, primary

    if (48 <= primary[0] <= 57) or (65 <= primary[0] <= 70):
        hex_str = primary.decode('ascii', errors='ignore')
        try:
            int(hex_str, 16)
            if primary[7] & 0x80:
                secondary = data[8:16] if len(data) >= 16 else None
                return BitmapFormat.HEX_ASCII, 128, secondary
            return BitmapFormat.HEX_ASCII, 64, None
        except ValueError:
            pass

    return BitmapFormat.BINARY, 64, primary


def detect_dialect(data: bytes) -> DialectAnalysis:
    """Detect ISO8583 dialect from raw message data."""
    notes = []
    data_len = len(data)

    if data_len < 4:
        return DialectAnalysis(
            dialect=Dialect.CUSTOM,
            confidence=0.0,
            mti_version="Unknown",
            bitmap_format=BitmapFormat.HEX_ASCII,
            is_binary=False,
            is_ascii=False,
            has_length_prefix=False,
            primary_bitmap="",
            secondary_bitmap=None,
            card_type=None,
            card_name="Unknown",
            notes=["Message too short to analyze"],
        )

    is_ascii = False
    is_binary = False
    has_length_prefix = False
    offset = 0

    sample = data[:20]
    if all(0x20 <= b < 0x7F or b in (0x0A, 0x0D, 0x09) for b in sample):
        is_ascii = True
    elif all(b < 0x80 for b in sample):
        is_binary = True

    if is_ascii:
        try:
            prefix_len = int(data[:4].decode('ascii'))
            if 4 < prefix_len < data_len and prefix_len > 10:
                has_length_prefix = True
                offset = 4
        except (ValueError, UnicodeDecodeError):
            pass

    mti_data = data[offset:offset + 4]
    if is_binary and len(data) >= offset + 2:
        mti_analysis = analyze_mti(data[offset:offset + 2], True)
    else:
        mti_analysis = analyze_mti(mti_data, False)

    offset += 4 if is_ascii else 2
    bitmap_format, bitmap_bits, secondary = detect_bitmap_format(data[offset:])

    bitmap_hex = data[offset:offset + 8].hex() if is_binary else data[offset:offset + 16].decode('ascii', errors='replace')

    dialect = Dialect.CUSTOM
    confidence = 0.5

    if mti_analysis["version"] == "1" and is_binary:
        dialect = Dialect.HISO93_BINARY
        confidence = 0.9
        notes.append("HISO93 binary format detected (MasterCard-style)")
    elif mti_analysis["version"] == "1" and is_ascii:
        dialect = Dialect.HISO93_ASCII
        confidence = 0.9
        notes.append("HISO93 ASCII format detected (MasterCard-style)")
    elif mti_analysis["version"] == "2" and is_binary:
        dialect = Dialect.HISO87_BINARY
        confidence = 0.9
        notes.append("HISO87 binary format detected (Visa-style)")
    elif mti_analysis["version"] == "2" and is_ascii:
        dialect = Dialect.HISO87_ASCII
        confidence = 0.9
        notes.append("HISO87 ASCII format detected (Visa-style)")
    elif mti_analysis["mti"].startswith("0") and is_binary:
        dialect = Dialect.HISO93_BINARY
        confidence = 0.7
        notes.append("ISO8583-1993 binary format (default assumption)")
    elif mti_analysis["mti"].startswith("0") and is_ascii:
        dialect = Dialect.HISO93_ASCII
        confidence = 0.7
        notes.append("ISO8583-1993 ASCII format (default assumption)")

    if has_length_prefix:
        notes.append("ASCII length prefix detected (4 bytes)")

    if bitmap_bits > 64:
        notes.append("Extended bitmap (128 bits) detected")

    card_type = None
    card_name = "Unknown"

    return DialectAnalysis(
        dialect=dialect,
        confidence=confidence,
        mti_version=mti_analysis["version_name"],
        bitmap_format=bitmap_format,
        is_binary=is_binary,
        is_ascii=is_ascii,
        has_length_prefix=has_length_prefix,
        primary_bitmap=bitmap_hex,
        secondary_bitmap=secondary.hex() if secondary else None,
        card_type=card_type,
        card_name=card_name,
        notes=notes,
    )


def print_analysis(analysis: DialectAnalysis, mti_info: Dict = None):
    """Print dialect analysis results."""
    print("\n" + "=" * 60)
    print("ISO8583 DIALECT ANALYSIS")
    print("=" * 60)

    print(f"\nDialect Detected: {analysis.dialect.value}")
    print(f"Confidence: {analysis.confidence * 100:.0f}%")

    print(f"\n--- Format Characteristics ---")
    print(f"Encoding: {'Binary' if analysis.is_binary else 'ASCII' if analysis.is_ascii else 'Unknown'}")
    print(f"Bitmap Format: {analysis.bitmap_format.value}")
    print(f"Length Prefix: {'Yes' if analysis.has_length_prefix else 'No'}")
    print(f"MTI Version: {analysis.mti_version}")

    if mti_info:
        print(f"\n--- MTI Analysis ---")
        print(f"MTI: {mti_info.get('mti', 'N/A')}")
        print(f"Class: {mti_info.get('class_name', 'N/A')}")
        print(f"Function: {mti_info.get('function_name', 'N/A')}")

    print(f"\n--- Bitmap ---")
    print(f"Primary: {analysis.primary_bitmap}")
    if analysis.secondary_bitmap:
        print(f"Secondary: {analysis.secondary_bitmap}")

    if analysis.card_name != "Unknown":
        print(f"\n--- Card Classification ---")
        print(f"Card Type: {analysis.card_name}")

    if analysis.notes:
        print(f"\n--- Notes ---")
        for note in analysis.notes:
            print(f"  * {note}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: fingerprinter.py <hex_message>")
        print("   or: echo <hex> | fingerprinter.py -")
        sys.exit(1)

    if sys.argv[1] == "-":
        data = sys.stdin.read().strip()
    else:
        data = sys.argv[1]

    data = data.replace(" ", "").replace(":", "").replace("\n", "")

    try:
        raw_bytes = bytes.fromhex(data)
    except ValueError:
        print("Error: Invalid hex data")
        sys.exit(1)

    analysis = detect_dialect(raw_bytes)

    offset = 0
    if analysis.has_length_prefix:
        offset = 4
    is_binary = analysis.is_binary
    mti_bytes = raw_bytes[offset:offset + 2] if is_binary else raw_bytes[offset:offset + 4]
    mti_info = analyze_mti(mti_bytes, is_binary)

    print_analysis(analysis, mti_info)

    return analysis


if __name__ == "__main__":
    main()