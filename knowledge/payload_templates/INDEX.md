# Payload Template Index

All available attack payloads organized by category.

## Categories

| Category | Path | Description |
|----------|------|-------------|
| ISO8583 | `iso8583/` | Message injection, fuzzing, MAC bypass |
| Web | `web/` | XSS, SQLi, command injection, SSRF |
| API | `api/` | REST fuzzing, GraphQL attacks, webhook replay |
| HSM | `hsm/` | PIN block, MAC forgery, key extraction |
| POS | `pos/` | SPDH multicall, terminal commands |
| Checkout | `checkout/` | Price manipulation, token theft |

## Adding Payloads

1. Test in experiment mode first
2. Document: target type, conditions, expected result
3. Save to appropriate category
4. Update this index
