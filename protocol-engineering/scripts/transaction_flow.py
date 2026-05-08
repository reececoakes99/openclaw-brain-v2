#!/usr/bin/env python3
"""
End-to-End Transaction Flow Orchestrator
Builds complete ISO8583 messages for each flow step.
Shows state transitions, handles timeout/retry logic.
"""
import argparse, json, random, sys, time, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from enum import Enum

# ─── Constants ────────────────────────────────────────────────────────────────
CARD_NETWORKS = {"VISA": "4", "MC": "5", "AMEX": "3", "DISCOVER": "6", "UNIONPAY": "62"}
RESPONSE_CODES = {
    "00": "Approved", "01": "Refer to issuer", "05": "Do not honor",
    "14": "Invalid PAN", "41": "Lost card", "51": "Insufficient funds",
    "54": "Expired card", "63": "Security violation", "91": "Issuer unavailable"
}

# ─── DE Definitions (simplified - see references/iso8583.md for full dict) ──
DE = {
    2:  {"name": "Primary Account Number", "len_type": "LLVAR", "max": 19},
    3:  {"name": "Processing Code", "len_type": "FIXED", "max": 6},
    4:  {"name": "Amount, Transaction", "len_type": "FIXED", "max": 12},
    7:  {"name": "Transmission Date/Time", "len_type": "FIXED", "max": 10},
    11: {"name": "Systems Trace Audit Number", "len_type": "FIXED", "max": 6},
    12: {"name": "Date, Local Transaction", "len_type": "FIXED", "max": 6},
    13: {"name": "Time, Local Transaction", "len_type": "FIXED", "max": 4},
    14: {"name": "Date, Expiration", "len_type": "FIXED", "max": 4},
    15: {"name": "Date, Settlement", "len_type": "FIXED", "max": 6},
    18: {"name": "Merchant Type", "len_type": "FIXED", "max": 4},
    19: {"name": "Acquiring Institution Country Code", "len_type": "FIXED", "max": 3},
    22: {"name": "Point of Service Entry Mode", "len_type": "FIXED", "max": 3},
    25: {"name": "Point of Service Condition Code", "len_type": "FIXED", "max": 2},
    32: {"name": "Acquiring Institution ID Code", "len_type": "LLVAR", "max": 11},
    35: {"name": "Track 2 Data", "len_type": "LLVAR", "max": 37},
    37: {"name": "Retrieval Reference Number", "len_type": "FIXED", "max": 12},
    39: {"name": "Response Code", "len_type": "FIXED", "max": 2},
    41: {"name": "Card Acceptor Terminal ID", "len_type": "FIXED", "max": 8},
    42: {"name": "Card Acceptor ID Code", "len_type": "FIXED", "max": 15},
    43: {"name": "Card Acceptor Name/Location", "len_type": "FIXED", "max": 40},
    48: {"name": "Additional Data (Private)", "len_type": "LLLVAR", "max": 120},
    49: {"name": "Currency Code, Transaction", "len_type": "FIXED", "max": 3},
    52: {"name": "PIN Data", "len_type": "FIXED", "max": 8},
    55: {"name": "EMV Data", "len_type": "LLLVAR", "max": 255},
    63: {"name": "Transaction Life Cycle ID", "len_type": "LLLVAR", "max": 16},
    64: {"name": "Message Authentication Code", "len_type": "FIXED", "max": 8},
    70: {"name": "Card ISSUER/Business Date", "len_type": "FIXED", "max": 8},
    123: {"name": "POS Data Code", "len_type": "FIXED", "max": 12},
    128: {"name": "MAC Extended", "len_type": "FIXED", "max": 8},
}


class FlowState(Enum):
    INIT = "INIT"
    SENT = "SENT"
    AWAITING_RESPONSE = "AWAITING_RESPONSE"
    TIMEOUT = "TIMEOUT"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    REVERSED = "REVERSED"
    CAPTURED = "CAPTURED"
    SETTLED = "SETTLED"
    ERROR = "ERROR"


@dataclass
class Message:
    mti: str
    fields: dict
    hex_payload: str = ""
    timestamp: str = ""

    def to_hex(self, format: str = "ASCII") -> str:
        """Build ISO8583 message as hex string"""
        now = datetime.utcnow()
        if not self.timestamp:
            self.timestamp = now.strftime("%m%d%H%M%S")

        de_keys = sorted(self.fields.keys())
        # Primary bitmap (8 bytes, 64 bits for DE 1-64)
        primary_bitmap = bytearray(8)
        for de in de_keys:
            if 1 <= de <= 64:
                primary_bitmap[(de - 1) // 8] |= 0x80 >> ((de - 1) % 8)

        # Build field data
        field_data = ""
        for de in de_keys:
            if 65 <= de <= 128:
                primary_bitmap[0] |= 0x40  # Set bit for secondary bitmap
            val = str(self.fields[de])
            if de == 2:
                field_data += f"{len(val):02d}{val}"
            elif de in (3, 11, 12, 13, 14, 15, 18, 19, 22, 25, 39, 41, 42, 43, 49, 52, 64, 70, 123, 128):
                field_data += val.ljust(DE.get(de, {}).get("max", 20))[:DE.get(de, {}).get("max", 20)]
            elif de == 32:
                field_data += f"{len(val):02d}{val}"
            elif de in (35, 37, 48, 55, 63):
                field_data += f"{len(val):03d}{val}"

        # ASCII format: MTI + bitmap + fields
        bitmap_hex = primary_bitmap.hex().upper()
        msg = self.mti + bitmap_hex + field_data
        return msg.upper()


@dataclass
class TransactionContext:
    transaction_id: str
    pan: str
    exp_date: str
    amount: str
    currency: str
    merchant_id: str
    terminal_id: str
    stan: int
    timestamp: str
    state: FlowState = FlowState.INIT
    response_code: str = ""
    response_text: str = ""
    steps: list = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30


def generate_stan() -> str:
    return f"{random.randint(1, 999999):06d}"

def generate_rrn() -> str:
    return datetime.utcnow().strftime("%m%d%H%M%S") + f"{random.randint(1, 9999):04d}"

def generate_timestamp() -> str:
    return datetime.utcnow().strftime("%m%d%H%M%S")

def luhn_valid(pan: str) -> bool:
    digits = [int(c) for c in pan]
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9: digits[i] -= 9
    return sum(digits) % 10 == 0

def format_amount(amount: float) -> str:
    return f"{int(amount * 100):012d}"

def pad_exp_date(exp: str) -> str:
    """Convert MMYY or MM/YY to MMDD format"""
    exp = exp.replace("/", "")
    return f"{exp[:2]}{exp[2:4]}"

def pad_date() -> str:
    now = datetime.utcnow()
    return now.strftime("%m%d%H%M%S")

def pad_time() -> str:
    return datetime.utcnow().strftime("%H%M%S")

def pad_date6() -> str:
    return datetime.utcnow().strftime("%m%d%H%M%S")

# ─── Flow: Authorization ─────────────────────────────────────────────────────
def flow_authorize(ctx: TransactionContext, test_mode: bool = False) -> TransactionContext:
    """0100 Authorization Request → Switch → HSM → Scheme → 0110 Response"""
    print("\n" + "=" * 60)
    print("FLOW: AUTHORIZATION")
    print("=" * 60)

    # Step 1: POS sends 0100
    msg_0100 = Message(
        mti="0100",
        fields={
            2: ctx.pan,
            3: "000000",
            4: format_amount(ctx.amount),
            7: pad_date6(),
            11: f"{ctx.stan:06d}",
            12: pad_date(),
            13: pad_time(),
            14: pad_exp_date(ctx.exp_date),
            18: "5411",  # MCC: Grocery stores
            19: "840",   # USD
            22: "051",   # POS Entry Mode: Chip + PIN
            25: "00",
            32: "00000001111",
            35: f"{len(ctx.pan)}={ctx.exp_date}101{generate_stan()}",
            37: generate_rrn(),
            41: ctx.terminal_id,
            42: ctx.merchant_id,
            43: "MERCHANT NAME          CITY US",
            49: ctx.currency,
            55: "9F26081234567890ABCDEF9F2701809F1013ABCDEF1234567890ABCDEF12345678901E",
            123: "1203000000000000",
        }
    )
    msg_0100.hex_payload = msg_0100.to_hex()
    print(f"\n[STEP 1] POS → SWITCH")
    print(f"  MTI: {msg_0100.mti} (Authorization Request)")
    print(f"  DE2 PAN: {msg_0100.fields[2][:6]}****{msg_0100.fields[2][-4:]}")
    print(f"  DE4 Amount: {ctx.amount} {ctx.currency}")
    print(f"  DE11 STAN: {ctx.stan:06d}")
    print(f"  DE37 RRN: {msg_0100.fields[37]}")
    print(f"  HEX: {msg_0100.hex_payload[:80]}...")
    ctx.steps.append({"step": 1, "action": "POS_SEND_0100", "mti": "0100", "hex": msg_0100.hex_payload[:80], "state": "SENT"})
    ctx.state = FlowState.SENT

    # Step 2: Switch parses and routes
    print(f"\n[STEP 2] SWITCH: Parse & Route")
    if not luhn_valid(ctx.pan):
        ctx.response_code = "14"
        ctx.response_text = "Invalid PAN"
        print(f"  ⚠ Luhn check failed → Response: {ctx.response_code}")
    else:
        print(f"  ✓ Luhn check passed")
        print(f"  ✓ Routing to: Scheme (Visa/MC based on BIN)")
        print(f"  ✓ Message validated, bitmap parsed")
        print(f"  ✓ Routed to: SCHEME_CONNECTOR (ISO8583 over TLS)")
    ctx.steps.append({"step": 2, "action": "SWITCH_PARSE_ROUTE", "state": "ROUTED"})

    # Step 3: HSM PIN verification (if PIN present)
    print(f"\n[STEP 3] HSM: PIN Verification")
    print(f"  Command: HC (Verify PIN under ZMK)")
    print(f"  PIN Block (DE52): {msg_0100.fields.get(52, 'N/A')}")
    print(f"  Verifying PIN... → VERIFIED ✓")
    ctx.steps.append({"step": 3, "action": "HSM_PIN_VERIFY", "command": "HC", "result": "OK"})

    # Step 4: Scheme authorization (simulated)
    print(f"\n[STEP 4] SCHEME: Authorization")
    if test_mode:
        ctx.response_code = "00"
        ctx.response_text = "Approved"
    else:
        if float(ctx.amount) > 10000:
            ctx.response_code = "05"
        elif float(ctx.amount) < 0:
            ctx.response_code = "13"
        else:
            ctx.response_code = random.choices(
                ["00", "05", "51", "54", "14"],
                weights=[75, 10, 5, 5, 5]
            )[0]
    ctx.response_text = RESPONSE_CODES.get(ctx.response_code, "Unknown")
    print(f"  Scheme Response: {ctx.response_code} - {ctx.response_text}")
    ctx.steps.append({"step": 4, "action": "SCHEME_AUTH", "response_code": ctx.response_code, "response_text": ctx.response_text})

    # Step 5: Switch sends 0110 to POS
    msg_0110 = Message(
        mti="0110",
        fields={
            2: ctx.pan,
            3: "000000",
            4: format_amount(ctx.amount),
            7: pad_date6(),
            11: f"{ctx.stan:06d}",
            12: pad_date(),
            13: pad_time(),
            14: pad_exp_date(ctx.exp_date),
            18: "5411",
            19: "840",
            22: "051",
            25: "00",
            32: "00000001111",
            37: msg_0100.fields[37],
            39: ctx.response_code,
            41: ctx.terminal_id,
            42: ctx.merchant_id,
            43: "MERCHANT NAME          CITY US",
            49: ctx.currency,
            123: "1203000000000000",
        }
    )
    msg_0110.hex_payload = msg_0110.to_hex()
    print(f"\n[STEP 5] SWITCH → POS")
    print(f"  MTI: {msg_0110.mti} (Authorization Response)")
    print(f"  DE39 Response: {ctx.response_code} - {ctx.response_text}")
    print(f"  HEX: {msg_0110.hex_payload[:80]}...")
    ctx.steps.append({"step": 5, "action": "SWITCH_SEND_0110", "mti": "0110", "hex": msg_0110.hex_payload[:80]})

    if ctx.response_code == "00":
        ctx.state = FlowState.APPROVED
        print(f"\n✅ RESULT: APPROVED")
    else:
        ctx.state = FlowState.DECLINED
        print(f"\n❌ RESULT: DECLINED ({ctx.response_code})")
    return ctx

# ─── Flow: Reversal ──────────────────────────────────────────────────────────
def flow_reversal(ctx: TransactionContext, original_stan: int) -> TransactionContext:
    """0420 Reversal Request → Switch → Scheme → 0430 Response"""
    print("\n" + "=" * 60)
    print("FLOW: REVERSAL / ADJUSTMENT")
    print("=" * 60)

    msg_0420 = Message(
        mti="0420",
        fields={
            2: ctx.pan,
            3: "200000",  # Reversal code
            4: format_amount(ctx.amount),
            7: pad_date6(),
            11: f"{ctx.stan:06d}",
            12: pad_date(),
            13: pad_time(),
            14: pad_exp_date(ctx.exp_date),
            18: "5411",
            19: "840",
            22: "051",
            25: "00",
            32: "00000001111",
            37: generate_rrn(),
            39: "00",  # Will be updated by scheme
            41: ctx.terminal_id,
            42: ctx.merchant_id,
            43: "MERCHANT NAME          CITY US",
            49: ctx.currency,
            63: f"0001{original_stan:06d}",  # Original STAN
            123: "1203000000000000",
        }
    )
    msg_0420.hex_payload = msg_0420.to_hex()
    print(f"\n[STEP 1] POS → SWITCH: Reversal Request")
    print(f"  MTI: {msg_0420.mti}")
    print(f"  DE3: {msg_0420.fields[3]} (Reversal Processing Code)")
    print(f"  DE63: Original STAN = {original_stan:06d}")
    print(f"  HEX: {msg_0420.hex_payload[:80]}...")

    print(f"\n[STEP 2] SWITCH: Route reversal to scheme")
    ctx.steps.append({"step": 1, "action": "SEND_0420", "mti": "0420", "hex": msg_0420.hex_payload[:80]})
    ctx.steps.append({"step": 2, "action": "SCHEME_PROCESS_REVERSAL", "result": "ACCEPTED"})
    ctx.steps.append({"step": 3, "action": "RECEIVE_0430", "mti": "0430", "response": "00"})
    ctx.state = FlowState.REVERSED
    print(f"\n✅ RESULT: REVERSAL COMPLETE")
    return ctx

# ─── Flow: Capture ───────────────────────────────────────────────────────────
def flow_capture(ctx: TransactionContext) -> TransactionContext:
    """0200 Financial Request → 0202 Capture → Settlement Batch"""
    print("\n" + "=" * 60)
    print("FLOW: CAPTURE & SETTLEMENT")
    print("=" * 60)

    msg_0200 = Message(
        mti="0200",
        fields={
            2: ctx.pan,
            3: "000000",
            4: format_amount(ctx.amount),
            7: pad_date6(),
            11: f"{ctx.stan:06d}",
            12: pad_date(),
            13: pad_time(),
            14: pad_exp_date(ctx.exp_date),
            18: "5411",
            19: "840",
            22: "051",
            25: "00",
            32: "00000001111",
            35: f"{len(ctx.pan)}={pad_exp_date(ctx.exp_date)}101{generate_stan()}",
            37: generate_rrn(),
            39: "00",
            41: ctx.terminal_id,
            42: ctx.merchant_id,
            43: "MERCHANT NAME          CITY US",
            49: ctx.currency,
            55: msg_0200.fields.get(55, ""),
            123: "1203000000000000",
        }
    )
    msg_0200.hex_payload = msg_0200.to_hex()
    print(f"\n[STEP 1] POS → SWITCH: Capture Request (MTI 0200)")
    print(f"  DE4 Amount: {ctx.amount}")
    print(f"  DE37 RRN: {msg_0200.fields[37]}")
    print(f"  HEX: {msg_0200.hex_payload[:80]}...")

    print(f"\n[STEP 2] SWITCH: Validate, settle against batch")
    ctx.steps.append({"step": 1, "action": "SEND_0200", "mti": "0200", "hex": msg_0200.hex_payload[:80]})
    ctx.steps.append({"step": 2, "action": "BATCH_MATCH", "original_stan": ctx.stan})
    ctx.steps.append({"step": 3, "action": "CLEARING_BATCH_READY", "batch_id": f"BATCH_{pad_date()}"})
    ctx.state = FlowState.CAPTURED
    print(f"\n✅ RESULT: CAPTURED — Ready for settlement batch")
    return ctx

# ─── Flow: Network Management ─────────────────────────────────────────────────
def flow_network_mgmt(cmd_type: str = "0800") -> list:
    """0800 Echo Test / 0820 Cutover"""
    print("\n" + "=" * 60)
    print(f"FLOW: NETWORK MANAGEMENT ({cmd_type})")
    print("=" * 60)
    steps = []

    if cmd_type == "0800":
        msg_0800 = Message(
            mti="0800",
            fields={
                7: pad_date6(),
                11: f"{random.randint(1, 999999):06d}",
                70: "301",  # Network management code: Echo test
            }
        )
        msg_0800.hex_payload = msg_0800.to_hex()
        print(f"\n[STEP 1] SWITCH → SCHEME: Network Echo Request (0800)")
        print(f"  DE70 NMC: 301 (Echo Test)")
        print(f"  HEX: {msg_0800.hex_payload}")
        steps.append({"action": "SEND_0800", "mti": "0800"})

        print(f"\n[STEP 2] SCHEME → SWITCH: Network Echo Response (0810)")
        msg_0810 = Message(
            mti="0810",
            fields={
                7: msg_0800.fields[7],
                11: msg_0800.fields[11],
                70: "301",
            }
        )
        msg_0810.hex_payload = msg_0810.to_hex()
        print(f"  MTI: 0810 (Echo Response)")
        print(f"  HEX: {msg_0810.hex_payload}")
        steps.append({"action": "RECEIVE_0810", "mti": "0810", "result": "OK"})

    elif cmd_type == "0820":
        print(f"\n[STEP 1] SWITCH: Cutover request (0820)")
        print(f"  DE70 NMC: 001 (Cutover)")
        print(f"  Action: Prepare switch to new instance")
        steps.append({"action": "CUTOVER_PREPARE"})
        print(f"\n[STEP 2] SWITCH: Execute cutover")
        print(f"  Traffic shifted to new instance")
        steps.append({"action": "CUTOVER_EXECUTE", "result": "OK"})

    return steps

# ─── Timeout / Retry Logic ─────────────────────────────────────────────────────
def simulate_timeout_retry(ctx: TransactionContext, steps: list) -> TransactionContext:
    """Simulate timeout scenario and retry flow"""
    print("\n" + "-" * 40)
    print("TIMEOUT / RETRY SIMULATION")
    print("-" * 40)
    print(f"  Initial timeout at: {ctx.timeout_seconds}s")
    print(f"  Retry #{ctx.retry_count + 1}/{ctx.max_retries}")
    if ctx.retry_count < ctx.max_retries:
        ctx.retry_count += 1
        print(f"  → Retrying with same STAN+1 = {ctx.stan + 1:06d}")
        steps.append({"action": "RETRY", "retry_num": ctx.retry_count, "result": "OK"})
    else:
        ctx.state = FlowState.ERROR
        print(f"  → Max retries exceeded. Escalate to manual review.")
        steps.append({"action": "MAX_RETRIES_EXCEEDED", "escalate": True})
    return ctx

# ─── Main CLI ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Transaction Flow Orchestrator")
    parser.add_argument("--flow", required=True,
                        choices=["authorize", "reversal", "capture", "network-mgmt"],
                        help="Transaction flow type")
    parser.add_argument("--pan", default="4111111111111111", help="16-digit PAN")
    parser.add_argument("--exp", default="1225", help="Expiry date (MMYY or MM/YY)")
    parser.add_argument("--amount", type=float, default=99.99, help="Amount")
    parser.add_argument("--currency", default="840", help="ISO 4217 currency code")
    parser.add_argument("--merchant-id", default="MERCHANT001", help="Merchant ID")
    parser.add_argument("--terminal-id", default="TERM001", help="Terminal ID")
    parser.add_argument("--test-mode", action="store_true", help="Force approval")
    parser.add_argument("--simulate-timeout", action="store_true", help="Simulate timeout")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    stan = generate_stan()
    ctx = TransactionContext(
        transaction_id=str(uuid.uuid4())[:8].upper(),
        pan=args.pan,
        exp_date=args.exp,
        amount=args.amount,
        currency=args.currency,
        merchant_id=args.merchant_id,
        terminal_id=args.terminal_id,
        stan=int(stan),
        timestamp=datetime.utcnow().isoformat()
    )

    if args.flow == "authorize":
        ctx = flow_authorize(ctx, test_mode=args.test_mode)
    elif args.flow == "reversal":
        ctx = flow_reversal(ctx, original_stan=int(stan))
    elif args.flow == "capture":
        ctx = flow_capture(ctx)
    elif args.flow == "network-mgmt":
        steps = flow_network_mgmt("0800")

    if args.simulate_timeout:
        ctx = simulate_timeout_retry(ctx, ctx.steps)

    # Print summary
    print("\n" + "=" * 60)
    print("TRANSACTION SUMMARY")
    print("=" * 60)
    summary = {
        "transaction_id": ctx.transaction_id,
        "flow": args.flow,
        "pan": f"{ctx.pan[:6]}***{ctx.pan[-4:]}",
        "amount": f"{ctx.amount} {ctx.currency}",
        "stan": f"{ctx.stan:06d}",
        "state": ctx.state.value,
        "response_code": ctx.response_code,
        "response_text": ctx.response_text,
        "retry_count": ctx.retry_count,
        "steps": ctx.steps,
        "timestamp": ctx.timestamp
    }
    print(json.dumps(summary, indent=2))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSaved to {args.output}")

if __name__ == "__main__":
    main()
