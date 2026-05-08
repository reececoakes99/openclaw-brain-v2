# POS Protocols Reference

POS terminal integration covers three main protocol families: **SPDH**, **HPDH**, and **Verifone**. These are used for terminal-to-acquirer communication over TCP/IP.

## SPDH — Standard Protocol Data Highway

SPDH (also known as HPDH base) is a message-based protocol used by Verifone, Ingenico, and other terminal manufacturers. Messages are sent over TCP/IP (typically port 4001 or 5001).

### SPDH Message Structure

```
+----------------+----------------+----------------+
|  HEADER (10B) |  MESSAGE LEN (4B) |  MSG TYPE (4B)  |
+----------------+----------------+----------------+
|  DATA (variable)           |  TRAILER (2B EDC |
+----------------------------+-----------------+
```

**Header (10 bytes):**
- `STX` = 0x02 (1B)
- Source ID = terminal ID (4B)
- Destination ID = host ID (4B)
- Message Length (4B, big-endian, excludes header/trailer)
- Message Type (4B)
- Data (LEN bytes)
- TRAILER = LRC (1B) or CRC-16 (2B)

**Common SPDH Message Types:**
| Type | Name | Description |
|------|------|-------------|
| 0100 | Financial Request | Authorization / sale |
| 0120 | Financial Response | Authorization response |
| 0200 | Configuration Request | Terminal config download |
| 0220 | Configuration Response | Config data |
| 0300 | Key Exchange Request | Key loading |
| 0320 | Key Exchange Response | Key confirmation |
| 0400 | Status Request | Heartbeat / status |
| 0420 | Status Response | Host acknowledgement |
| 0500 | Reversal Request | Void / reversal |
| 0520 | Reversal Response | Reversal acknowledged |
| 0600 | Completion | Transaction completion |
| 0700 | Download Request | Firmware/app download |
| 0720 | Download Response | Download block |

### SPDH Key Exchange (Type 0300/0320)

```
Terminal → Host: Type 0300
  Data: [KeyType(1)] [EncryptedKeyData(8/16)]
  
Host → Terminal: Type 0320
  Data: [Status(1)] [MAC(4)]
```

**Key Types:**
- `01` = MAC key (ZMK component)
- `02` = PIN key (TPK/PIK)
- `03` = Encryption key (DEK)
- `04` = Transport key (TMK → working keys)

## HPDH — High Performance Data Highway

HPDH is an enhanced version of SPDH with higher throughput and additional features — longer messages, faster heartbeats, support for multiple transactions per connection.

### HPDH vs SPDH Differences

| Feature | SPDH | HPDH |
|---------|------|------|
| Max message size | 64KB | 512KB |
| Compression | No | Optional |
| Multi-txn per connection | No | Yes |
| Heartbeat interval | 60s | 30s |
| Session keys | Single | Multiple simultaneous |
| Encryption | TDES | TDES/AES-128/AES-256 |
| Protocol version field | No | Yes (v2+) |

### HPDH Header (Extended)

```
| STX(1) | VERSION(1) | FLAGS(1) | MSG_TYPE(2) | SEQ_NO(2) |
| SRC_ID(4) | DST_ID(4) | MSG_LEN(4) | TIMESTAMP(4) |
| DATA(variable) | TRAILER(2) |
```

**FLAGS byte:**
- bit 7 = compressed
- bit 6 = encrypted
- bit 5 = multi-part
- bit 4 = acknowledgment required
- bit 0-3 = protocol minor version

## Verifone XFlow Protocol

Verifone terminals support **XFlow** — a POSIX-based message protocol over TCP. XFlow uses a structured binary format with XML payloads in ISO-8859-1.

### Verifone XFlow Message

```
TCP CONNECT on port 443 or 4433 (TLS)
│
├─ Greeting: XFlow/2.1 {TERMINAL_ID}
│
├─ Handshake (TLS upgrade)
│
├─ Send Transaction Request:
│  POST /v2/transaction HTTP/1.1
│  Host: acquirer.example.com
│  Content-Type: application/xml
│
│  <?xml version="1.0" encoding="ISO-8859-1"?>
│  <XFlow version="2.1">
│    <TransactionRq>
│      <MerchantId>MERCH001</MerchantId>
│      <TerminalId>TERM001</TerminalId>
│      <TransactionType>sale</TransactionType>
│      <Amount>10000</Amount>
│      <Currency>EUR</Currency>
│      <PAN>4111111111111111</PAN>
│      <ExpDateMonth>12</ExpDateMonth>
│      <ExpDateYear>28</ExpDateYear>
│      <Track2>...</Track2>
│      <PIN>...</PIN>
│    </TransactionRq>
│  </XFlow>
│
└─ Receive Response:
   HTTP/1.1 200 OK
   <?xml version="1.0"?>
   <XFlow version="2.1">
     <TransactionRs>
       <Status>approved</Status>
       <AuthCode>123456</AuthCode>
       <RRN>987654321</RRN>
       <ResponseCode>00</ResponseCode>
     </TransactionRs>
   </XFlow>
```

### Verifone TEP (Terminal Exchange Protocol)

For legacy Verifone terminals without full IP capability:
- Dial-up fallback (V.22bis modem)
- Dial-up over TCP bridge
- Batch upload via FTP

## POS Message Mapping to ISO8583

Terminals send SPDH/HPDH → Neopay converts to ISO8583 internally:

| SPDH/HPDH Field | ISO8583 Field | Content |
|----------------|--------------|---------|
| Terminal ID | 41 | Card Acceptor Terminal ID |
| Merchant ID | 42 | Card Acceptor ID |
| Transaction Amount | 4 | Transaction Amount |
| Currency | 49 | Currency Code |
| Card Number / Track | 2 / 35 | PAN / Track 2 |
| PIN | 52 | PIN Block (ISO9564) |
| Auth Code (response) | 38 | Authorization ID |
| RRN | 37 | Retrieval Reference Number |
| Response Code | 39 | Action Code |
| STAN | 11 | System Trace Audit Number |
| Date/Time | 7 | Transmission Date/Time |
| MCC | 18 | Merchant Type Code |

## Terminal Configuration Scripts

Terminals are configured via **Script scripting** — configuration scripts sent from host to terminal.

### Script Types

```
SCRIPT TYPE 0x01 — Terminal Configuration
  Set parameter: parameter_id, value
  
SCRIPT TYPE 0x02 — Merchant Configuration  
  Set merchant name, address, ID
  
SCRIPT TYPE 0x03 — Key Loading
  Inject ZMK/TMK/WK via HSM-encrypted transport
  
SCRIPT TYPE 0x04 — Blacklist Update
  Update card blacklist / hotlist
  
SCRIPT TYPE 0x05 — Firmware Download
  Block-by-block firmware push
  
SCRIPT TYPE 0x06 — Application Load
  Push payment applet to terminal
```

### Script Example (Configuration)

```java
// Neopay terminal script language (TSL) example
SCRIPT ID="CONF001" VERSION="2.1"

// Network settings
SET NETWORK.DHCP = TRUE
SET NETWORK.IP = "192.168.1.100"
SET NETWORK.MASK = "255.255.255.0"
SET NETWORK.GATEWAY = "192.168.1.1"
SET NETWORK.DNS1 = "8.8.8.8"
SET NETWORK.DNS2 = "8.8.4.4"

// Acquirer host settings
SET HOST.IP = "acquirer.neopay.io"
SET HOST.PORT = 4001
SET HOST.PROTOCOL = "HPDH"
SET HOST.TIMEOUT = 60
SET HOST.RETRY = 3

// Security settings
SET SEC.MAC_ALGO = "ISO9797M1"
SET SEC.PIN_ALGO = "ISO9564F0"
SET SEC.KEY_TYPE = "TDES"
SET SEC.MAC_WINDOW = 1

// Transaction settings
SET TXN.CURRENCY = "EUR"
SET TXN.COUNTRY = "LT"
SET TXN.TIP_PROCESSING = TRUE
SET TXN.CASHBACK_MAX = 20000
SET TXN.REFUND_ENABLED = TRUE

// Feature flags
ENABLE contactless
ENABLE contact
ENABLE cashback
DISABLE tip_adjustment
```

## Terminal Applet Scripting (Java-based POS)

Neopay terminals run a **Java applet** (Java Card / Multos) for EMV processing:

### Applet Lifecycle

```
LOAD    → INSTALL → SELECT → INITIALIZE → PROCESS → (loop) → TERMINATE → DELETE
           │                      ↑
           │                      └── Applet receives APDU commands
           └── Terminal personalization (keys, AIDs, config)
```

### APDU Command Structure (EMV)

```java
// CLA INS P1 P2 Lc [data] [Le]
// Example: SELECT PSE
byte[] selectPSE = {
    0x00, 0xA4, 0x04, 0x00,  // CLA=00, INS=A4, P1=04, P2=00
    0x0E,                     // Lc = 14 bytes
    0x31, 0x50, 0x41, 0x59,  // "1PAY"
    0x2E, 0x53, 0x59, 0x53,  // ".SYS"
    0x2E, 0x44, 0x44, 0x46,  // ".DDF"
    0x31,                     // 1 (directory entry)
    0x00                      // Le = 0 (no expected response)
};
```
