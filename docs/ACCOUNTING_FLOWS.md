# ACCOUNTING FLOWS

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

**Document Type:** Utility Accounting Flow Specification

> تثبيت القيود والمستندات المحاسبية المرجعية لجميع دورات الإيراد والتحصيل والتصحيح.

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


## 1. Accounting Truth

`account.move` هو الحقيقة المحاسبية النهائية.

Utility documents توفر business context، لكنها لا تستبدل Accounting Documents.

---

## 2. Utility Consumption Billing

```text
Utility Bill
 → Customer Invoice
```

Typical:
```text
Dr Customer Receivable
Cr Electricity Revenue
Cr Service/Local Revenue accounts as configured
```

No tax lines in current flow.

---

## 3. Collection

```text
Dr Bank/Cash/Outstanding Receipts
Cr Customer Receivable
```

ثم targeted reconciliation إلى invoice lines.

---

## 4. Payment Gateway

Provider لا يغير receivable مباشرة.

```text
Gateway Transaction
 → Account Payment
 → Allocation
 → Reconciliation
```

Provider settlement fees, if later required, are separate accounting entries/configuration.

---

## 5. Customer Deposit

### Receive
```text
Dr Bank/Cash
Cr Customer Deposit Liability
```

### Release
```text
Dr Customer Deposit Liability
Cr Bank/Cash
```

### Forfeit
```text
Dr Customer Deposit Liability
Cr Fine/Other Revenue
```

لا يعامل التأمين كتحصيل فاتورة كهرباء عادية.

---

## 6. Penalty

عند application:
```text
Dr Customer Receivable
Cr Penalty Revenue
```

Document:
- separate invoice or approved equivalent.
- linked to source Utility Bill/account.
- waiver before posting or explicit reversal/credit after posting.

---

## 7. Write-Off

Write-off approved against customer receivable:
- use approved writeoff account/journal.
- create credit note or accounting document.
- reconcile only source receivable.

No direct balance mutation.

---

## 8. Financial Settlement

### Credit to customer
Credit Note / out_refund.

### Debit to customer
Debit/Customer Invoice.

Requires:
- reason.
- approval.
- source.
- accounting account.
- posted move.

### Collector custody and bank deposit settlement

The V1 collector deposit flow is separate from customer invoice payment
allocation and uses Odoo accounting entries as its financial truth:

```text
posted collection custody
  → collector settlement (FIFO or explicit source allocation)
  → deposit settlement (bank journal Dr / deposit clearing Cr)
  → exact partial reconciliation on deposit clearing
```

- `utility.collection.settlement` owns the collector custody settlement.
- `utility.bank.settlement` owns the bank deposit event and its allocation lines.
- Confirming either settlement is the business execution action; there is no
  second operational post/reconcile step.
- A bank settlement without explicit lines can allocate its declared deposit
  amount automatically by collector, currency, bank reference, then oldest
  settlement date and ID.
- `settlement_key` is generated for automatic entry points and is unique per
  company to prevent duplicate settlement events.
- Bank statement lines are not part of the V1 deposit lifecycle. The bank
  deposit creates and posts its own `account.move` directly.
- `utility.financial.settlement` remains an explicit manual approved
  adjustment/refund path; it is not an automatic collector deposit source.

---

## 9. Reading Correction

Never edit billed reading financially.

```text
Corrected consumption delta > 0
 → Debit Invoice

Corrected consumption delta < 0
 → Credit Note
```

Original invoice/components preserved.

---

## 10. Meter Replacement

Replacement itself has no automatic revenue unless configured service charge applies.

Unbilled consumption remains in Reading Components of next periodic Utility Bill.

Stock movement/accounting follows inventory valuation configuration where applicable.

---

## 11. Service Charges

Connection/reconnection/testing fees:
- operational source `utility.service.order`.
- approved charge document.
- customer invoice.
- explicit link service order ↔ charge ↔ account.move.

---

## 12. Configuration

Must be configured before operation:
- revenue accounts.
- penalty account.
- deposit liability.
- writeoff account/journal.
- settlement account/journal.
- collection/payment journals.
- service charge products/accounts.

No silent runtime chart-of-accounts creation.

---

## 13. Reconciliation Policy

- selected receivable lines only.
- same partner/account/currency constraints as accounting requires.
- no broad exception swallowing.
- failed reconciliation blocks financial completion and logs reason.
- collector deposit reconciliation is restricted to the deposit clearing
  account and the explicitly or automatically allocated source settlements.

---

## 14. Period Close Reconciliation

Reading Period close verifies generated bills and posted invoices.

Payment Period reconcile verifies payment/reconciliation exceptions according to policy.

---

## 15. Accounting UAT

- invoice journal entry.
- partial/full payment.
- deposit receive/release/forfeit.
- penalty apply/waive/reverse.
- writeoff.
- debit/credit settlement.
- reading correction.
- concurrent payment.
- traceability to Utility source.

## V3.2 Current Implementation Synchronization

**CURRENT V1:** `account.move` is canonical financial truth; utility Bills are `sale.order` records and Payments are `account.payment`. Allocation is explicit to the selected invoice receivable lines and does not perform partner-wide arbitrary reconciliation. Bill forms navigate directly to related accounting invoices and payments.

- **Collector Settlements & Bank Deposits:** `utility.collection.settlement` captures confirmed collections, and `utility.bank.settlement` links them to bank journal entries using company-scoped `settlement_key` preventing duplicate bank reconciliation.
- **Write-Off Invariant:** The current write-off lifecycle is `draft → approved → applied`. Only `approved → draft` is safe before financial application. Row locking and the existing `move_id` enforce the invariant **one write-off → at most one generated Credit Note**; `applied` cannot be reopened or applied again.

**DEFERRED:** static implementation includes concurrency controls and regression test coverage exists, but runtime concurrency proof and full accounting runtime/UAT execution are not claimed here.
