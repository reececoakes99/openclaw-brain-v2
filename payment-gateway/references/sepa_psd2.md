# SEPA / PSD2 Open Banking

## PSD2 Regulatory Framework

PSD2 (Payment Services Directive 2 — EU 2015/2366) mandates open banking APIs across EEA.

### Key Rights Under PSD2

| Right | Description |
|-------|-------------|
| **AISP** | Account Information Service — read account data, balances, transactions |
| **PISP** | Payment Initiation Service — initiate payments from customer's account |
| **CISP** | Card Issuing Service — not widely implemented |

### Exemptions

| Scenario | Exemption | Notes |
|----------|-----------|-------|
| < €30 + 5 reqs/day | Low-value payment | No SCA |
| Recurring same amount/amount | Recurring payment | First payment needs SCA |
| Contactless < €50 (cumulative < €150) | Low value | Must fall back after limits |
| Trusted beneficiary | Whitelist | No SCA required |

## AISP Flow

```
User → PSP → ASPSP (Bank)
          │
          ├── /accounts          → List user's accounts
          ├── /accounts/{id}     → Account details
          ├── /accounts/{id}/balances → Current balance
          ├── /accounts/{id}/transactions → Transaction history
          └── /accounts/{id}/standing-orders → Scheduled payments

ASPSP Response → PSP → User (via dashboard/API)
```

### AISP API Example (Berlin Group NextGenPSD2)
```python
# Step 1: PSU (Payment Service User) consents via redirect
# The PSU is redirected to the ASPSP's consent page

# Step 2: After consent, get access token
def get_account_token(aspsp: str, auth_code: str) -> Token:
    return requests.post(f"{aspsp}/oauth/token", data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })

# Step 3: List accounts
def list_accounts(token: str) -> list[Account]:
    resp = requests.get(
        f"{ASPSP}/v1/accounts",
        headers={"Authorization": f"Bearer {token.access_token}",
                 "X-Request-ID": uuid4(),
                 "Consent-ID": token.consent_id}
    )
    return resp.json()["accounts"]

# Step 4: Get transactions
def get_transactions(account_id: str, token: str) -> list[Transaction]:
    resp = requests.get(
        f"{ASPSP}/v1/accounts/{account_id}/transactions",
        headers={"Authorization": f"Bearer {token.access_token}",
                 "Consent-ID": token.consent_id},
        params={"dateFrom": "2024-01-01", "dateTo": "2024-12-31"}
    )
    return resp.json()["transactions"]
```

## PISP Flow — Payment Initiation

```
1. PSU selects PISP to initiate payment
2. PISP → ASPSP: POST /v1/payments/sepa
   { amount: "100.00", currency: "EUR", creditor_iban: "DE89370400440532013000" }
3. ASPSP: Redirect PSU to consent page (redirect)
4. PSU authenticates with ASPSP (SCA)
5. ASPSP: Returns redirect to PISP with authorization result
6. PISP → ASPSP: GET /v1/payments/{paymentId}/status (poll or webhook)
7. ASPSP: Payment executes; webhooks notify PISP of status changes
```

### PISP API Example
```python
class PISPClient:
    def initiate_payment(self, 
                         aspsp_id: str,
                         amount: Decimal,
                         creditor_iban: str,
                         creditor_name: str,
                         remittance: str) -> PaymentInitiation:
        
        # Check ASPSP supports SEPA SCT
        aspsp = self.aspsp_registry.get(aspsp_id)
        if "sepa_sct" not in aspsp.services:
            raise UnsupportedService(f"ASPSP {aspsp_id} doesn't support SEPA SCT")
        
        payload = {
            "instructedAmount": {
                "amount": str(amount),
                "currency": "EUR"
            },
            "debtorAccount": {
                "iban": None  # Filled by PSU at ASPSP
            },
            "creditorAccount": {
                "iban": creditor_iban,
                "name": creditor_name
            },
            "remittanceInformationUnstructured": remittance,
            "requestedExecutionDate": date.today().isoformat()
        }
        
        resp = self.session.post(
            f"{aspsp.api_url}/v1/payments/sepa-credit-transfers",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Request-ID": str(uuid4()),
                "Consent-ID": self.consent_id,
                "PSU-ID": self.psu_id
            }
        )
        
        payment_id = resp.headers["Location"].split("/")[-1]
        
        return PaymentInitiation(
            payment_id=payment_id,
            status="RCVD",  # Received
            aspsp_redirect_url=resp.json()["scaRedirect"]["redirect"]
        )
    
    def poll_payment_status(self, payment_id: str) -> PaymentStatus:
        resp = self.session.get(
            f"{self.aspsp_url}/v1/payments/sepa-credit-transfers/{payment_id}",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        return PaymentStatus(**resp.json())

# Webhook handler for status updates
def handle_payment_status_webhook(payload: dict):
    payment_id = payload["paymentId"]
    status = payload["status"]  # ACSC=AcceptedSettled, ACSP=Accepted, RJCT=Rejected
    
    payment = Payment.objects.get(neopay_id=payment_id)
    payment.psp_status = status
    payment.save()
    
    if status == "ACSC":
        payment.complete()
        send_webhook_to_merchant(payment.merchant, payment)
    elif status == "RJCT":
        payment.fail(reason=payload.get("rejectReason"))
        send_webhook_to_merchant(payment.merchant, payment)
```

## ISO 20022 (MX Messages)

### pacs.008 — FIToFICustomerCreditTransfer
SEPA Credit Transfer message (SCT):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:20022:tech:xsd:pacs.008.001.02">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>MSG-2024-001234</MsgId>
      <CreDtTm>2024-05-05T10:30:00</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf>
        <SttlmMtd>CLRG</SttlmMtd>
        <ClrSys>
          <Cd>SEPA</Cd>
        </ClrSys>
      </SttlmInf>
      <InstgAgt>
        <FinInstnId>
          <Othr><Id>NEOPAYXXX</Id></Othr>
        </FinInstnId>
      </InstgAgt>
      <InstdAgt>
        <FinInstnId>
          <Othr><Id>BANKDEXXX</Id></Othr>
        </FinInstnId>
      </InstdAgt>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>INSTR-001</InstrId>
        <EndToEndId>E2E-MERCH-12345</EndToEndId>
      </PmtId>
      <Amt>
        <InstdAmt>
          <Amt W="125.00" Ccy="EUR"/>
        </InstdAmt>
      </Amt>
      <CdtrAcct>
        <Id><IBAN>DE89370400440532013000</IBAN></Id>
      </CdtrAcct>
      <CdtrAgt>
        <FinInstnId>
          <Othr><Id>DEUTDEFF</Id></Othr>
        </FinInstnId>
      </CdtrAgt>
      <RmtInf>
        <Ustrd>Invoice #12345</Ustrd>
      </RmtInf>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>
```

### pain.001 — CustomerCreditTransferInitiation (Outbound)
Used to initiate batch SEPA payments:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <PmtInf>
      <PmtInfId>BATCH-2024-001</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <NbOfTxs>3</NbOfTxs>
      <CtrlSum>500.00</CtrlSum>
      <PmtTpInf>
        <SvcLvl>
          <Cd>SEPA</Cd>
        </SvcLvl>
      </PmtTpInf>
      <ReqdExctnDt>2024-05-07</ReqdExctnDt>
      <Dbtr>
        <Nm>Neopay Ltd</Nm>
        <PstlAdr>
          <Ctry>IE</Ctry>
          <AdrLine>Dublin 1</AdrLine>
        </PstlAdr>
      </Dbtr>
      <DbtrAcct>
        <Id><IBAN>IE86IRDX12345678901234</IBAN></Id>
      </DbtrAcct>
      <DbtrAgt>
        <FinInstnId><Othr><Id>IRISXXXX</Id></Othr></FinInstnId>
      </DbtrAgt>
      <ChrgBr>SLEV</ChrgBr>  <!-- SHA: shared charges -->
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>
```

### pain.002 — BankStatementReport
Statement / status report from bank:
```xml
<pain.002.001.03>
  <StsRpt>
    <OrgnlGrpInfAndSts>
      <OrgnlMsgId>BATCH-2024-001</OrgnlMsgId>
      <OrgnlMsgNmId>pain.001.001.03</OrgnlMsgNmId>
      <StsGrpInf>
        <Sts>ACCP</Sts>  <!-- Accepted -->
        <NbOfTxs>3</NbOfTxs>
        <CtrlSum>500.00</CtrlSum>
      </StsGrpInf>
    </OrgnlGrpInfAndSts>
  </StsRpt>
</pain.002.001.03>
```

### camt.053 — BankToCustomerAccountReport
Account statement:
```xml
<Document xmlns="urn:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt>
    <Stmt>
      <Acct>
        <Id><IBAN>DE89370400440532013000</IBAN></Id>
      </Acct>
      <Bal>
        <Tp><Cd>CLBD</Cd></Tp>
        <Amt W="10000.00" Ccy="EUR"/>
      </Bal>
      <Ntry>
        <Amt W="125.00" Ccy="EUR"/>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <BookgDt>2024-05-05</BookgDt>
        <NtryRef>REF-12345</NtryRef>
        <BkTxCd><Domn><Cd>SEPA</Cd></Domn></BkTxCd>
        <NtryDtls>
          <Refs><EndToEndId>E2E-MERCH-12345</EndToEndId></Refs>
          <RmtInf><Ustrd>Invoice #12345</Ustrd></RmtInf>
        </NtryDtls>
      </Ntry>
    </Stmt>
  </BkToCstmrStmt>
</Document>
```

## SEPA Instant (SCT Inst)

Settlement in < 10 seconds, 24/7/365.

### SCT vs SCT Inst Comparison

| Feature | SEPA CT (SCT) | SEPA Instant (SCT Inst) |
|---------|---------------|----------------------|
| Settlement | D+1 (next business day) | < 10 seconds |
| Availability | Business days | 24/7/365 |
| Amount limit | None | Max €100,000 (configurable per ASPSP) |
| Cost | Lower | Higher (interchange) |
| Refund | Not automatic | Not automatic |

### SCT Inst Flow
```python
def initiate_sepa_instant(amount: Decimal, 
                          creditor_iban: str,
                          creditor_bic: str) -> InstantPayment:
    
    payload = {
        "instructedAmount": {"amount": str(amount), "currency": "EUR"},
        "creditorAccount": {"iban": creditor_iban},
        "creditorAgent": {"bicfi": creditor_bic},
        "remittanceInformationUnstructured": "Payment",
        "requestedExecutionDate": "2024-05-05"
    }
    
    resp = requests.post(
        f"{ASPSP_URL}/v1/payments/sepa-instant-credit-transfers",
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Request-ID": str(uuid4()),
            "Idempotency-Key": idempotency_key
        }
    )
    
    # Poll for immediate settlement confirmation
    payment_id = resp.json()["paymentId"]
    for attempt in range(10):
        status = check_status(payment_id)
        if status == "ACSC":
            return InstantPayment(success=True, settlement_time=status.timestamp)
        elif status in ("RJCT", "PDNG"):
            return InstantPayment(success=False, reason=status.reason)
        sleep(1)
```

## Open Banking Architecture

```python
# Neopay Open Banking Gateway
class OpenBankingGateway:
    
    def __init__(self):
        self.aspsp_registry = ASPSPRegistry()  # Bank configs
        self.consent_store = ConsentStore()      # PSU consents
        self.token_vault = TokenVault()           # AISP/PISP access tokens
    
    def register_pisp(self, pisp_id: str, public_key: bytes):
        """Register a PISP client for open banking."""
        # Store public key for request signing
        self.pisp_registry[pisp_id] = {
            "public_key": public_key,
            "qtsp_certificate": load_qtsp_cert(pisp_id),
            "capabilities": ["sepa_sct", "sepa_sct_inst", "sepa_sdd"]
        }
    
    def initiate_psd2_consent(self, 
                               aspsp_id: str, 
                               psu_id: str,
                               scopes: list[str]) -> ConsentRequest:
        """Create consent object at ASPSP."""
        aspsp = self.aspsp_registry.get(aspsp_id)
        
        consent = self.consent_store.create(
            psu_id=psu_id,
            aspsp_id=aspsp_id,
            scopes=scopes,  # ["accounts", "balances", "transactions"]
            expiration=timedelta(days=90)
        )
        
        # Build redirect to ASPSP consent page
        redirect_url = build_consent_redirect(
            aspsp.consent_url,
            consent_id=consent.id,
            redirect_uri=self.callback_url,
            scope=" ".join(scopes),
            state=consent.state
        )
        
        return ConsentRequest(redirect_url=redirect_url, consent_id=consent.id)
    
    def execute_pisp_payment(self, payment: Payment) -> PISPResult:
        """Execute payment via PISP."""
        aspsp = self.aspsp_registry.get(payment.aspsp_id)
        access_token = self.token_vault.get_token(payment.psu_id, aspsp_id)
        
        # Build ISO20022 pacs.008
        mx_message = build_pacs008(
            amount=payment.amount,
            creditor_iban=payment.creditor_iban,
            creditor_name=payment.creditor_name,
            end_to_end_id=payment.id
        )
        
        resp = requests.post(
            f"{aspsp.api_url}/v1/payments/sepa-credit-transfers",
            json=mx_message,
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Request-ID": str(uuid4()),
                "PSU-ID": payment.psu_id,
                "Idempotency-Key": payment.idempotency_key
            }
        )
        
        return PISPResult(
            psp_payment_id=extract_payment_id(resp),
            status="RCVD",
            redirect_url=resp.json().get("scaRedirect")
        )
```

## SEPA Direct Debit (SDD)

Two variants: CORE (B2C) and B2B.

```python
# Initiate SDD mandate
def create_sdd_mandate(customer_iban: str, 
                       customer_name: str,
                       creditor_iban: str,
                       mandate_id: str) -> Mandate:
    
    # Build pain.009 mandate request
    mandate_msg = build_mandate(
        creditor_iban=creditor_iban,
        debtor_iban=customer_iban,
        debtor_name=customer_name,
        mandate_id=mandate_id
    )
    
    # Submit to ASPSP
    resp = requests.post(f"{ASPSP}/v1/mandates", json=mandate_msg)
    return Mandate(mandate_id=mandate_id, status="RCVD", aspsp_mandate_id=resp["mandateId"])

# Collect SDD
def collect_sdd(mandate: Mandate, 
                amount: Decimal,
                collection_date: date) -> Collection:
    
    # Build camt.054 / pacs.004 collection request
    collection = build_sdd_collection(
        mandate_id=mandate.aspsp_id,
        amount=amount,
        collection_date=collection_date
    )
    
    resp = requests.post(f"{ASPSP}/v1/direct-debits", json=collection)
    return Collection(id=resp["id"], status="PDNG")

# Handle SDD return/rejection
def handle_sdd_return(webhook_payload: dict):
    if webhook_payload["status"] == "RJCT":
        # Bank rejected the collection (insufficient funds, mandate revoked, etc.)
        payment = Payment.objects.get(reference=webhook_payload["endToEndId"])
        payment.fail(reason=webhook_payload["rejectReason"])
        payment.refund_fees_to_merchant()
```

## Country Coverage (SEPA)

SEPA covers: AT, BE, BG, HR, CY, CZ, DK, EE, FI, FR, DE, GR, HU, IS, IE, IT, LV, LI, LT, LU, MT, MC, NL, NO, PL, PT, RO, SM, SK, SI, ES, SE, CH, GB, VA

**Note**: Post-Brexit, UK's open banking is separate (Open Banking Implementation Entity — OBIE).