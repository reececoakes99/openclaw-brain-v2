#!/usr/bin/env python3
"""
iso20022_converter.py — ISO20022 MX / SWIFT MT Message Converter
=================================================================
Converts between:
  - ISO20022 MX (XML) ↔ JSON
  - SWIFT MT (FIN) ↔ JSON
  - ISO20022 MX ↔ SWIFT MT (bridging)

Supported message types:
  MX: pain.001, pain.002, pacs.008, pacs.009, pacs.002, camt.053, camt.054
  MT: MT103, MT202, MT900, MT910, MT940, MT950

Usage:
  python3 iso20022_converter.py --input message.xml --format json
  python3 iso20022_converter.py --input message.txt --type mt103 --format mx
  python3 iso20022_converter.py --parse --input '<Document>...</Document>'
"""

import json
import re
import argparse
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from datetime import datetime
import xml.etree.ElementTree as ET


# ── Namespace map for ISO20022 MX messages ──────────────────────────────────
MX_NAMESPACES = {
    'pain.001': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03',
    'pain.002': 'urn:iso:std:iso:20022:tech:xsd:pain.002.001.03',
    'pacs.008': 'urn:iso:std:iso:20022:tech:xsd:pacs.008.001.02',
    'pacs.009': 'urn:iso:std:iso:20022:tech:xsd:pacs.009.001.02',
    'pacs.002': 'urn:iso:std:iso:20022:tech:xsd:pacs.002.001.03',
    'camt.053': 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.02',
    'camt.054': 'urn:iso:std:iso:20022:tech:xsd:camt.054.001.02',
}

# ── SWIFT MT field definitions ────────────────────────────────────────────────
MT_FIELDS = {
    '20':  'Transaction Reference Number',
    '21':  'Related Reference',
    '23B': 'Bank Operation Code',
    '32A': 'Value Date / Currency / Amount',
    '33B': 'Currency / Instructed Amount',
    '50A': 'Ordering Customer (BIC)',
    '50F': 'Ordering Customer (Name+Address)',
    '50K': 'Ordering Customer (Account+Name)',
    '52A': 'Ordering Institution (BIC)',
    '53A': 'Sender\'s Correspondent (BIC)',
    '54A': 'Receiver\'s Correspondent (BIC)',
    '56A': 'Intermediary Institution (BIC)',
    '57A': 'Account With Institution (BIC)',
    '58A': 'Beneficiary Institution (BIC)',
    '59':  'Beneficiary Customer (Account+Name)',
    '59A': 'Beneficiary Customer (BIC)',
    '59F': 'Beneficiary Customer (Structured)',
    '70':  'Remittance Information',
    '71A': 'Details of Charges',
    '72':  'Sender to Receiver Information',
    '77B': 'Regulatory Reporting',
}


@dataclass
class MXMessage:
    message_type: str
    message_id: str
    creation_datetime: str
    sender_bic: Optional[str] = None
    receiver_bic: Optional[str] = None
    transactions: List[Dict] = field(default_factory=list)
    raw_xml: Optional[str] = None
    parsed_fields: Dict = field(default_factory=dict)


@dataclass
class MTMessage:
    message_type: str
    sender_bic: Optional[str] = None
    receiver_bic: Optional[str] = None
    fields: Dict[str, str] = field(default_factory=dict)
    raw_fin: Optional[str] = None


# ── MX Parser ────────────────────────────────────────────────────────────────

def detect_mx_type(xml_string: str) -> Optional[str]:
    """Detect ISO20022 message type from XML namespace."""
    for msg_type, ns in MX_NAMESPACES.items():
        if ns in xml_string:
            return msg_type
    # Try to detect from root element
    match = re.search(r'<(\w+)\s+xmlns', xml_string)
    if match:
        return match.group(1)
    return None


def parse_mx_message(xml_string: str) -> MXMessage:
    """Parse ISO20022 MX XML into structured MXMessage."""
    msg_type = detect_mx_type(xml_string) or 'unknown'

    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")

    # Strip namespace from tags for easier access
    def strip_ns(tag: str) -> str:
        return re.sub(r'\{[^}]+\}', '', tag)

    def xml_to_dict(element) -> Any:
        children = list(element)
        if not children:
            return element.text or ''
        result = {}
        for child in children:
            key = strip_ns(child.tag)
            value = xml_to_dict(child)
            if key in result:
                if not isinstance(result[key], list):
                    result[key] = [result[key]]
                result[key].append(value)
            else:
                result[key] = value
        return result

    parsed = xml_to_dict(root)

    # Extract common header fields
    msg_id = ''
    creation_dt = ''
    sender_bic = None
    receiver_bic = None

    # Try to find GrpHdr (common in pain/pacs messages)
    def find_field(d: dict, key: str) -> Optional[str]:
        if isinstance(d, dict):
            if key in d:
                return str(d[key])
            for v in d.values():
                result = find_field(v, key)
                if result:
                    return result
        return None

    msg_id = find_field(parsed, 'MsgId') or find_field(parsed, 'TxId') or ''
    creation_dt = find_field(parsed, 'CreDtTm') or datetime.utcnow().isoformat()
    sender_bic = find_field(parsed, 'InitgPty') or find_field(parsed, 'DbtrAgt')
    receiver_bic = find_field(parsed, 'CdtrAgt') or find_field(parsed, 'InstdAgt')

    return MXMessage(
        message_type=msg_type,
        message_id=msg_id,
        creation_datetime=creation_dt,
        sender_bic=sender_bic,
        receiver_bic=receiver_bic,
        raw_xml=xml_string,
        parsed_fields=parsed
    )


def mx_to_json(xml_string: str) -> dict:
    """Convert ISO20022 MX XML to JSON dict."""
    msg = parse_mx_message(xml_string)
    return {
        'message_type': msg.message_type,
        'message_id': msg.message_id,
        'creation_datetime': msg.creation_datetime,
        'sender_bic': msg.sender_bic,
        'receiver_bic': msg.receiver_bic,
        'fields': msg.parsed_fields,
        'converted_at': datetime.utcnow().isoformat()
    }


# ── MT Parser ────────────────────────────────────────────────────────────────

def parse_mt_message(fin_string: str) -> MTMessage:
    """Parse SWIFT MT FIN message into structured MTMessage."""
    msg_type = None
    sender_bic = None
    receiver_bic = None
    fields = {}

    # Extract message type from block 2
    b2_match = re.search(r'\{2:[IO](\d{3})', fin_string)
    if b2_match:
        msg_type = f"MT{b2_match.group(1)}"

    # Extract sender/receiver from block 1/2
    b1_match = re.search(r'\{1:F01([A-Z0-9]{8,11})', fin_string)
    if b1_match:
        sender_bic = b1_match.group(1)[:8]

    b2_recv = re.search(r'\{2:I\d{3}([A-Z0-9]{8,11})', fin_string)
    if b2_recv:
        receiver_bic = b2_recv.group(1)[:8]

    # Extract block 4 fields
    b4_match = re.search(r'\{4:(.*?)\}', fin_string, re.DOTALL)
    if b4_match:
        block4 = b4_match.group(1)
        # Parse :TAG:VALUE pairs
        field_pattern = re.finditer(r':(\d{2}[A-Z]?):(.*?)(?=:\d{2}[A-Z]?:|$)', block4, re.DOTALL)
        for m in field_pattern:
            tag = m.group(1)
            value = m.group(2).strip()
            fields[tag] = value
            if tag not in MT_FIELDS:
                MT_FIELDS[tag] = f'Field {tag}'

    return MTMessage(
        message_type=msg_type or 'MT_UNKNOWN',
        sender_bic=sender_bic,
        receiver_bic=receiver_bic,
        fields=fields,
        raw_fin=fin_string
    )


def mt_to_json(fin_string: str) -> dict:
    """Convert SWIFT MT FIN message to JSON dict."""
    msg = parse_mt_message(fin_string)
    result = {
        'message_type': msg.message_type,
        'sender_bic': msg.sender_bic,
        'receiver_bic': msg.receiver_bic,
        'fields': {}
    }
    for tag, value in msg.fields.items():
        result['fields'][tag] = {
            'name': MT_FIELDS.get(tag, f'Field {tag}'),
            'value': value
        }
    result['converted_at'] = datetime.utcnow().isoformat()
    return result


# ── MT → MX Bridge ────────────────────────────────────────────────────────────

def mt103_to_pacs008(fin_string: str) -> str:
    """Convert MT103 (customer credit transfer) to pacs.008 MX XML."""
    mt = parse_mt_message(fin_string)
    fields = mt.fields

    # Extract key fields
    ref = fields.get('20', 'NOTPROVIDED')
    value_date = ''
    currency = 'USD'
    amount = '0'

    f32a = fields.get('32A', '')
    if f32a and len(f32a) >= 9:
        value_date = f32a[:6]  # YYMMDD
        currency = f32a[6:9]
        amount = f32a[9:].lstrip('0') or '0'
        # Convert to decimal
        if amount and not '.' in amount:
            amount = amount[:-2] + '.' + amount[-2:]

    debtor_name = fields.get('50F', fields.get('50K', 'UNKNOWN'))
    creditor_name = fields.get('59F', fields.get('59', 'UNKNOWN'))
    debtor_bic = fields.get('52A', mt.sender_bic or 'NOTPROVIDED')
    creditor_bic = fields.get('57A', mt.receiver_bic or 'NOTPROVIDED')
    remittance = fields.get('70', '')

    # Build ISO date from YYMMDD
    try:
        iso_date = datetime.strptime(value_date, '%y%m%d').strftime('%Y-%m-%d')
    except Exception:
        iso_date = datetime.utcnow().strftime('%Y-%m-%d')

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.02">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>{ref}</MsgId>
      <CreDtTm>{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf>
        <SttlmMtd>CLRG</SttlmMtd>
      </SttlmInf>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <EndToEndId>{ref}</EndToEndId>
        <TxId>{ref}</TxId>
      </PmtId>
      <IntrBkSttlmAmt Ccy="{currency}">{amount}</IntrBkSttlmAmt>
      <IntrBkSttlmDt>{iso_date}</IntrBkSttlmDt>
      <InstdAmt Ccy="{currency}">{amount}</InstdAmt>
      <DbtrAgt>
        <FinInstnId>
          <BIC>{debtor_bic[:8]}</BIC>
        </FinInstnId>
      </DbtrAgt>
      <Dbtr>
        <Nm>{debtor_name[:140]}</Nm>
      </Dbtr>
      <CdtrAgt>
        <FinInstnId>
          <BIC>{creditor_bic[:8]}</BIC>
        </FinInstnId>
      </CdtrAgt>
      <Cdtr>
        <Nm>{creditor_name[:140]}</Nm>
      </Cdtr>
      <RmtInf>
        <Ustrd>{remittance[:140]}</Ustrd>
      </RmtInf>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""
    return xml


# ── MX → MT Bridge ────────────────────────────────────────────────────────────

def pacs008_to_mt103(xml_string: str) -> str:
    """Convert pacs.008 MX XML to MT103 FIN format."""
    msg = parse_mx_message(xml_string)
    f = msg.parsed_fields

    def get(d, *keys):
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return ''
        return str(d) if d else ''

    # Navigate pacs.008 structure
    tx = get(f, 'FIToFICstmrCdtTrf', 'CdtTrfTxInf') or {}
    if isinstance(tx, list):
        tx = tx[0]

    ref = get(tx, 'PmtId', 'TxId') or get(tx, 'PmtId', 'EndToEndId') or 'NOTPROVIDED'
    amount_raw = get(tx, 'IntrBkSttlmAmt') or get(tx, 'InstdAmt') or '0'
    currency = 'USD'

    # Try to get currency attribute
    amt_node = tx.get('IntrBkSttlmAmt', tx.get('InstdAmt', {}))
    if isinstance(amt_node, dict):
        currency = amt_node.get('@Ccy', 'USD')
        amount_raw = amt_node.get('#text', '0')

    settle_date = get(tx, 'IntrBkSttlmDt') or datetime.utcnow().strftime('%Y-%m-%d')
    try:
        dt = datetime.strptime(settle_date[:10], '%Y-%m-%d')
        swift_date = dt.strftime('%y%m%d')
    except Exception:
        swift_date = datetime.utcnow().strftime('%y%m%d')

    amount_str = str(amount_raw).replace('.', ',')
    debtor_bic = get(tx, 'DbtrAgt', 'FinInstnId', 'BIC') or 'NOTPROVIDED'
    creditor_bic = get(tx, 'CdtrAgt', 'FinInstnId', 'BIC') or 'NOTPROVIDED'
    debtor_name = get(tx, 'Dbtr', 'Nm') or 'UNKNOWN'
    creditor_name = get(tx, 'Cdtr', 'Nm') or 'UNKNOWN'
    creditor_acct = get(tx, 'CdtrAcct', 'Id', 'IBAN') or get(tx, 'CdtrAcct', 'Id', 'Othr', 'Id') or ''
    remittance = get(tx, 'RmtInf', 'Ustrd') or ''

    fin = f"""{{1:F01{debtor_bic:<12}0000000000}}{{2:I103{creditor_bic:<12}N}}{{4:
:20:{ref}
:23B:CRED
:32A:{swift_date}{currency}{amount_str}
:50F:/NOTPROVIDED
1/{debtor_name[:35]}
:52A:{debtor_bic}
:57A:{creditor_bic}
:59F:/{creditor_acct}
1/{creditor_name[:35]}
:70:{remittance[:140]}
:71A:SHA
-}}"""
    return fin


# ── Validation ────────────────────────────────────────────────────────────────

def validate_mx(xml_string: str) -> dict:
    """Basic structural validation of MX message."""
    issues = []
    msg_type = detect_mx_type(xml_string)

    if not msg_type:
        issues.append("Could not detect message type from namespace")

    try:
        root = ET.fromstring(xml_string)
        tag_count = sum(1 for _ in root.iter())
        if tag_count < 5:
            issues.append("Message appears too short — likely incomplete")
    except ET.ParseError as e:
        issues.append(f"XML parse error: {e}")

    required_fields = {
        'pain.001': ['MsgId', 'CreDtTm', 'NbOfTxs'],
        'pacs.008': ['MsgId', 'CreDtTm', 'NbOfTxs', 'IntrBkSttlmAmt'],
        'camt.053': ['MsgId', 'CreDtTm', 'Acct'],
    }

    if msg_type in required_fields:
        for req in required_fields[msg_type]:
            if req not in xml_string:
                issues.append(f"Missing required field: {req}")

    return {
        'valid': len(issues) == 0,
        'message_type': msg_type,
        'issues': issues,
        'validated_at': datetime.utcnow().isoformat()
    }


def validate_mt(fin_string: str) -> dict:
    """Basic structural validation of MT FIN message."""
    issues = []
    msg = parse_mt_message(fin_string)

    if not msg.message_type or msg.message_type == 'MT_UNKNOWN':
        issues.append("Could not detect MT message type from block 2")

    if not msg.fields:
        issues.append("No fields found in block 4")

    required_mt = {
        'MT103': ['20', '23B', '32A', '50', '59'],
        'MT202': ['20', '21', '32A', '58A'],
        'MT940': ['20', '25', '28C', '60F'],
    }

    mt_type = msg.message_type
    if mt_type in required_mt:
        for req in required_mt[mt_type]:
            # Check prefix match
            if not any(k.startswith(req) for k in msg.fields):
                issues.append(f"Missing required field: :{req}:")

    return {
        'valid': len(issues) == 0,
        'message_type': mt_type,
        'fields_found': list(msg.fields.keys()),
        'issues': issues,
        'validated_at': datetime.utcnow().isoformat()
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='ISO20022 MX / SWIFT MT Converter')
    parser.add_argument('--input', '-i', help='Input file path or message string')
    parser.add_argument('--format', '-f', choices=['json', 'mx', 'mt103', 'mt202', 'validate'],
                        default='json', help='Output format')
    parser.add_argument('--type', '-t', choices=['mx', 'mt'], help='Force input type detection')
    parser.add_argument('--output', '-o', help='Output file path (default: stdout)')
    args = parser.parse_args()

    # Read input
    if args.input:
        if args.input.startswith('<') or args.input.startswith('{'):
            content = args.input
        else:
            try:
                with open(args.input) as f:
                    content = f.read()
            except FileNotFoundError:
                print(f"Error: File not found: {args.input}", file=sys.stderr)
                sys.exit(1)
    else:
        content = sys.stdin.read()

    content = content.strip()

    # Auto-detect type
    input_type = args.type
    if not input_type:
        input_type = 'mx' if content.startswith('<') else 'mt'

    # Convert
    result = None
    if args.format == 'json':
        if input_type == 'mx':
            result = json.dumps(mx_to_json(content), indent=2)
        else:
            result = json.dumps(mt_to_json(content), indent=2)
    elif args.format == 'mx':
        if input_type == 'mt':
            result = mt103_to_pacs008(content)
        else:
            result = content  # Already MX
    elif args.format in ('mt103', 'mt202'):
        if input_type == 'mx':
            result = pacs008_to_mt103(content)
        else:
            result = content  # Already MT
    elif args.format == 'validate':
        if input_type == 'mx':
            result = json.dumps(validate_mx(content), indent=2)
        else:
            result = json.dumps(validate_mt(content), indent=2)

    if result:
        if args.output:
            with open(args.output, 'w') as f:
                f.write(result)
            print(f"Output written to: {args.output}")
        else:
            print(result)


if __name__ == '__main__':
    main()
