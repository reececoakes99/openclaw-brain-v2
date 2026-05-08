# SEPA Payments Reference

## SEPA Schemes

| Scheme | Type | Speed | Max Amount |
|--------|------|-------|------------|
| SEPA Credit Transfer (SCT) | Credit push | T+0 to T+2 | No limit |
| SEPA Instant Credit Transfer (SCT Inst) | Credit push | <10s, 24/7 | EUR 100,000 |
| SEPA Direct Debit Core (SDD Core) | Debit pull | T+1 to T+2 | No limit |
| SEPA Direct Debit B2B (SDD B2B) | Debit pull | T+1 to T+2 | No limit |

## ISO 20022 Messages

SEPA uses ISO 20022 XML messages. Key messages:

```
pain.001.001.03   → Customer Credit Transfer Initiation (SCT)
pain.002.001.03   → Payment Status Report (SDD status)
pain.003.001.04   → Direct Debit Initiation (SDD)
camt.053.001.02   → Bank-to-Customer Cash Management (statement)
camt.054.001.02   → Bank-to-Customer Debit/Credit Notification
```

## pain.001 (Credit Transfer) — Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>MSG-20260505-001</MsgId>
      <CreDtTm>2026-05-05T22:00:00</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf>
        <SttlmMtd>CLRG</SttlmMtd>
        <ClrSys>
          <Cd>SEPA</Cd>
        </ClrSys>
      </SttlmInf>
      <PmtInf>
        <PmtMtd>TRF</PmtMtd>
        <ReqdExctnDt>2026-05-06</ReqdExctnDt>
        <Dbtr>
          <Nm>Merchant Company Ltd</Nm>
          <PstlAdr>
            <StrtNm>Main Street</StrtNm>
            <BldgNb>123</BldgNb>
            <PstCd>10115</PstCd>
            <TwnNm>Berlin</TwnNm>
            <Ctry>DE</Ctry>
          </PstlAdr>
        </Dbtr>
        <DbtrAcct>
          <Id>
            <IBAN>DE89370400440532013000</IBAN>
          </Id>
        </DbtrAcct>
        <DbtrAgt>
          <FinInstnId>
            <BIC>COBADEFFXXX</BIC>
          </FinInstnId>
        </DbtrAgt>
      </PmtInf>
      <CdtTrfTxInf>
        <PmtId>
          <InstrId>INSTR-001</InstrId>
          <EndToEndId>ORDER-12345</EndToEndId>
        </PmtId>
        <Amt>
          <InstdAmt Ccy="EUR">49.99</InstdAmt>
        </Amt>
        <CdtrAgt>
          <FinInstnId>
            <BIC>DEUTDEFFXXX</BIC>
          </FinInstnId>
        </CdtrAgt>
        <Cdtr>
          <Nm>Customer Name</Nm>
          <PstlAdr>
            <Ctry>FR</Ctry>
          </PstlAdr>
        </Cdtr>
        <CdtrAcct>
          <Id>
            <IBAN>FR7612345678901234567890123</IBAN>
          </Id>
        </CdtrAcct>
        <RmtInf>
          <Ustrd>Invoice #12345</Ustrd>
        </RmtInf>
      </CdtTrfTxInf>
    </GrpHdr>
  </CstmrCdtTrfInitn>
</Document>
```

## pain.002 (Status Report)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.002.001.03">
  <CstmrPmtStsRpt>
    <GrpHdr>
      <MsgId>RPT-20260505-001</MsgId>
      <CreDtTm>2026-05-05T22:30:00</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf>
        <SttlmMtd>CLRG</SttlmMtd>
        <ClrSys><Cd>SEPA</Cd></ClrSys>
      </SttlmInf>
    </GrpHdr>
    <OrgnlGrpInfAndSts>
      <OrgnlMsgId>MSG-20260505-001</OrgnlMsgId>
      <OrgnlMsgNmId>pain.001.001.03</OrgnlMsgNmId>
      <StsRsnInf>
        <Rsn><Cd>ACCP</Cd></Rsn>  <!-- Accepted -->
      </StsRsnInf>
    </OrgnlGrpInfAndSts>
    <OrgnlPmtInfAndSts>
      <OrgnlPmtInfId>PmtInf-001</OrgnlPmtInfId>
      <TxInfAndSts>
        <OrgnlEndToEndId>ORDER-12345</OrgnlEndToEndId>
        <TxSts>ACCP</TxSts>  <!-- Accepted -->
      </TxInfAndSts>
    </OrgnlPmtInfAndSts>
  </CstmrPmtStsRpt>
</Document>
```

## Status Codes (pain.002)

| Code | Meaning |
|------|---------|
| `ACCP` | Accepted — settlement in progress |
| `ACSC` | Accepted Settlement Completed |
| `ACSP` | Accepted Settlement Pending |
| `ACWC` | Accepted With Change (partial) |
| `ACWP` | Accepted Without Post |
| `RJCT` | Rejected |
| `PDNG` | Pending |
| `CANC` | Cancelled |

## Rejection Reasons

| Code | Meaning |
|------|---------|
| `AM04` | Insufficient funds |
| `AC01` | Invalid IBAN |
| `AC03` | Invalid BIC |
| `AC04` | Closed account |
| `AC06` | Blocked account |
| `AC13` | Invalid debtor name |
| `FF01` | Invalid format |
| `MD01` | No mandate |
| `MD02` | Invalid mandate |
| `MS02` | Refused by customer |

## Direct Debit (SDD) — pain.003

```xml
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.003.001.04">
  <CstmrDrctDbtInitn>
    <GrpHdr>
      <MsgId>DD-MSG-001</MsgId>
      <CreDtTm>2026-05-05T10:00:00</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf>
        <SttlmMtd>CLRG</SttlmMtd>
        <ClrSys><Cd>SEPA</Cd></ClrSys>
      </SttlmInf>
    </GrpHdr>
    <PmtInf>
      <PmtMtd>DD</PmtMtd>
      <SvcLvl><Cd>SEPA</Cd></SvcLvl>
      <LclInstrm><Cd>CORE</Cd></LclInstrm>  <!-- or B2B -->
      <ReqdColltnDt>2026-05-10</ReqdColltnDt>
      <CdtrAcct>
        <Id><IBAN>DE89370400440532013000</IBAN></Id>
      </CdtrAcct>
      <ChrgBr>SLEV</ChrgBr>  <!-- SHA — usually -->
    </PmtInf>
    <DrctDbtTxInf>
      <PmtId><EndToEndId>SUBSCRIPTION-001</EndToEndId></PmtId>
      <InstdAmt Ccy="EUR">49.99</InstdAmt>
      <DrctDbtTxInf>
        <MndtRltdInf>
          <MndtId>MANDATE-12345</MndtId>
          <DtOfSgntr>2026-01-01</DtOfSgntr>
          <AmdmntInd>false</AmdmntInd>
        </MndtRltdInf>
        <DbtrAgt>
          <FinInstnId><BIC>DEUTDEFFXXX</BIC></FinInstnId>
        </DbtrAgt>
        <Dbtr>
          <Nm>Customer Name</Nm>
        </Dbtr>
        <DbtrAcct>
          <Id><IBAN>FR7612345678901234567890123</IBAN></Id>
        </DbtrAcct>
      </DrctDbtTxInf>
    </DrctDbtTxInf>
  </CstmrDrctDbtInitn>
</Document>
```

## SEPA Testing

- [ ] Valid SEPA XML generation (schema validation)
- [ ] IBAN validation (length, checksum per country)
- [ ] BIC lookup and validation
- [ ] SCT vs SCT Inst routing (instant for amounts < 15k EUR)
- [ ] Settlement date calculation (T+1 business day)
- [ ] Reject handling (pain.002 parsing)
- [ ] Refund / return handling (cross-border refunds 10 days)
- [ ] Mandate lifecycle (create → amend → cancel for SDD)
- [ ] Currency enforcement (only EUR in SEPA zone)
- [ ] TIN validation for tax compliance (Italy, Spain)

## SEPA Instant (SCT Inst)

Special requirements:
- Maximum: EUR 100,000
- Available: 24/7/365, max 10s settlement
- Requires specific SEPA Inst scheme participation
- Reject rate must be < 0.5%
- Timeout handling: if no response in 10s → check status separately

```python
async def send_sepa_instant(iban: str, amount: float, reference: str) -> dict:
    if amount > 100000:
        raise ValueError("SEPA Instant max amount is EUR 100,000")

    if not await self.is_instant_eligible(iban):
        return await self.send_standard_sepa(iban, amount, reference)

    # Build pain.001 with instruction priority
    doc = self.build_pain001(amount, iban, reference)
    doc.PmtInf.SpcfcSvcTlvl.Cd = "INST"
    return await self.submit_to_clearing(doc)
```