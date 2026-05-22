# Token Vault Extraction Procedures

## Overview

Token vaults replace raw PANs with non-sensitive tokens. Cracking the vault = mapping tokens back to real card numbers = full card data compromise.

## Vault Architecture

```
Token vault structure:
├── Token → PAN mapping table (encrypted at rest)
├── Encryption keys (master key + per-merchant keys)
├── Access controls (which app can request detokenization)
├── Audit log (who accessed what)
└── API interface (REST/gRPC for detokenization)

Common deployments:
- Stripe: stripe.com → tok_xxx format, managed cloud vault
- Braintree: braintreegateway.com → nonce-based, own vault
- Adyen: adyen.com → PSP reference, own vault
- Custom: merchant-built vault, variable security
```

## Attack Vectors

### 1. Token Enumeration

```
Vulnerability: Tokens follow predictable pattern, easily enumerated.

Pattern analysis:
- Stripe: tok_a-z + 24 chars (base62), sequential in some ranges
- Braintree: nonces follow pattern, predictable generation
- Custom: depends on implementation (UUID v4 = predictable)

Attack:
1. Enumerate token IDs systematically
   for i in {000000..999999}; do
     check /api/token/tok_xxx$i
   done
   
2. Map token → account by observing:
   - Response time (token exists vs 404)
   - Error message differences
   - Rate limiting patterns

3. Build token → account map across multiple merchants
```

### 2. Token Correlation Across Merchants

```
Vulnerability: Same card produces same token across merchants using same vault.

Attack:
1. Tokenize known card on Merchant A → TokenA
2. Submit TokenA to Merchant B (same processor)
3. If Merchant B accepts TokenA:
   - Merchant B processed payment for attacker's card
   - Attacker's card was charged (self-fraud)
   - OR: token mapped back → card number confirmed

Correlation test:
1. Get token on Merchant A
2. Use token on Merchant B
3. If payment succeeds → same vault → token correlation confirmed
```

### 3. Token → PAN Oracle

```
Vulnerability: Some vault implementations expose token metadata or allow partial PAN retrieval.

A. Token metadata exposure
   GET /api/tokens/tok_xxx
   Response may contain:
   - card_type: Visa, MC
   - last4: 4242
   - exp_month, exp_year
   → Build card database from token alone

B. Partial PAN via card brand lookup
   - Submit token to Visa/MC verification service
   - Service returns: card valid/invalid, card type, issuing bank
   → Cardinal/3DS verification endpoints expose card status

C. Token self-verification
   - Some vaults allow token → PAN via verification endpoint
   - Requires: token + CVV or OTP
   - If CVV known: full PAN retrieved
```

### 4. Vault Key Extraction

```
Vulnerability: Custom vault implementations store encryption keys improperly.

Attack:
1. Identify vault API endpoint
2. Test for command injection: /api/detokenize?token=xxx&key=yyy
3. Look for admin/debug endpoints: /vault/admin, /debug/token
4. If vault runs on-premises (merchant-hosted):
   - Extract from config files: /etc/vault/config.json
   - Extract from database: encryption keys in key_table
   - Memory dump during detokenization request

Key extraction from database:
SELECT master_key FROM encryption_keys WHERE key_id = 'master';
→ Decrypt all tokens in vault with extracted master key
```

### 5. Vault API Authentication Bypass

```
Vulnerability: Vault API enforces weak auth, easily bypassed.

A. API key in client-side code
   - Extract API key from merchant checkout JS
   - Use key directly against vault API
   - Request detokenization for any token

B. IP whitelist bypass
   - Vault restricts detokenization to known IPs
   - Bypass: compromise one whitelisted server (merchant server)
   - Use merchant server to call vault

C. HMAC signature bypass
   - Capture valid API request + HMAC
   - Replay request with different token
   - If HMAC verified client-side (not server): token → PAN
```

### 6. Session Token Theft

```
Vulnerability: Vault session tokens are stored in memory or logged insecurely.

Attack:
1. SQL injection in vault query log
   SELECT token, pan FROM detokenize_log WHERE timestamp > ...
   
2. Memory dump during detokenization
   - Capture running process memory
   - Extract: plaintext tokens, session keys, master key

3. Log file exposure
   - Vault logs detokenization requests to file
   - File accessible via: /logs/vault.log, admin panel
   - Contains: token → PAN mapping in plaintext
```

### 7. PCI-DSS Token Vault Weakness

```
Vulnerability: PCI-DSS compliance creates false sense of security.

PCI-DSS allows tokenization as long as:
- Token ≠ PAN
- Vault isolated from merchant network

Bypass:
1. If vault admin panel exposed → full token access
2. If vault runs on merchant server (not separate) → key extraction
3. If token generated from predictable data → reverse engineer
4. If token = encrypted PAN (weak key) → decrypt with extracted key
```

## Testing Checklist

```
[ ] Token enumeration tested (range + pattern analysis)
[ ] Cross-merchant token correlation tested
[ ] Token metadata endpoint tested
[ ] Brand verification API tested (3DS lookup)
[ ] Vault debug/admin endpoints enumerated
[ ] Vault key extraction attempted (config, database, memory)
[ ] API key extraction from client code
[ ] IP whitelist bypass attempted
[ ] HMAC signature replay tested
[ ] SQL injection in vault logs tested
[ ] Memory dump during detokenization attempted
[ ] Log file exposure tested (path enumeration)
[ ] Vault admin panel tested (default creds, auth bypass)
```

## Exfiltration

```
Token vault exfil method:
1. Gain vault access (API key, admin panel, or key extraction)
2. Bulk detokenize: SELECT token FROM cards → detokenize(token)
3. Map all tokens → PANs
4. Export: card_number|expiry|cvv|name|address@attacker.com
5. Clean exit: cover tracks in vault audit log
```

## Evidence Preservation

- Screenshot of token enumeration results
- PCAP of vault API calls
- Hash of extracted keys
- Screenshot of detokenized card data