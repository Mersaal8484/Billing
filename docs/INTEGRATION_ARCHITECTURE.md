# INTEGRATION ARCHITECTURE

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

**Document Type:** External Integration, Outbox & Workflow Specification

> تحديد حدود المزودين الخارجيين، الـOutbox، retries، Temporal scope، AMI وPayment callbacks.

---


## المبادئ المعمارية الملزمة

- Odoo 16 Community هو **System of Record** للـUtility Domain والمحاسبة.
- التشغيل المستهدف لمؤسسة تشغيلية واحدة؛ النطاق الأمني والتشغيلي يعتمد على Geography وليس Business Multi-Company.
- لا توجد Customer Wallet في Postpaid Utility.
- لا توجد Taxes في Utility Billing Flow الحالي.
- Reading + Review مرحلة تشغيلية واحدة.
- لكل Cycle فترة Reading وفترة Payment مستقلة مرتبطة بنفس `cycle_key`.
- `utility.bill.reading.component` هو Immutable Billing Segment Snapshot ولا يعاد تصميمه.
- `periodic` هو Billing Anchor، و`replacement_closing` و`opening` يحتفظان بدلالتهما.
- عدة عمليات Replacement داخل نفس Cycle تنتهي إلى **فاتورة واحدة** للحساب/الفترة مع عدة Reading Components.
- `utility.media.asset` هو Canonical Media Model.
- Payment Reconciliation يجب أن يكون Targeted/Explicit، وليس Partner-wide.
- التصحيحات التاريخية تتم بواسطة Correction/Reversal Documents، وليس بتعديل السجل التاريخي المنشور.
- Hybrid Workflow: المعاملات القصيرة داخل Odoo؛ Temporal للعمليات الطويلة وReading Batch orchestration عند Target Scale.
- Redis مساعد للـRate Limiting/Cache فقط، وليس Source of Truth.
- PgBouncer جزء من Target Production Scale عند تعدد العقد والـWorkers.
- Persistent Staging + Idempotency + Partial Failure هي القاعدة لدفعات القراءات.


## 1. Provider Registry

`utility.integration.provider` يدير:
- SMS.
- AMI.
- Payment Gateway.
- Mobile Money.
- Bank Transfer.
- Direct Debit.

Fields:
- type.
- endpoint.
- timeout.
- auth style.
- secret/API key.
- custom headers.
- journals where payment-capable.
- active/status.

---

## 2. Architectural Boundary

External provider must not become Source of Truth.

```text
Odoo Domain Transaction
 → persistent business state
 → Outbox/Command
 → provider side effect
```

---

## 3. Outbox

`utility.workflow.command` or equivalent durable command records:
- command UUID.
- idempotency key.
- target record.
- payload.
- state.
- attempt count.
- schedule.
- error.
- timestamps.

---

## 4. Retry

Transient:
- timeout.
- connection reset.
- provider 5xx.
- explicit retryable status.

Permanent:
- invalid business payload.
- authentication rejected until config fixed.
- invalid account/meter.

Target backoff:
- bounded exponential.
- max attempts.
- dead-letter/manual retry.

---

## 5. Temporal Scope

Use:
- long field workflows.
- reading batch orchestration.

Potential:
- billing batch coordination.

Do not use:
- one invoice.
- one notification.
- short accounting posting.
- one image unless benchmark justifies.

---

## 6. Payment Provider

Outbound request:
- reference.
- amount/currency.
- bill/account.
- callback authentication context.

Callback:
- verify cryptography.
- replay protection.
- idempotency.
- lock transaction/bill.
- create payment once.

---

## 7. AMI

Provider request/read callback supports:
- unique provider reading reference.
- meter.
- timestamp.
- value.
- quality flags if available.
- source/provider ID.

AMI reading still passes core validation/VEE.

---

## 8. SMS/Notification

Financial transaction commits first.

Notification failure:
- logs failed command.
- retries.
- does not rollback posted payment/bill.

---

## 9. Secret Management

Target:
- environment/secret store for deployment secrets.
- encrypted/restricted Odoo fields where configuration UI needed.
- no secret in ordinary logs.
- rotation runbook.
- key identifier separate from key material.

---

## 10. Observability

Per provider:
- call count.
- success rate.
- latency.
- error status distribution.
- retry backlog.
- oldest pending.
- callback duplicates.
- auth failures.

---

## 11. Acceptance

- provider timeout retry.
- 5xx retry.
- permanent 4xx classified.
- duplicate command.
- duplicate callback.
- secret masked.
- notification failure after successful payment does not rollback payment.
- Temporal outage does not corrupt Odoo state.

## V2.1 Current Implementation Synchronization

**CURRENT V1:** Payment gateway callbacks resolve the transaction, authenticate the callback before locking, use constant-time token comparison where applicable, then lock the transaction/invoice/order as needed. Only pending transactions may transition. Payloads are sanitized, provider references are required for successful settlement where applicable, and repeated successful callbacks are idempotent.

**DEFERRED:** runtime callback race proof and full external-provider certification are separate runtime activities; static controls and regression test files must not be reported as production proof.

## Organizational Scope for Integrations

External/API integrations must preserve the same two-axis model: functional role plus company/organizational scope. Current portal/customer ownership checks are narrower than a complete Region/Branch scope implementation. Any future `sudo()` integration path must resolve scope before processing identifiers, and integration reports/aggregates must not leak unauthorized region totals.
