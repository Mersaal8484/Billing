# BILLING ENGINE

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** Billing Domain & Execution Specification

> المرجع الملزم لمحرك فوترة الكهرباء، مكوناته، invariants، التسعير، التزامن والتصحيحات.

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


## 1. Billing Identity

الوحدة المالية الأساسية:

```text
Utility Account + Reading Period
```

ينتج عنها:

```text
ONE Active Utility Bill
```

حتى لو مر الحساب بعدة عدادات داخل نفس الدورة.

---

## 2. Canonical Inputs

- Periodic Billing Anchor.
- Zero or more approved pending `replacement_closing` readings.
- Opening readings التي تحدد بداية Segment الجديد.
- Account Contract/Tariff.
- Meter multipliers.
- Historical last billed boundary.

---

## 3. Frozen Segment Model

`utility.bill.reading.component` هو Snapshot لا يعاد حسابه من Master Data لاحقًا.

يحفظ:
- reading.
- account.
- meter.
- purpose.
- period boundaries.
- previous/current reading.
- multiplier.
- consumption.
- company.

بعد Billing يصبح Immutable.

---

## 4. Replacement Aggregation Example

```text
Last billed periodic = 1000

Old Meter A:
closing = 1300
segment = 300

Meter B:
opening = 20
closing = 170
segment = 150

Meter C:
opening = 5
periodic = 105
segment = 100
```

النتيجة:

```text
Bill Consumption = 550
Components = [300, 150, 100]
ONE Sale Order
ONE Accounting Invoice
```

---

## 5. Billing Algorithm

1. Validate periodic reading is approved/queued and billable.
2. Validate account/period.
3. Lock target billing identity.
4. Reject existing active bill for account+period.
5. Resolve last billed periodic boundary.
6. Lock pending replacement-closing readings.
7. Build component snapshots in chronological sequence.
8. Sum segment consumption.
9. Resolve tariff snapshot.
10. Calculate order lines.
11. Create Sale Order.
12. Persist components.
13. Mark included closing readings.
14. Create/post Accounting Invoice per policy.
15. Mark anchor billed.
16. Commit.

---

## 6. Tariff Modes

### Flat
`total = consumption × flat price`

### Tier
حدد الشريحة على أساس إجمالي الاستهلاك ثم طبق سعرها على كامل الاستهلاك.

### Progressive Block
وزع الاستهلاك على الشرائح بصورة تصاعدية.

### Additional
- fixed/service charges.
- local fees.
- discounts.
- sponsor discounts.
- min/max charge.
- controlled formula quantities.

No taxes.

---

## 7. Tariff Snapshot

عند Bill Creation احفظ:
- template ID/code.
- template version/effective dates.
- pricing mode.
- block definitions used.
- fees.
- discount policy.
- formula ID/version/hash.
- rounding policy.

لا تعتمد إعادة بناء فاتورة قديمة على Template الحالية.

---

## 8. Idempotency & Concurrency

### Constraints
- one active bill per account+period.
- unique bill+reading component.
- no duplicate active reading bill.

### Locks
- billing target/account/period.
- selected replacement closing readings.

### Retry
Retry لنفس business key يعيد نفس النتيجة أو يرفض duplicate بصورة deterministically.

---

## 9. Batch Billing at Scale

Coordinator يقسم الحسابات إلى micro-batches:

```text
500–1000 accounts starting benchmark
```

كل Unit:
- transaction مستقلة.
- deterministic ordering.
- error isolation.
- progress metrics.

الرقم النهائي يثبت بالـLoad Test.

---

## 10. Billing Error Taxonomy

- missing tariff.
- missing periodic anchor.
- duplicate active bill.
- invalid meter segment.
- negative consumption.
- incomplete block coverage.
- missing accounting configuration.
- posting failure.
- stale/concurrent state.

Business errors لا تعاد تلقائيًا بلا تعديل Configuration/Data.

Transient errors يمكن Retry.

---

## 11. Corrections

بعد Posting:
- لا تعديل order financial history مباشرة.
- لا تعديل billed reading.
- لا تعديل components.

التصحيح:
```text
Settlement
 → Delta Consumption
 → Reprice using approved correction policy
 → Debit Invoice / Credit Note
```

---

## 12. Golden Regression Matrix

- normal periodic.
- zero replacement.
- one replacement.
- multiple replacement.
- opening=0.
- flat.
- tier boundaries.
- progressive boundaries.
- discount blocks.
- min/max charge.
- concurrent billing.
- duplicate retry.
- accounting posting.
- correction after billing.

---

## 13. Billing Definition of Done

- Golden numeric results ثابتة.
- Invoice amount = component/tariff result.
- Components reconstruct bill.
- No duplicate under concurrency.
- Posted accounting document links back to Utility Bill.
- Historical tariff interpretation survives future configuration changes.
