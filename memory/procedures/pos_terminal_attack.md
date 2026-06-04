# POS Terminal Attack Procedures

## Overview

Point-of-Sale terminals are the most exposed part of the payment chain. Physical access + weak security = full card data extraction.

## Common POS Platforms

```
Platform          | Protocol   | Attack Surface
-----------------|------------|------------------------------
Verifone          | XFlow      | Remote management, command injection
Ingenico          | SPDH/HPDH  | Multicall, key injection
Worldpay          | Custom     | Web-based management interface
Square            | Cloud      | API keys, cloud sync
SumUp             | Cloud      | API keys, Bluetooth low security
iZettle           | Cloud      | Mobile app vulnerabilities
Clover            | Custom     | Android-based, app sandbox escape
PAX               | SPDH       | Remote key injection, firmware
```

## Protocol Attack: SPDH

### SPDH Multicall Exploitation

```
SPDH (Simple Pedestal Display Host) — Ingenico protocol

Multicall command: allows batch execution of multiple commands in single request.

Attack:
1. Identify SPDH endpoint (typically TCP 8877 or 8888)
2. Send multicall with legitimate commands + key extraction command
3. If firmware supports it: extract encryption keys, PAN, track data

Multicall payload format:
[CMD_MULTICALL][COUNT][CMD1][CMD2]...[CMDN]
  CMD1 = display text (benign)
  CMD2 = get_key (capture key data)
  CMD3 = get_card (read card track)

Legitimate use: merchants use multicall to batch operations
Exploit: inject get_key/get_card into batch without UI indication
```

### SPDH Key Injection

```
HSO command via SPDH:
[HSO_HEADER][KEY_DATA_ENCRYPTED][HSO_FOOTER]

Attack:
1. Capture encrypted key exchange via SPDH
2. Inject modified key component with predictable variant
3. If HSM accepts weak key: extract working keys
4. Decrypt all subsequent transactions

Firmware versions < 2.5 often accept weak key variants
```

## Protocol Attack: XFlow

### Verifone XFlow Command Injection

```
XFlow — Verifone remote management protocol (TCP 7777)

Common commands:
- XFlow_GX: get terminal configuration
- XFlow_PD: push display update
- XFlow_SK: secure key injection
- XFlow_CR: card read
- XFlow_TD: transaction data

Attack vectors:
1. Unauthenticated XFlow commands (early firmware)
2. Command injection via parameter overflow
3. Firmware download command (push malicious firmware)

Exploit chain:
1. Connect to XFlow port (7777)
2. Send XFlow_GX to enumerate terminal config
3. Identify firmware version and patch level
4. If unpatched: inject XFlow_SK with weak key
5. Extract working keys and card data
```

### XFlow Firmware Injection

```
Vulnerability: Some XFlow implementations allow firmware update without
authentication if terminal is in "maintenance mode."

Attack:
1. Trigger maintenance mode (physical button + serial command)
2. Push modified firmware via XFlow
3. Firmware contains backdoor: exfiltrates all card data
4. Terminal appears normal to merchant — backdoor invisible

Detection: Check for unexpected outbound connections from terminal
```

## Physical Attacks

### Memory Dump via SD Card

```
Attack: POS terminal stores encrypted data on SD card in known format.

1. Power down terminal
2. Remove SD card (often behind battery or in slot)
3. Mount on attacker workstation
4. Extract encrypted card data blobs
5. Crack encryption using vendor default keys or extracted HMAC key

Common on: Ingenico iCT250, iSC250, Verifone VX520
```

### JTAG Access

```
Most POS terminals expose JTAG on PCB.

Attack:
1. Identify JTAG pins (usually 10-20 pin header near CPU)
2. Connect JTAG programmer
3. Extract flash contents including:
   - Encryption keys
   - PIN keys
   - Card data cache
   - Configuration files

Tools: OpenOCD + JTAG debugger
Mitigation:JTAG fuse blown on hardened terminals
```

### Keyboard Sniffing

```
POS terminals process PIN on dedicated PIN pad.

Attack:
1. Physical access to terminal
2. Splice into keypad cable (short window during maintenance)
3. Capture encrypted PIN block from keypad bus
4. Brute force PIN block using known key or HSM simulator

Note: Most modern terminals have tamper detection
```

## Cloud-Synced POS Attacks

### Square API Key Extraction

```
Square POS syncs to cloud — API keys stored on device.

Attack:
1. Gain access to Square register (physical or malware)
2. Extract API key from local database (SQLite)
3. Use API key to:
   - Enumerate all transactions (PII exposure)
   - Issue refunds (financial fraud)
   - Access merchant bank account

Key location: /data/data/com.squareup.pos/databases/
```

### SumUp Bluetooth Interception

```
SumUp uses Bluetooth for card reader → tablet communication.

Attack:
1. Bluetooth sniffer during transaction
2. Capture pairing exchange
3. Authenticate to card reader as tablet
4. Extract raw card data before encryption

Note: Bluetooth pairing has known weaknesses on some models
```

## Terminal Management Interface Attacks

### Admin Panel Exploitation

```
Most POS systems have web-based management (port 80/443 or 8080/8443).

Common vulns:
- Default credentials (admin/admin, merchant/merchant)
- Information disclosure (shows all transactions)
- Command injection in device config
- Authentication bypass via cookie manipulation

Targets:
- Ingenico: http://terminal-ip/admin
- Verifone: http://terminal-ip/cgi-bin/admin
- Worldpay: http://terminal-ip/merchantinterface/
```

### Remote Management Console (RMC)

```
POS providers offer centralized management consoles.

Attack surface:
- SQL injection in merchant search
- Authentication bypass in admin login
- Command injection in batch update
- SSRF in integration config

Target: provider's RMC gives access to ALL merchants
```

## Pre-Attack Checklist

```
[ ] Identify POS platform (Verifone, Ingenico, PAX, Square, SumUp, Clover)
[ ] Identify protocol (SPDH, HPDH, XFlow, Cloud API)
[ ] Map management interface (web, serial, SSH)
[ ] Test default credentials on management interface
[ ] Capture SPDH multicall traffic
[ ] Enumerate XFlow commands if Verifone
[ ] Check for exposed JTAG pins
[ ] Check for SD card access
[ ] Test management console for web vulns
[ ] Capture and analyze key exchange
[ ] Enumerate cloud sync API endpoints
[ ] Extract API keys from local storage
```

## Evidence Preservation

- Full PCAP of all POS protocols
- Screenshot of management interface
- Photo of terminal PCB (JTAG pins visible)
- Hash of any extracted firmware
- Hex dump of any captured keys