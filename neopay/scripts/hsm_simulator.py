#!/usr/bin/env python3
"""
Thales PayShield-style HSM Command Simulator
============================================
Implements a subset of PayShield commands for development/testing.
Commands: HA, HB, HC, HD, HE, GA, GB, GK, GM
Also supports ARQC generation and ARPC response generation.
Requires: pip install pycryptodome

Usage:
    python hsm_simulator.py --cmd HA --pan 4111111111111111 --pin 1234
    python hsm_simulator.py --cmd HD --key 00112233445566778899AABBCCDDEEFF --data "message"
    python hsm_simulator.py --cmd GK --key-type ZEK --key-length 16
    python hsm_simulator.py --cmd ARQC --pan 4111111111111111 --atc 0001 --atn 1234567890ABCDEF
    python hsm_simulator.py --cmd ARPC --arqc DEADBEEF01234567 --arc 3030 --isk DEADBEEF01234567DEADBEEF01234567
"""

import argparse
import binascii
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

try:
    from Crypto.Cipher import DES, DES3, AES
    from Crypto.Random import get_random_bytes
    from Crypto.Util.padding import pad, unpad
except ImportError:
    print("ERROR: pycryptodome not installed. Run: pip install pycryptodome", file=sys.stderr)
    sys.exit(1)

# ─── Key Hierarchy (Simulated LMK/ZMK/TMK/KEK) ───────────────────────────────
# In production, LMK is never exported from the HSM. Here we simulate for dev.
# Format: key encrypted under parent key (or raw for LMK which is stored in HSM)

class HSMSimulator:
    def __init__(self, lmk: str = None):
        # Simulated LMK (in production this never leaves the HSM)
        self.lmk = lmk or "0123456789ABCDEF0123456789ABCDEF"
        self.zmk = self._derive_key(self.lmk, "ZM")
        self.tmk = self._derive_key(self.lmk, "TM")
        self._key_store = {}  # name -> key bytes

    def _derive_key(self, parent_key: str, suffix: str) -> bytes:
        """Derive a child key from a parent key using key type suffix."""
        data = parent_key.encode() + suffix.encode()
        return hashlib.sha256(data).digest()[:16]

    def _pad_pin(self, pin: str) -> str:
        """Pad PIN to 4-12 digits with 'F' (ISO9564 format 0)."""
        return pin.ljust(12, 'F')

    def _check_digit(self, pan: str) -> str:
        """Calculate Luhn check digit for PAN."""
        digits = [int(c) for c in pan]
        odd_sum = sum(digits[-1::-2])
        even_sum = sum(sum(divmod(2 * d, 10)) for d in digits[-2::-2])
        return str((10 - (odd_sum + even_sum)) % 10)

    def _encrypt_3des(self, data: bytes, key: bytes) -> bytes:
        cipher = DES3.new(key, DES3.MODE_ECB)
        return cipher.encrypt(pad(data, 8))

    def _decrypt_3des(self, data: bytes, key: bytes) -> bytes:
        cipher = DES3.new(key, DES3.MODE_ECB)
        return unpad(cipher.decrypt(data), 8)

    def _encrypt_aes(self, data: bytes, key: bytes) -> bytes:
        cipher = AES.new(key, AES.MODE_ECB)
        return cipher.encrypt(pad(data, 16))

    def _decrypt_aes(self, data: bytes, key: bytes) -> bytes:
        cipher = AES.new(key, AES.MODE_ECB)
        return unpad(cipher.decrypt(data), 16)

    # ─── HA: Generate PIN under ZMK ─────────────────────────────────────────
    def cmd_HA(self, pan: str, pin: str, zmk_key: str = None) -> dict:
        """
        Generate encrypted PIN block (ISO9564-1 Format 0) under ZMK.
        PAN: Primary Account Number (16 digits)
        PIN: Clear PIN (4-6 digits)
        ZMK: Zone Master Key (32 hex chars, 3DES key)
        Returns: PIN block encrypted under ZMK
        """
        zmk = bytes.fromhex(zmk_key or self.zmk.hex())
        pin_block = self._build_pin_block_format0(pan, pin)
        encrypted = self._encrypt_3des(pin_block, zmk)
        return {
            "command": "HA",
            "pin_block_hex": pin_block.hex().upper(),
            "pin_block_format": "ISO9564-1 Format 0",
            "encrypted_pin_block_hex": encrypted.hex().upper(),
            "zmk_check": self._kcv(zmk).upper(),
        }

    def _build_pin_block_format0(self, pan: str, pin: str) -> bytes:
        """Build ISO9564-1 Format 0 PIN block: 04 + PIN + padding."""
        padded_pin = pin.ljust(12, 'F')
        block = "04" + padded_pin
        return bytes.fromhex(block)

    def _build_pin_block_format1(self, pan: str, pin: str) -> bytes:
        """Build ISO9564-1 Format 1 PIN block."""
        padded_pin = pin.ljust(12, 'F')
        # PAN in PIN block is right-justified, padded left with F
        pan_suffix = pan[-13:-1]  # last 12 chars of PAN without check digit
        block = "01" + padded_pin + pan_suffix
        return bytes.fromhex(block)

    # ─── HB: Translate PIN Block ─────────────────────────────────────────────
    def cmd_HB(self, pin_block_hex: str, in_key: str, out_key: str,
               in_format: int = 0, out_format: int = 0) -> dict:
        """
        Translate PIN block from one format/encryption key to another.
        """
        in_k = bytes.fromhex(in_key)
        out_k = bytes.fromhex(out_key)

        # Decrypt with input key
        encrypted_in = bytes.fromhex(pin_block_hex)
        pin_block = self._decrypt_3des(encrypted_in, in_k)

        # Re-encrypt with output key
        encrypted_out = self._encrypt_3des(pin_block, out_k)
        return {
            "command": "HB",
            "input_format": f"ISO9564-1 Format {in_format}",
            "output_format": f"ISO9564-1 Format {out_format}",
            "input_pin_block_hex": pin_block_hex.upper(),
            "output_pin_block_hex": encrypted_out.hex().upper(),
            "output_key_check": self._kcv(out_k).upper(),
        }

    # ─── HC: Verify PIN ──────────────────────────────────────────────────────
    def cmd_HC(self, pan: str, pin: str, encrypted_pin_block_hex: str,
               zmk_key: str = None) -> dict:
        """
        Verify a PIN against an encrypted PIN block.
        """
        zmk = bytes.fromhex(zmk_key or self.zmk.hex())
        stored = bytes.fromhex(encrypted_pin_block_hex)

        # Decrypt stored PIN block
        decrypted = self._decrypt_3des(stored, zmk)
        stored_pin = decrypted[:2] == b'\x04\x'

        # Build expected PIN block
        expected = self._build_pin_block_format0(pan, pin)

        # Compare
        match = (decrypted[:8] == expected[:8])
        return {
            "command": "HC",
            "verified": match,
            "status": "00 (OK)" if match else "PASS (Fail - simulated)",
            "note": "In production, HSM returns only pass/fail, never decrypted PIN",
        }

    # ─── HD: Generate MAC (ISO9797-1 M1) ────────────────────────────────────
    def cmd_HD(self, key: str, data: str) -> dict:
        """
        Generate MAC using ISO9797-1 Algorithm M1 (DES CBC MAC, padding method 2).
        """
        k = bytes.fromhex(key)
        if len(k) == 16:
            k = DES3.adjust_key_parity(k)

        data_bytes = bytes.fromhex(data) if all(c in '0123456789ABCDEFabcdef' for c in data) else data.encode()

        # Padding method 2: append 0x80, then zeros to 8-byte boundary
        block_size = 8
        if isinstance(data_bytes, str):
            data_bytes = data_bytes.encode()
        padded = data_bytes + b'\x80' + b'\x00' * ((block_size - len(data_bytes) - 1) % block_size)

        # CBC MAC
        iv = b'\x00' * 8
        cipher = DES.new(k[:8], DES.MODE_CBC, iv)
        mac = cipher.encrypt(padded)[-8:]
        return {
            "command": "HD",
            "algorithm": "ISO9797-1 M1 (DES CBC MAC, padding method 2)",
            "data_hex": data_bytes.hex().upper(),
            "mac_hex": mac.hex().upper(),
            "mac_6_hex": mac[:3].hex().upper(),  # 6-char key check value
        }

    # ─── HE: Verify MAC ─────────────────────────────────────────────────────
    def cmd_HE(self, key: str, data: str, mac: str) -> dict:
        """Verify a MAC."""
        gen = self.cmd_HD(key, data)
        match = gen["mac_hex"].upper() == mac.upper()
        return {
            "command": "HE",
            "verified": match,
            "status": "MAC OK" if match else "MAC FAIL",
            "expected": gen["mac_hex"].upper(),
            "received": mac.upper(),
        }

    # ─── GA: Encrypt Data ───────────────────────────────────────────────────
    def cmd_GA(self, key: str, data: str, algorithm: str = "3DES") -> dict:
        """Encrypt arbitrary data."""
        k = bytes.fromhex(key)
        d = bytes.fromhex(data)
        if algorithm == "3DES":
            if len(k) == 16:
                k = DES3.adjust_key_parity(k)
            encrypted = self._encrypt_3des(d, k)
        elif algorithm == "AES":
            if len(k) == 16:
                k = bytes.fromhex(key)
            encrypted = self._encrypt_aes(d, k)
        else:
            return {"error": f"Unknown algorithm: {algorithm}"}
        return {
            "command": "GA",
            "algorithm": algorithm,
            "input_hex": data.upper(),
            "output_hex": encrypted.hex().upper(),
        }

    # ─── GB: Decrypt Data ───────────────────────────────────────────────────
    def cmd_GB(self, key: str, data: str, algorithm: str = "3DES") -> dict:
        """Decrypt arbitrary data."""
        k = bytes.fromhex(key)
        d = bytes.fromhex(data)
        if algorithm == "3DES":
            if len(k) == 16:
                k = DES3.adjust_key_parity(k)
            decrypted = self._decrypt_3des(d, k)
        elif algorithm == "AES":
            decrypted = self._decrypt_aes(d, k)
        else:
            return {"error": f"Unknown algorithm: {algorithm}"}
        return {
            "command": "GB",
            "algorithm": algorithm,
            "input_hex": data.upper(),
            "output_hex": decrypted.hex().upper(),
        }

    # ─── GK: Generate Key ───────────────────────────────────────────────────
    def cmd_GK(self, key_type: str = "ZEK", key_length: int = 16) -> dict:
        """
        Generate a random DES/3DES/AES key with KCV.
        Key types: ZEK (Zone Key), TEK (Terminal Key), KEK (Key Encrypting Key)
        """
        if key_length == 8:
            key = get_random_bytes(8)
            key = DES3.adjust_key_parity(key)
        elif key_length == 16:
            key = get_random_bytes(16)
            key = DES3.adjust_key_parity(key)
        elif key_length == 32:
            key = get_random_bytes(32)
        else:
            return {"error": "Key length must be 8, 16, or 32 bytes"}

        kcv = self._kcv(key)
        return {
            "command": "GK",
            "key_type": key_type,
            "key_length_bytes": key_length,
            "key_hex": key.hex().upper(),
            "kcv_3char_hex": kcv.upper(),
            "algorithm": "3DES" if key_length <= 16 else "AES-256",
        }

    def _kcv(self, key: bytes) -> str:
        """Key Check Value: encrypt 8 zeros under the key, take first 3 bytes."""
        cipher = DES.new(key[:8], DES.MODE_ECB)
        return cipher.encrypt(b'\x00' * 8)[:3].hex()

    # ─── GM: Key Check ───────────────────────────────────────────────────────
    def cmd_GM(self, key_hex: str) -> dict:
        """Calculate KCV for a key."""
        k = bytes.fromhex(key_hex)
        return {
            "command": "GM",
            "key_hex": key_hex.upper(),
            "kcv_3char_hex": self._kcv(k).upper(),
        }

    # ─── ARQC: Authorization Request Cryptogram ─────────────────────────────
    def cmd_ARQC(self, pan: str, atc: str, atn: str,
                 ipk_hex: str = None) -> dict:
        """
        Generate ARQC (Authorization Request Cryptogram).
        Simplified: HMAC-SHA256(PAN || ATC || ATN) under issuer key.
        In production: Uses Derive Key (EMV) + 3DES + unpredictable number.
        """
        # In production, ipk would be the issuer master key derived key
        ipk = bytes.fromhex(ipk_hex or self._derive_key(self.lmk, "AR").hex()[:32])

        # Pad/format inputs
        pan_bytes = pan.rjust(16, '0').encode()
        atc_bytes = atc.rjust(6, '0').encode()
        atn_bytes = atn.rjust(32, '0').encode()

        # Build cryptogram data
        data = pan_bytes + atc_bytes + atn_bytes

        # Simplified ARQC (production uses 3DES)
        mac_gen = hmac.new(ipk, data, hashlib.sha256)
        arqc_full = mac_gen.digest()
        arqc = arqc_full[:8].hex().upper()

        return {
            "command": "ARQC",
            "pan": pan,
            "atc": atc,
            "unpredictable_number": atn,
            "arqc_hex": arqc,
            "arqc_full_sha256": arqc_full.hex().upper(),
            "note": "This is a simplified HMAC-SHA256 ARQC. Production EMV uses 3DES-CBC with derived session key.",
        }

    # ─── ARPC: Authorization Response Cryptogram ─────────────────────────────
    def cmd_ARPC(self, arqc_hex: str, response_code: str,
                 issuer_key_hex: str = None) -> dict:
        """
        Generate ARPC (Authorization Response Cryptogram).
        ARPC = first 8 bytes of HMAC-SHA256(ARQC || RC || 0x8000...) under issuer key.
        """
        isk = bytes.fromhex(issuer_key_hex or self._derive_key(self.lmk, "AR").hex()[:32])
        arqc = bytes.fromhex(arqc_hex)
        rc = bytes.fromhex(response_code)
        pad_data = b'\x80' + b'\x00' * 7

        data = arqc + rc + pad_data
        mac_gen = hmac.new(isk, data, hashlib.sha256)
        arpc = mac_gen.digest()[:8].hex().upper()

        return {
            "command": "ARPC",
            "input_arqc": arqc_hex.upper(),
            "response_code": response_code.upper(),
            "arpc_hex": arpc,
            "note": "ARPC generation per EMV Book 2. Use RC='3030' for approved.",
        }

    # ─── CVV Generation ─────────────────────────────────────────────────────
    def cmd_CVV(self, pan: str, exp: str, svv: str = None) -> dict:
        """
        Generate CVV (Card Verification Value).
        CVV = Visa, CVV2 = checks only, iCVV = EMV.
        """
        service_code = "000"  # Default
        key = b'\x00' * 16  # In production: CVK-A/CVK-B pair
        padded = (pan + exp + service_code).encode()
        mac_gen = hmac.new(key, padded, hashlib.sha256)
        cvv_raw = mac_gen.digest()
        cvv = f"{cvv_raw[0]:02d}{cvv_raw[1]:02d}{cvv_raw[2]:02d}"
        return {
            "command": "CVV",
            "pan": pan,
            "expiry": exp,
            "cvv": cvv,
            "cvv2": cvv[:3],  # Same for Visa-style
            "note": "Use CVK-A/CVK-B key pair in production",
        }

    # ─── CVV2 Verify ─────────────────────────────────────────────────────────
    def cmd_CVV2_VERIFY(self, pan: str, exp: str, cvv2: str) -> dict:
        """Verify a CVV2 value provided by cardholder."""
        gen = self.cmd_CVV(pan, exp)
        match = gen["cvv2"] == cvv2
        return {
            "command": "CVV2_VERIFY",
            "verified": match,
            "status": "OK" if match else "FAIL",
        }


# ─── CLI Interface ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="HSM Simulator (PayShield-style commands)")
    parser.add_argument("--cmd", required=True,
                        help="Command: HA, HB, HC, HD, HE, GA, GB, GK, GM, ARQC, ARPC, CVV, CVV2_VERIFY")
    parser.add_argument("--pan", help="Primary Account Number (16 digits)")
    parser.add_argument("--pin", help="Clear PIN (4-6 digits)")
    parser.add_argument("--pin-block", dest="pin_block", help="Encrypted PIN block hex")
    parser.add_argument("--zmk-key", dest="zmk_key", help="ZMK hex key (32 chars for 3DES)")
    parser.add_argument("--in-key", dest="in_key", help="Input encryption key hex")
    parser.add_argument("--out-key", dest="out_key", help="Output encryption key hex")
    parser.add_argument("--in-format", dest="in_format", type=int, default=0, help="Input PIN block format")
    parser.add_argument("--out-format", dest="out_format", type=int, default=0, help="Output PIN block format")
    parser.add_argument("--key", dest="key", help="Encryption key hex")
    parser.add_argument("--data", help="Data to MAC/encrypt/decrypt (hex or string)")
    parser.add_argument("--algorithm", default="3DES", help="Algorithm: 3DES or AES")
    parser.add_argument("--mac", dest="mac", help="MAC value to verify")
    parser.add_argument("--key-type", dest="key_type", default="ZEK", help="Key type for GK")
    parser.add_argument("--key-length", dest="key_length", type=int, default=16, help="Key length in bytes")
    parser.add_argument("--atc", help="Application Transaction Counter (for ARQC)")
    parser.add_argument("--atn", dest="atn", help="Unpredictable Number (for ARQC)")
    parser.add_argument("--ipk-hex", dest="ipk_hex", help="Issuer Provisioing Key hex (for ARQC)")
    parser.add_argument("--arqc", help="ARQC hex (for ARPC)")
    parser.add_argument("--arc", dest="arc", default="3030", help="Authorization Response Code hex (for ARPC)")
    parser.add_argument("--issuer-key", dest="issuer_key", help="Issuer key hex (for ARPC)")
    parser.add_argument("--exp", help="Expiry date MMYY (for CVV)")
    parser.add_argument("--cvv2", dest="cvv2", help="CVV2 value to verify")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--lmk", default=None, help="LMK hex (for simulation only, never in production)")

    args = parser.parse_args()
    hsm = HSMSimulator(lmk=args.lmk)

    result = None
    cmd = args.cmd.upper()

    try:
        if cmd == "HA":
            if not args.pan or not args.pin:
                print("ERROR: --pan and --pin required for HA", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_HA(args.pan, args.pin, args.zmk_key)

        elif cmd == "HB":
            if not args.pin_block or not args.in_key or not args.out_key:
                print("ERROR: --pin-block, --in-key, --out-key required for HB", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_HB(args.pin_block, args.in_key, args.out_key,
                                args.in_format, args.out_format)

        elif cmd == "HC":
            if not args.pan or not args.pin or not args.pin_block:
                print("ERROR: --pan, --pin, --pin-block required for HC", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_HC(args.pan, args.pin, args.pin_block, args.zmk_key)

        elif cmd == "HD":
            if not args.key or not args.data:
                print("ERROR: --key and --data required for HD", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_HD(args.key, args.data)

        elif cmd == "HE":
            if not args.key or not args.data or not args.mac:
                print("ERROR: --key, --data, --mac required for HE", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_HE(args.key, args.data, args.mac)

        elif cmd == "GA":
            if not args.key or not args.data:
                print("ERROR: --key and --data required for GA", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_GA(args.key, args.data, args.algorithm)

        elif cmd == "GB":
            if not args.key or not args.data:
                print("ERROR: --key and --data required for GB", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_GB(args.key, args.data, args.algorithm)

        elif cmd == "GK":
            result = hsm.cmd_GK(args.key_type, args.key_length)

        elif cmd == "GM":
            if not args.key:
                print("ERROR: --key required for GM", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_GM(args.key)

        elif cmd == "ARQC":
            if not args.pan or not args.atc or not args.atn:
                print("ERROR: --pan, --atc, --atn required for ARQC", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_ARQC(args.pan, args.atc, args.atn, args.ipk_hex)

        elif cmd == "ARPC":
            if not args.arqc or not args.arc:
                print("ERROR: --arqc and --arc required for ARPC", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_ARPC(args.arqc, args.arc, args.issuer_key)

        elif cmd == "CVV":
            if not args.pan or not args.exp:
                print("ERROR: --pan and --exp required for CVV", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_CVV(args.pan, args.exp)

        elif cmd == "CVV2_VERIFY":
            if not args.pan or not args.exp or not args.cvv2:
                print("ERROR: --pan, --exp, --cvv2 required for CVV2_VERIFY", file=sys.stderr)
                sys.exit(1)
            result = hsm.cmd_CVV2_VERIFY(args.pan, args.exp, args.cvv2)

        else:
            print(f"ERROR: Unknown command: {args.cmd}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"  HSM Command: {result.pop('command', args.cmd)}")
            print(f"{'='*60}")
            for k, v in result.items():
                print(f"  {k:<30} : {v}")
            print(f"{'='*60}\n")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
