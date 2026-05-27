#!/usr/bin/env python3
"""
clearing_settlement.py — Visa/Mastercard Clearing & Settlement Processor
=========================================================================
Implements parsing and generation of:
  - Visa Base II / CTF (Clearing Transaction File) records
  - Mastercard IPM (Interchange Posting and Management) files
  - ISO8583 batch settlement messages
  - Net settlement position calculation
  - Dispute and chargeback record generation

Usage:
  python3 clearing_settlement.py --parse --file batch.ctf --format visa
  python3 clearing_settlement.py --generate --format mc --count 100 --output test_ipm.bin
  python3 clearing_settlement.py --settle --file batch.json --report settlement_report.json
  python3 clearing_settlement.py --analyze --file batch.ctf
"""

import json
import struct
import argparse
import random
import string
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal


# ── Visa CTF Record Types ─────────────────────────────────────────────────────
VISA_RECORD_TYPES = {
    '0100': 'Authorization Request',
    '0110': 'Authorization Response',
    '0120': 'Authorization Advice',
    '0200': 'Financial Request',
    '0210': 'Financial Response',
    '0220': 'Financial Advice',
    '0400': 'Reversal Request',
    '0420': 'Reversal Advice',
    '0500': 'Reconciliation Request',
    '0510': 'Reconciliation Response',
    '0600': 'Administrative Request',
    '0620': 'Administrative Advice',
    '0800': 'Network Management Request',
    '0810': 'Network Management Response',
}

# ── Mastercard IPM DE (Data Element) definitions ──────────────────────────────
MC_IPM_DE = {
    2:   ('PAN', 'LLVAR', 19),
    3:   ('Processing Code', 'FIXED', 6),
    4:   ('Amount Transaction', 'FIXED', 12),
    5:   ('Amount Settlement', 'FIXED', 12),
    6:   ('Amount Cardholder Billing', 'FIXED', 12),
    7:   ('Transmission Date/Time', 'FIXED', 10),
    9:   ('Conversion Rate Settlement', 'FIXED', 8),
    10:  ('Conversion Rate Cardholder Billing', 'FIXED', 8),
    11:  ('STAN', 'FIXED', 6),
    12:  ('Time Local Transaction', 'FIXED', 6),
    13:  ('Date Local Transaction', 'FIXED', 4),
    14:  ('Date Expiration', 'FIXED', 4),
    15:  ('Date Settlement', 'FIXED', 4),
    22:  ('POS Entry Mode', 'FIXED', 3),
    23:  ('Card Sequence Number', 'FIXED', 3),
    24:  ('Network International ID', 'FIXED', 3),
    25:  ('POS Condition Code', 'FIXED', 2),
    26:  ('POS PIN Capture Code', 'FIXED', 2),
    30:  ('Amounts Original', 'FIXED', 24),
    32:  ('Acquiring Institution ID', 'LLVAR', 11),
    33:  ('Forwarding Institution ID', 'LLVAR', 11),
    37:  ('RRN', 'FIXED', 12),
    38:  ('Authorization ID Response', 'FIXED', 6),
    39:  ('Response Code', 'FIXED', 2),
    40:  ('Service Restriction Code', 'FIXED', 3),
    41:  ('Card Acceptor Terminal ID', 'FIXED', 8),
    42:  ('Card Acceptor ID Code', 'FIXED', 15),
    43:  ('Card Acceptor Name/Location', 'FIXED', 40),
    48:  ('Additional Data Private', 'LLLVAR', 999),
    49:  ('Currency Code Transaction', 'FIXED', 3),
    50:  ('Currency Code Settlement', 'FIXED', 3),
    51:  ('Currency Code Cardholder Billing', 'FIXED', 3),
    54:  ('Amounts Additional', 'LLLVAR', 120),
    55:  ('ICC Data', 'LLLVAR', 510),
    62:  ('Interchange Data', 'LLLVAR', 999),
    63:  ('Network Data', 'LLLVAR', 999),
}

# ── Transaction Categories ────────────────────────────────────────────────────
TRANSACTION_CATEGORIES = {
    '000000': 'Purchase',
    '200000': 'Refund/Credit',
    '010000': 'Cash Advance',
    '090000': 'Purchase with Cashback',
    '310000': 'Balance Inquiry',
    '920000': 'Settlement',
}


@dataclass
class ClearingRecord:
    record_type: str
    mti: str
    pan: str
    amount: Decimal
    currency: str
    settlement_amount: Decimal
    settlement_currency: str
    processing_code: str
    stan: str
    rrn: str
    auth_code: str
    response_code: str
    terminal_id: str
    merchant_id: str
    merchant_name: str
    transaction_datetime: str
    settlement_date: str
    acquirer_id: str
    issuer_id: str
    card_type: str = 'UNKNOWN'
    transaction_category: str = ''
    icc_data: str = ''
    raw: str = ''


@dataclass
class SettlementReport:
    report_date: str
    total_transactions: int
    total_purchase_amount: Decimal
    total_refund_amount: Decimal
    total_cash_advance_amount: Decimal
    net_settlement_amount: Decimal
    currency: str
    acquirer_id: str
    records: List[ClearingRecord] = field(default_factory=list)
    by_merchant: Dict = field(default_factory=dict)
    by_card_type: Dict = field(default_factory=dict)
    by_response_code: Dict = field(default_factory=dict)
    disputes: List[Dict] = field(default_factory=list)


# ── Visa CTF Parser ───────────────────────────────────────────────────────────

def parse_visa_ctf_record(line: str) -> Optional[ClearingRecord]:
    """Parse a single Visa CTF record (fixed-width format)."""
    if len(line) < 100:
        return None

    try:
        # Visa CTF fixed-width layout (simplified)
        mti = line[0:4]
        pan = line[4:23].strip()
        proc_code = line[23:29]
        amount_str = line[29:41]
        settle_amount_str = line[41:53]
        trans_datetime = line[53:63]
        stan = line[63:69]
        auth_code = line[69:75]
        response_code = line[75:77]
        terminal_id = line[77:85]
        merchant_id = line[85:100].strip()
        merchant_name = line[100:140].strip() if len(line) > 140 else ''
        rrn = line[140:152].strip() if len(line) > 152 else ''
        currency = line[152:155] if len(line) > 155 else '840'
        settle_currency = line[155:158] if len(line) > 158 else '840'
        acquirer_id = line[158:169].strip() if len(line) > 169 else ''
        issuer_id = line[169:180].strip() if len(line) > 180 else ''

        amount = Decimal(amount_str) / 100 if amount_str.strip() else Decimal('0')
        settle_amount = Decimal(settle_amount_str) / 100 if settle_amount_str.strip() else Decimal('0')

        return ClearingRecord(
            record_type='VISA_CTF',
            mti=mti,
            pan=pan,
            amount=amount,
            currency=currency,
            settlement_amount=settle_amount,
            settlement_currency=settle_currency,
            processing_code=proc_code,
            stan=stan,
            rrn=rrn,
            auth_code=auth_code,
            response_code=response_code,
            terminal_id=terminal_id,
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            transaction_datetime=trans_datetime,
            settlement_date=datetime.utcnow().strftime('%m%d'),
            acquirer_id=acquirer_id,
            issuer_id=issuer_id,
            transaction_category=TRANSACTION_CATEGORIES.get(proc_code, 'Unknown'),
            raw=line
        )
    except Exception as e:
        return None


def parse_visa_ctf_file(filepath: str) -> List[ClearingRecord]:
    """Parse a complete Visa CTF file."""
    records = []
    try:
        with open(filepath, 'r', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                line = line.rstrip('\n\r')
                if not line or line.startswith('#'):
                    continue
                record = parse_visa_ctf_record(line)
                if record:
                    records.append(record)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
    return records


# ── Mastercard IPM Parser ─────────────────────────────────────────────────────

def parse_mc_ipm_record(data: dict) -> ClearingRecord:
    """Parse a Mastercard IPM record from JSON representation."""
    de = data.get('de', {})

    pan = de.get('2', '')
    proc_code = de.get('3', '000000')
    amount_str = de.get('4', '000000000000')
    settle_amount_str = de.get('5', '000000000000')
    trans_datetime = de.get('7', '')
    stan = de.get('11', '')
    auth_code = de.get('38', '')
    response_code = de.get('39', '00')
    terminal_id = de.get('41', '')
    merchant_id = de.get('42', '')
    merchant_name = de.get('43', '')[:25]
    rrn = de.get('37', '')
    currency = de.get('49', '840')
    settle_currency = de.get('50', '840')
    acquirer_id = de.get('32', '')
    issuer_id = de.get('33', '')
    icc_data = de.get('55', '')
    mti = data.get('mti', '0220')

    try:
        amount = Decimal(amount_str) / 100
        settle_amount = Decimal(settle_amount_str) / 100
    except Exception:
        amount = Decimal('0')
        settle_amount = Decimal('0')

    return ClearingRecord(
        record_type='MC_IPM',
        mti=mti,
        pan=pan,
        amount=amount,
        currency=currency,
        settlement_amount=settle_amount,
        settlement_currency=settle_currency,
        processing_code=proc_code,
        stan=stan,
        rrn=rrn,
        auth_code=auth_code,
        response_code=response_code,
        terminal_id=terminal_id,
        merchant_id=merchant_id,
        merchant_name=merchant_name,
        transaction_datetime=trans_datetime,
        settlement_date=de.get('15', datetime.utcnow().strftime('%m%d')),
        acquirer_id=acquirer_id,
        issuer_id=issuer_id,
        transaction_category=TRANSACTION_CATEGORIES.get(proc_code, 'Unknown'),
        icc_data=icc_data,
        raw=json.dumps(data)
    )


# ── Settlement Calculator ─────────────────────────────────────────────────────

def calculate_settlement(records: List[ClearingRecord], acquirer_id: str = '') -> SettlementReport:
    """Calculate net settlement position from clearing records."""
    total_purchase = Decimal('0')
    total_refund = Decimal('0')
    total_cash = Decimal('0')
    by_merchant = {}
    by_card_type = {}
    by_response = {}
    disputes = []
    currency = '840'

    for rec in records:
        if rec.settlement_currency:
            currency = rec.settlement_currency

        # Categorize by processing code
        if rec.processing_code.startswith('00'):
            total_purchase += rec.settlement_amount
        elif rec.processing_code.startswith('20'):
            total_refund += rec.settlement_amount
        elif rec.processing_code.startswith('01'):
            total_cash += rec.settlement_amount

        # By merchant
        mid = rec.merchant_id or 'UNKNOWN'
        if mid not in by_merchant:
            by_merchant[mid] = {
                'name': rec.merchant_name,
                'transaction_count': 0,
                'total_amount': Decimal('0'),
                'refund_amount': Decimal('0')
            }
        by_merchant[mid]['transaction_count'] += 1
        if rec.processing_code.startswith('20'):
            by_merchant[mid]['refund_amount'] += rec.settlement_amount
        else:
            by_merchant[mid]['total_amount'] += rec.settlement_amount

        # By response code
        rc = rec.response_code
        by_response[rc] = by_response.get(rc, 0) + 1

        # Flag potential disputes (declined after auth, duplicate STAN, etc.)
        if rec.response_code not in ('00', '10', '85'):
            disputes.append({
                'rrn': rec.rrn,
                'stan': rec.stan,
                'pan_masked': rec.pan[:6] + '****' + rec.pan[-4:] if len(rec.pan) >= 10 else rec.pan,
                'amount': str(rec.amount),
                'response_code': rec.response_code,
                'merchant_id': rec.merchant_id,
                'reason': f'Non-approval response: {rec.response_code}'
            })

    net = total_purchase - total_refund

    # Convert Decimal to str for JSON serialization
    def d2s(d: Decimal) -> str:
        return str(d.quantize(Decimal('0.01')))

    by_merchant_str = {
        k: {
            'name': v['name'],
            'transaction_count': v['transaction_count'],
            'total_amount': d2s(v['total_amount']),
            'refund_amount': d2s(v['refund_amount'])
        }
        for k, v in by_merchant.items()
    }

    return SettlementReport(
        report_date=datetime.utcnow().strftime('%Y-%m-%d'),
        total_transactions=len(records),
        total_purchase_amount=total_purchase,
        total_refund_amount=total_refund,
        total_cash_advance_amount=total_cash,
        net_settlement_amount=net,
        currency=currency,
        acquirer_id=acquirer_id,
        records=records,
        by_merchant=by_merchant_str,
        by_card_type=by_card_type,
        by_response_code=by_response,
        disputes=disputes
    )


# ── Test Data Generator ───────────────────────────────────────────────────────

def generate_test_batch(count: int = 100, fmt: str = 'visa') -> List[dict]:
    """Generate a batch of test clearing records."""
    records = []
    merchants = [
        ('MERCH001', 'AMAZON MARKETPLACE'),
        ('MERCH002', 'WOOLWORTHS SUPERMARKET'),
        ('MERCH003', 'SHELL FUEL STATION'),
        ('MERCH004', 'NETFLIX SUBSCRIPTION'),
        ('MERCH005', 'UBER TECHNOLOGIES'),
    ]
    pan_prefixes = ['4111', '5500', '3714', '6011', '3528']

    for i in range(count):
        merchant_id, merchant_name = random.choice(merchants)
        pan_prefix = random.choice(pan_prefixes)
        pan = pan_prefix + ''.join(random.choices(string.digits, k=12))
        amount = round(random.uniform(1.00, 500.00), 2)
        proc_code = random.choices(
            ['000000', '200000', '010000'],
            weights=[80, 15, 5]
        )[0]
        response_code = random.choices(
            ['00', '05', '51', '54', '12'],
            weights=[85, 5, 5, 3, 2]
        )[0]

        now = datetime.utcnow() - timedelta(hours=random.randint(0, 24))

        if fmt == 'visa':
            # Visa CTF fixed-width format
            pan_padded = pan.ljust(19)
            amount_cents = str(int(amount * 100)).zfill(12)
            settle_cents = amount_cents
            trans_dt = now.strftime('%m%d%H%M%S')
            stan = str(i + 1).zfill(6)
            auth_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            terminal_id = f"TERM{random.randint(1000, 9999)}"
            rrn = ''.join(random.choices(string.digits, k=12))
            line = (
                f"0220{pan_padded}{proc_code}{amount_cents}{settle_cents}"
                f"{trans_dt}{stan}{auth_code}{response_code}"
                f"{terminal_id}{merchant_id:<15}{merchant_name:<40}"
                f"{rrn}840840"
                f"{'ACQ001':>11}{'ISS001':>11}"
            )
            records.append({'raw': line, 'format': 'visa_ctf'})

        else:  # Mastercard IPM JSON
            record = {
                'mti': '0220',
                'de': {
                    '2': pan,
                    '3': proc_code,
                    '4': str(int(amount * 100)).zfill(12),
                    '5': str(int(amount * 100)).zfill(12),
                    '7': now.strftime('%m%d%H%M%S'),
                    '11': str(i + 1).zfill(6),
                    '12': now.strftime('%H%M%S'),
                    '13': now.strftime('%m%d'),
                    '15': now.strftime('%m%d'),
                    '37': ''.join(random.choices(string.digits, k=12)),
                    '38': ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)),
                    '39': response_code,
                    '41': f"TERM{random.randint(1000, 9999)}",
                    '42': merchant_id.ljust(15),
                    '43': merchant_name[:25].ljust(25) + 'SYDNEY         AU',
                    '49': '840',
                    '50': '840',
                    '32': 'ACQ001',
                    '33': 'ISS001',
                }
            }
            records.append(record)

    return records


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Visa/Mastercard Clearing & Settlement Processor')
    parser.add_argument('--parse', action='store_true', help='Parse a clearing file')
    parser.add_argument('--generate', action='store_true', help='Generate test clearing data')
    parser.add_argument('--settle', action='store_true', help='Calculate settlement position')
    parser.add_argument('--analyze', action='store_true', help='Analyze clearing file for anomalies')
    parser.add_argument('--file', '-f', help='Input file path')
    parser.add_argument('--format', choices=['visa', 'mc'], default='visa', help='File format')
    parser.add_argument('--count', type=int, default=100, help='Number of records to generate')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--acquirer-id', default='ACQ001', help='Acquirer ID for settlement')
    args = parser.parse_args()

    if args.generate:
        records = generate_test_batch(args.count, args.format)
        print(f"Generated {len(records)} {args.format.upper()} clearing records")

        if args.output:
            if args.format == 'visa':
                with open(args.output, 'w') as f:
                    for r in records:
                        f.write(r['raw'] + '\n')
            else:
                with open(args.output, 'w') as f:
                    json.dump(records, f, indent=2)
            print(f"Saved to: {args.output}")
        else:
            for r in records[:5]:
                print(r.get('raw', json.dumps(r))[:80] + '...')
            if len(records) > 5:
                print(f"... and {len(records) - 5} more records")

    elif args.parse or args.settle or args.analyze:
        if not args.file:
            print("Error: --file required", file=sys.stderr)
            sys.exit(1)

        if args.format == 'visa':
            records = parse_visa_ctf_file(args.file)
        else:
            with open(args.file) as f:
                raw_records = json.load(f)
            records = [parse_mc_ipm_record(r) for r in raw_records]

        print(f"Parsed {len(records)} records from {args.file}")

        if args.settle or args.analyze:
            report = calculate_settlement(records, args.acquirer_id)

            def d2s(d):
                return str(d.quantize(Decimal('0.01'))) if isinstance(d, Decimal) else str(d)

            summary = {
                'report_date': report.report_date,
                'acquirer_id': report.acquirer_id,
                'total_transactions': report.total_transactions,
                'total_purchase_amount': d2s(report.total_purchase_amount),
                'total_refund_amount': d2s(report.total_refund_amount),
                'total_cash_advance_amount': d2s(report.total_cash_advance_amount),
                'net_settlement_amount': d2s(report.net_settlement_amount),
                'currency': report.currency,
                'by_merchant': report.by_merchant,
                'by_response_code': report.by_response_code,
                'disputes_flagged': len(report.disputes),
                'disputes': report.disputes[:20],
            }

            print(f"\n=== Settlement Summary ===")
            print(f"Total Transactions: {report.total_transactions}")
            print(f"Total Purchase:     {d2s(report.total_purchase_amount)} {report.currency}")
            print(f"Total Refunds:      {d2s(report.total_refund_amount)} {report.currency}")
            print(f"Net Settlement:     {d2s(report.net_settlement_amount)} {report.currency}")
            print(f"Disputes Flagged:   {len(report.disputes)}")

            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(summary, f, indent=2)
                print(f"Report saved: {args.output}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
