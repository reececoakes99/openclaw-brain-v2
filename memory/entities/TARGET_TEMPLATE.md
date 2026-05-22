# Target Intel Template

Create one file per target: `memory/entities/<target-domain>/TARGET.md`

```markdown
# <Target Domain>

## Basic Info
- **Discovered:** YYYY-MM-DD
- **First Contact:** YYYY-MM-DD
- **Last Active:** YYYY-MM-DD
- **Campaign Status:** ACTIVE | ARCHIVED | MONITORING

## Infrastructure
- **Primary IP:** x.x.x.x
- **ASN:** ASxxxxx
- **Cloud Provider:** AWS | GCP | Azure | On-prem | Unknown
- **CDN/WAF:** Cloudflare | Imperva | Akamai | None
- **Open Ports:** [list]

## Technology Stack
- **Frontend:** [framework, version]
- **Backend:** [language, framework, version]
- **Database:** [type, version]
- **Payment Processor:** Stripe | Braintree | Custom | Other

## Payment Infrastructure
- **Protocol:** ISO8583 (HISO93/HISO87) | REST API | GraphQL | Custom
- **Token Format:** [UUID/MD5/custom]
- **Checkout Flow:** [description]
- **Webhook Endpoint:** yes/no

## Findings
| Date | Finding | Severity | Status |
|------|---------|----------|--------|
| YYYY-MM-DD | [description] | CRITICAL/HIGH/MEDIUM/LOW | Open/Closed |

## Attack Vectors
1. [Primary vector]
2. [Secondary vector]

## Engagement History
- **Sessions:** N
- **Last Session:** YYYY-MM-DD
- **Access Level:** None | API Only | Low | Admin | Full

## Notes
[Observations, countermeasures, operator notes]
```

Update after every interaction.