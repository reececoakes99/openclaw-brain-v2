#!/usr/bin/env python3
"""
Sample ISO8583 Test Messages
HISO93 binary format and HISO87 ASCII format for MTI 0100, 0200, 0400
"""
import struct, secrets

# ============== HISO93 Binary Format ==============
# HISO93: Binary encoding, 2-byte MTI, 8-byte primary bitmap,
#         8-byte secondary bitmap if bit 1 set, variable-length fields

def make_hiso93_message(mti, fields):
    """Build HISO93 binary message"""
    msg = struct.pack('!H', mti)  # 2-byte MTI big-endian
    
    # Build primary bitmap (byte 0 = bits 1-8, byte 7 = bits 64-72)
    primary = bytearray(8)
    secondary = None
    has_secondary = False
    
    for field_num, value in sorted(fields.items()):
        if 1 <= field_num <= 64:
            byte_idx = (field_num - 1) // 8
            bit_idx = (field_num - 1) % 8
            primary[byte_idx] |= (0x80 >> bit_idx)
        elif 65 <= field_num <= 128:
            if not has_secondary:
                secondary = bytearray(8)
                has_secondary = True
                primary[0] |= 0x80  # Bit 1 set = secondary bitmap present
            byte_idx = (field_num - 65) // 8
            bit_idx = (field_num - 65) % 8
            secondary[byte_idx] |= (0x80 >> bit_idx)
    
    msg += bytes(primary)
    if has_secondary:
        msg += bytes(secondary)
    
    # Add fixed-length fields (standard positions)
    field_order = [2, 3, 4, 7, 11, 12, 13, 14, 15, 17, 18, 19, 22, 23, 25, 32, 35, 37, 38, 41, 42, 43, 49, 50, 52, 53, 54, 57, 58, 59, 60, 61, 62, 63]
    
    # Add field data
    for fn, val in sorted(fields.items()):
        if isinstance(val, bytes):
            msg += val
        elif isinstance(val, str):
            msg += val.encode('ascii')
        elif isinstance(val, int):
            msg += str(val).encode('ascii')
    
    return msg

# Authorization Request (0100)
AUTHORIZATION_REQUEST_HISO93 = bytes.fromhex(
    '0130'  # MTI 0100
    '80'    # Primary bitmap: bit 1 set (secondary bitmap)
    '0000000000000000'  # Secondary bitmap (all 0 = no fields 65-128)
    '0000000000000000000000000000000000000000000000000000000000000000'  # Primary bitmap bytes
)
# Corrected - let's build it properly
AUTHORIZATION_REQUEST_HISO93 = (
    b'\x01\x30'  # MTI
    b'\xe0\x00\x00\x00\x01\x00\x00\x00'  # Primary bitmap (bits 2,11,12,14,15,17,18,20,21,22,23,25,32,41,42,43)
    b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Secondary (empty)
    b'4111111111111111'  # DE2 PAN
    b'000000'             # DE3 Processing code (000000 = auth)
    b'0526100000'        # DE7 Transmission datetime (MMDDhhmmss)
    b'000001'            # DE11 System trace audit number (STAN)
    b'000000'            # DE12 Local transaction time
    b'0526'              # DE13 Local transaction date
    b'00'                # DE14 Expiry date (placeholder)
    b'00'                # DE15 Settlement date
    b'000'               # DE17 Pos entry mode
    b'000'               # DE18 Pos condition code
    b'0000'              # DE19 Acquiring institution country code
    b'0000'              # DE20 PAN extended country code
    b'0000'              # DE21 Forwarding institution country code
    b'MERCHANT001'       # DE41 Card acceptor terminal ID
    b'MERCHANT NAME     ' # DE42 Card acceptor name/location
    b'840'               # DE43 Currency code (USD)
)

# Financial Transaction Request (0200)
FINANCIAL_REQUEST_HISO93 = (
    b'\x02\x00'  # MTI
    b'\xf0\x00\x00\x00\x01\x00\x00\x00'  # Bitmap (auth fields + DE49)
    b'\x00\x00\x00\x00\x00\x00\x00\x00'
    b'4111111111111111'  # DE2
    b'000000'             # DE3
    b'0526100000'         # DE7
    b'000002'             # DE11
    b'0526'               # DE13
    b'840'                # DE49 (currency code)
)

# Reversal Request (0400)
REVERSAL_REQUEST_HISO93 = (
    b'\x04\x00'  # MTI
    b'\xf0\x04\x00\x00\x01\x00\x00\x00'  # Bitmap (has DE90)
    b'\x00\x00\x00\x00\x00\x00\x00\x00'
    b'4111111111111111'  # DE2
    b'000000'             # DE3
    b'0526100000'         # DE7
    b'000003'             # DE11
    b'0526'               # DE13
    b'00000000000000000000'  # DE90 Original data elements (original MTI + STAN + datetime)
)

# ============== HISO87 ASCII Format ==============
# Length prefix (4-digit ASCII), MTI (4-digit ASCII), bitmap (16 or 32 ASCII hex chars), fields ASCII

AUTHORIZATION_REQUEST_HISO87 = (
    '0040'        # Length: 64 bytes
    '0100'        # MTI
    'F00000010000000000000000'  # Bitmap (bits 2,11,12,14,15,17,18,20,21,22,23,25,32,41,42,43)
    '4111111111111111'           # DE2
    '000000'                    # DE3
    '0526100000000001'          # DE7 + DE11
    '05260000000000'            # DE12 + DE13 + DE14
    '000000'                    # DE17 + DE18
    '0000000000'               # DE19 + DE20 + DE21
    'MERCHANT001MERCHANT NAME     840'  # DE41 + DE42 + DE43
)
AUTHORIZATION_REQUEST_HISO87 = AUTHORIZATION_REQUEST_HISO87.encode('ascii')

FINANCIAL_REQUEST_HISO87 = (
    '0040'
    '0200'
    'F00000010000000000000000'
    '4111111111111111'
    '000000'
    '0526100000000002'
    '05260000000000'
    '000000'
    '0000000000'
    'MERCHANT001MERCHANT NAME     840'
).encode('ascii')

REVERSAL_REQUEST_HISO87 = (
    '0050'
    '0400'
    'F004000000010000000000000'
    '4111111111111111'
    '000000'
    '0526100000000003'
    '05260000000000'
    '000000'
    '0000000000'
    'MERCHANT001MERCHANT NAME     840'
    '0100000000000526100000'  # DE90 Original data
).encode('ascii')

# ============== Message Templates ==============
MESSAGE_TEMPLATES = {
    '0100': {
        'hiso93': AUTHORIZATION_REQUEST_HISO93,
        'hiso87': AUTHORIZATION_REQUEST_HISO87,
        'description': 'Authorization Request',
        'expected_response': '0110',
        'response_codes': {'00': 'Approved', '05': 'Do not honor', '51': 'Insufficient funds', '54': 'Expired card'}
    },
    '0200': {
        'hiso93': FINANCIAL_REQUEST_HISO93,
        'hiso87': FINANCIAL_REQUEST_HISO87,
        'description': 'Financial Transaction Request',
        'expected_response': '0210',
        'response_codes': {'00': 'Approved', '05': 'Do not honor', '12': 'Invalid transaction', '14': 'Invalid card', '51': 'Insufficient funds'}
    },
    '0400': {
        'hiso93': REVERSAL_REQUEST_HISO93,
        'hiso87': REVERSAL_REQUEST_HISO87,
        'description': 'Reversal Request',
        'expected_response': '0410',
        'response_codes': {'00': 'Approved', '10': 'Partial reversal', '11': 'Already reversed'}
    }
}

def generate_random_pan():
    """Generate a valid Luhn PAN starting with 4 (Visa test range)"""
    prefix = '4' + ''.join([str(secrets.randbelow(10)) for _ in range(14)])
    # Calculate Luhn check digit
    digits = [int(c) for c in prefix]
    for i in range(10):
        test = prefix + str(i)
        if luhn_check(test):
            return test
    return prefix + '0'

def luhn_check(number):
    digits = [int(c) for c in number]
    odd = digits[-1::-2]
    even = digits[-2::-2]
    total = sum(odd) + sum(sum(divmod(d*2, 10)) for d in even)
    return total % 10 == 0

def generate_auth_message(mti='0100', amount='000000001000', currency='840', pan=None):
    """Generate a random valid authorization message"""
    if pan is None:
        pan = generate_random_pan()
    rrn = ''.join([str(secrets.randbelow(10)) for _ in range(12)])
    stan = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    return {
        'mti': mti,
        'pan': pan,
        'amount': amount,
        'currency': currency,
        'rrn': rrn,
        'stan': stan,
        'term_id': 'TERM001',
        'merch_id': 'MERCHANT001'
    }

if __name__ == '__main__':
    import json
    print("=== HISO93 Binary Messages ===")
    print(f"Auth Request: {AUTHORIZATION_REQUEST_HISO93.hex()}")
    print(f"Auth Request length: {len(AUTHORIZATION_REQUEST_HISO93)} bytes")
    print()
    print("=== HISO87 ASCII Messages ===")
    print(f"Auth Request: {AUTHORIZATION_REQUEST_HISO87.decode()}")
    print(f"Auth Request length: {len(AUTHORIZATION_REQUEST_HISO87)} bytes")
    print()
    print("=== Generated Message ===")
    msg = generate_auth_message()
    print(json.dumps(msg, indent=2))