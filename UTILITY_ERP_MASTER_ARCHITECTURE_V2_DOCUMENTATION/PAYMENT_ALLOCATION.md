# PAYMENT ALLOCATION

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** Payment Allocation & Reconciliation Specification

> إلغاء المطابقة العامة للشريك واعتماد تخصيص صريح وآمن تحت التزامن.

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


## 1. Core Rule

```text
Payment
  → Allocation Lines
      → Explicit Accounting Invoice(s)
```

ممنوع:
```text
find all partner receivables
→ reconcile all
```

---

## 2. Data Model Target

Suggested allocation entity:
- payment_id.
- utility_sale_order_id.
- move_id.
- amount.
- currency.
- state.
- allocation_key.
- created_by/date.
- reconciliation reference.

يمكن التنفيذ كنموذج مستقل أو abstraction مناسبة، لكن يجب أن تكون العلاقة explicit/auditable.

---

## 3. Inbound Flow

1. Resolve Utility Bill.
2. Read current posted invoice residual.
3. Lock target order/invoice.
4. Validate bill payable.
5. Validate amount > 0.
6. Validate allocated total ≤ residual.
7. Create/post account.payment.
8. Select payment receivable line.
9. Select target invoice receivable line.
10. reconcile selected lines only.
11. persist allocation.
12. refresh bill state.

---

## 4. Multiple Bill Allocation

عند دعم Payment واحدة لعدة فواتير:
- sum allocations = payment amount, except approved unapplied balance policy.
- each allocation ≤ invoice residual.
- deterministic order if auto-allocation is allowed by explicit policy.
- user-visible allocation detail.

---

## 5. Concurrency

Example:
```text
Residual = 1000
A = 600
B = 600
```

Transaction A/B both must lock target before final validation.

Allowed final result:
```text
A=600
B=400 or B rejected/adjusted
```

Never 1200.

---

## 6. Gateway Callback

1. lock gateway transaction.
2. idempotency check.
3. lock target bill/invoice.
4. validate residual.
5. create payment once.
6. allocate.
7. mark transaction done.

Provider reference unique per provider.

---

## 7. Overpayment

No silent overpayment.

Policy options:
- reject.
- allocate allowed residual and keep explicit unapplied credit document.
- customer credit process approved by accounting.

No customer wallet.

---

## 8. Refund / Outbound

Outbound payment must reference explicit source:
- credit note.
- approved refund.
- deposit release.
- other authorized accounting document.

---

## 9. Reversal

Payment reversal:
- reverse/unreconcile target allocation explicitly.
- maintain audit.
- restore residual deterministically.
- never delete posted financial history.

---

## 10. Payment Period

Every utility payment references Payment Period linked to bill's Reading Period.

Classification:
- on_time.
- late.
- exceptional.
- outside_window.

Due/late logic uses due date/payment policy rather than Sale Order date alone.

---

## 11. Acceptance

- full payment.
- partial.
- two partial payments.
- concurrent payments.
- multi-invoice allocation.
- duplicate callback.
- overpayment.
- cancelled/paid bill rejection.
- reversal.
- no unrelated partner line reconciled.
