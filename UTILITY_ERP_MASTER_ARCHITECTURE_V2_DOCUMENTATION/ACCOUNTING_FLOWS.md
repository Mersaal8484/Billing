# ACCOUNTING FLOWS

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

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
