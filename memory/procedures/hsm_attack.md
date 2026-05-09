# HSM Attack Procedures

## Overview

Hardware Security Modules (HSM) protect cryptographic keys and perform sensitive operations (PIN verification, MAC generation, key derivation). Attacking an HSM means compromising the root of trust for the entire payment system.

## Target Profile

Common HSMs in payment environments:
- **Thales PayShield 10K** — enterprise payment HSM, supports PIN, MAC, key exchange
- **Thales PayShield 9K** — legacy variant, similar attack surface
- **Utimaco HSM** — high-security, used in cloud payment infrastructure
- **AWS CloudHSM** — cloud-hosted HSM, different attack surface (API interface)
- **Marvell HSM** — lower-end terminal HSM, common in POS

## Attack Surface

```
HSM attack surface:
├── Management interface (TCP 18443 / SSH / serial)
│   ├── Default credentials (common in legacy deployments)
│   ├── Weak key exchange protocols
│   └── Firmware extraction via JTAG/serial
│
├── Key loading interface
│   ├── Manual key injection (ZMK → TMK → KEK chain)
│   ├── Key ceremony corruption
│   └── Lazy key loading (key in memory, not secure flash)
│
├── Command interface
│   ├── PIN verification commands (verify_pin, generate_pin)
│   ├── MAC commands (generate_mac, verify_mac)
│   ├── Key derivation commands (derive_key, translate_key)
│   └── Custom commands exposed by vendor firmware
│
└── API interface (for cloud HSMs)
    ├── AWS CloudHSM PKCS#11 interface
    ├── Key extraction via weak session authentication
    └── Command injection via malformed PKCS#11
```

## Pre-Attack Intelligence

```
Before attacking HSM:
1. Identify HSM type and firmware version
   - Port scan: 18443 (PayShield), 9999 (legacy)
   - Check SSL certificate banner for HSM type
   - Look for HSM vendor-specific HTTP headers
   
2. Identify management interface exposure
   - Is SSH open on HSM management port?
   - Is there an unguarded serial console?
   - Does cloud HSM have exposed PKCS#11 endpoint?
   
3. Map key hierarchy
   - Identify if ZMK (Zone Master Key) is in use
   - Determine key hierarchy: ZMK → TMK → KEK → Data keys
   - Check for key versioning / rotation schedule
   
4. Identify command interface
   - HSO commands visible in network traffic?
   - API commands for cloud HSM?
   - Are vendor-specific commands enabled?
```

## Key Extraction Attacks

### 1. ZMK Interception via Lazy Loading

```
Vulnerability: Some HSM configurations load ZMK from secure memory 
on transaction start, leaving plaintext in RAM during operation.

Attack:
1. Monitor HSM traffic during key exchange window
2. Capture ZMK-loaded transaction (HSO message type 0800)
3. Extract key component from captured traffic
4. Derive lower-tier keys (TMK, working keys)

Detection: Check for 0800 messages without proper key wrapping
Mitigation: Use HSM-bound key exchange only
```

### 2. Key Derivation Weakness

```
Vulnerability: Some HSM implementations use predictable key derivation
from a known master key + counter/timestamp.

Attack:
1. Capture multiple key derivation operations
2. Identify derivation algorithm (often vendor-specific)
3. Derive master key from 2+ derived keys + known derivation data
4. Generate any key in the hierarchy

Known weak derivations:
- Thales: variant key derivation with predictable offset
- Utimaco: timestamp-seeded derivation
- AWS CloudHSM: predictable master key in certain configurations
```

### 3. Terminal Key Extraction

```
Vulnerability: POS terminals often store TMK in local flash with weak encryption.

Attack chain:
1. Physical access to POS terminal (or remote via management interface)
2. Extract TMK from local storage (often flat file or SQLite)
3. Decrypt with known vendor key or default algorithm
4. Derive working keys (TPK, MAC key, PIN key)

Tools:
- POS_terminal_dump.py (from neopay/scripts/)
- HSM_simulator for key chain verification
```

## PIN Block Attacks

### ISO9564-1 Oracle Attack

```
PIN block format: TPAD ⊕ PIN ⊕ PAN

If you have:
- Encrypted PIN block
- PAN (partially known or fully known)

Attack:
1. Extract encrypted PIN block from transaction
2. If PAN is known (last 4 digits + card BIN): brute force first 6 digits
   - For each candidate PAN: TPAD ⊕ PIN ⊕ PAN = encrypted
   - Compare to captured block
   - When match found: PIN = TPAD ⊕ encrypted ⊕ PAN
   
3. Use HSM simulator to accelerate brute force:
   python3 neopay/scripts/pin_block.py --mode brute-force \
     --pin-block <encrypted_hex> --pan-suffix <last4>

Protection: Use account-based format (ISO9564-3) or secure PIN pad
```

### PIN Verification Attack

```
Vulnerability: Some gateways send PIN directly for verification vs HSM verify.

Attack:
1. Intercept PIN verification request
2. Forward to legitimate HSM via captured session
3. Extract result and potentially PIN plaintext

Detection: PIN verification without proper HSM session management
```

## MAC Attacks

### MAC Replay

```
Vulnerability: Gateway accepts same MAC for multiple transactions.

Attack:
1. Capture valid transaction with MAC
2. Modify transaction amount
3. Replay same MAC with modified message
4. Verify: does gateway accept?

Counter: Check for MAC over message content including amount
```

### MAC Generation Bypass

```
If you have access to HSM (physical or network):
1. Generate MAC for arbitrary message
2. Use generated MAC to authenticate fraud transaction

Attack chain:
1. Gain HSM command access (network or physical)
2. Issue generate_mac command for crafted transaction
3. Use valid MAC in fraud transaction

Protection: HSM must validate MAC requester's permissions
```

## Key Exchange Attacks

### ISO9797-1 Algorithm Confusion

```
Vulnerability: Some gateways accept DES instead of 3DES for key exchange.

Attack:
1. During key exchange (0800/0810), inject DES key component
2. If gateway accepts DES variant, you may be able to:
   - Downgrade to weak key length (56-bit)
   - Exploit weak DES key exchange (meet-in-middle)
   
Protection: Enforce 3DES or AES-128 minimum in key exchange
```

### Key Exchange Replay

```
Vulnerability: Key exchange messages replayable.

Attack:
1. Capture valid key exchange (0800/0810)
2. Replay at later time
3. If gateway accepts replay, derive working keys from old exchange

Protection: Timestamp validation, sequence numbers, one-time keys
```

## Cloud HSM Attacks (AWS)

```
AWS CloudHSM attack surface:
- PKCS#11 interface exposed to application
- Key extraction via weak IAM policies
- Session token capture from running applications
- Command injection via malformed PKCS#11 calls

Attack chain:
1. Enumerate PKCS#11 endpoints and session state
2. Attempt to extract key material via C_FindObjects
3. If application has excessive HSM permissions: extract keys
4. Use extracted keys for transaction signing

Protection: Strict IAM policies, short-lived sessions, application isolation
```

## Firmware Extraction

```
Physical HSM attack:
1. Identify JTAG/SWD pins on PCB
2. Connect logic analyzer
3. Extract firmware during boot
4. Analyze for:
   - Hardcoded keys
   - Backdoor commands
   - Weak crypto implementations
   - Default credentials

Common targets:
- PayShield JTAG exposed on early revisions
- Serial console with root access on legacy HSMs
```

## Testing Checklist

```
[ ] HSM management interface identified (SSH/serial/HTTP)
[ ] Port scan confirms HSM exposure
[ ] Default credentials tested (manufacturer defaults)
[ ] Key exchange (0800) captured and analyzed
[ ] Key derivation pattern identified
[ ] PIN block format tested (ISO9564-1 oracle)
[ ] MAC replay tested
[ ] MAC generation bypass attempted (if access obtained)
[ ] Algorithm downgrade tested (DES vs 3DES)
[ ] Terminal key extraction attempted (if terminal access)
[ ] Cloud HSM PKCS#11 permissions enumerated
[ ] Firmware extraction attempted (if physical access)
```

## Evidence Preservation

- Full HSO message capture for all key exchanges
- Screenshot of HSM management interface
- PCAP of all HSM commands during engagement
- Hash of any extracted firmware