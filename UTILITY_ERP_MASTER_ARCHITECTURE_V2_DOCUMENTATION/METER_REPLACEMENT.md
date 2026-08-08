# METER REPLACEMENT

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** Canonical Meter Replacement Specification

> توحيد Domain الاستبدال وحفظ الاستهلاك والأدلة والمخزون والفوترة عبر العدادات المتعاقبة.

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


## 1. Canonical Model

```text
utility.meter.replacement
```

يدعم:
- subscriber.
- feeder.
- transformer.

Operations لا يعيد حساب replacement domain.

---

## 2. Preconditions

- target exists.
- old meter resolved.
- new meter exists/created and differs.
- new meter eligible for installation.
- closing reading ≥ last invoiced boundary.
- opening reading ≥ 0.
- user authorized geographically.
- inventory availability/reservation satisfied for operational completion.

---

## 3. Domain Transaction

1. lock replacement/target as required.
2. create old-meter `replacement_closing`.
3. create new-meter `opening`.
4. closing/opening state approved.
5. detach/deactivate old meter logically.
6. attach/activate new meter.
7. update account/network target.
8. write meter logs.
9. set replacement done.

---

## 4. Reading Semantics

Old:
```text
reading_purpose = replacement_closing
reading_event = replacement
```

New:
```text
reading_purpose = opening
reading_event = replacement
previous_reading = opening value
consumption = 0
```

Opening zero is valid.

---

## 5. Billing

Closing segment remains unbilled until next periodic anchor.

The next bill:
- locks all pending closings.
- builds chronological segments.
- creates one bill.
- creates multiple immutable components.

---

## 6. Operations Orchestration

```text
Service Request
 → Approve
 → Schedule/Assign
 → Reserve new meter
 → Field visit
 → Capture readings/evidence
 → Canonical replacement
 → Stock movements
 → Complete
```

---

## 7. Inventory

New meter:
```text
Warehouse/Custody → Installed
```

Old meter:
```text
Installed → Removed/Quarantine
 → Test/Repair/Return/Scrap
```

No hard-coded global stock location in target design.

---

## 8. Evidence

Replacement may link:
- old meter photo.
- new meter photo.
- seals.
- serial scan.
- field signature/notes.

Evidence uses `utility.media.asset`.

---

## 9. Idempotency

Repeated completion request must not:
- create duplicate closing/opening readings.
- repeat stock movement.
- switch meter twice.
- duplicate logs.

Use replacement business key/state/linked reading constraints.

---

## 10. Corrections

After replacement done:
- do not directly delete closing/opening.
- correction via controlled settlement/reversal workflow.
- stock reversal via stock documents.
- meter connection history retained.

---

## 11. Acceptance

- subscriber replacement.
- feeder replacement.
- transformer replacement.
- opening=0.
- invalid closing.
- same old/new rejected.
- stock unavailable rejected.
- retry completion idempotent.
- two replacements in same period bill correctly.
- security scope enforced.
