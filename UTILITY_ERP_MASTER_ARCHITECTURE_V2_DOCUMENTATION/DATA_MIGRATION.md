# DATA MIGRATION

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** Legacy Data Migration & Reconciliation Plan

> تحديد ترتيب الهجرة، staging، mapping، data quality، dry runs، reconciliation وrollback.

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


## 1. Migration Principles

- Preserve source identifiers.
- Staging before canonical import.
- Idempotent re-run.
- Explicit error queue.
- no silent data correction.
- reconcile counts and financial totals.
- multiple dry runs.

---

## 2. Migration Order

1. Geography.
2. Network.
3. Partners.
4. Utility Accounts.
5. Contract Templates/Tariffs.
6. Meters.
7. Meter↔Stock Serial.
8. Historical Readings.
9. Last billed reading boundaries.
10. Opening receivables.
11. Open bills.
12. Payments.
13. Replacements.
14. Media.
15. Open operations/inventory.

---

## 3. Mapping Registry

For every source object:
- source_system.
- source_model/table.
- source_id.
- target_model.
- target_id.
- migration_batch.
- status.
- checksum.
- error.

---

## 4. Period State Migration

Legacy states map to new states using explicit migration.

After:
- no legacy selection value.
- no stale domain.
- counts by state reconciled.

---

## 5. Media Migration

Classify:
- valid.
- double-base64.
- missing.
- corrupt.
- orphan.

Repair recoverable before target external filesystem migration.

Preserve asset UUID/revision/link.

---

## 6. Reading Migration

Validate:
- meter exists.
- account relation.
- reading order.
- no impossible negative progression unless documented.
- purpose/event.
- period mapping.
- billed boundary.

Historical billed readings must not be re-run through live billing.

---

## 7. Financial Migration

Approach approved with accounting:
- opening receivables via controlled opening entries.
- open invoices migrated/recreated as accounting documents according to cutover policy.
- payments/reconciliation preserve residual truth.

Required reconciliation:
```text
Source AR total = Target AR total
Source open invoice count = Target approved count
```

Tolerance must be explicitly approved, not implicit.

---

## 8. Meter/Stock

- serial uniqueness.
- current physical location.
- installed meter mapping.
- orphan serial.
- logical/physical mismatch report.

---

## 9. Dry Runs

At least:
- Dry Run 1: discover mapping/data issues.
- Dry Run 2: corrected full migration + timing.
- Final rehearsal: production-like dataset and cutover timing.

---

## 10. Validation Reports

- row counts.
- rejected rows.
- duplicate keys.
- account/meter missing.
- reading continuity.
- AR totals.
- bill residual totals.
- media valid ratio.
- inventory serial/location reconciliation.

---

## 11. Cutover

- define source freeze timestamp.
- extract delta after final full rehearsal.
- load final delta.
- run validation.
- business sign-off.
- switch users/endpoints.

---

## 12. Rollback

Rollback criteria defined before migration:
- financial mismatch.
- critical missing accounts/meters.
- unacceptable corrupt media rate.
- failed application validation.

Rollback restores:
- DB snapshot.
- media snapshot.
- configuration/secrets.
- integration routing.

---

## 13. Acceptance

Migration complete only when:
- all critical rejects dispositioned.
- accounting signed.
- billing sampling signed.
- inventory sampling signed.
- media repair report accepted.
- exact cutover duration known.
