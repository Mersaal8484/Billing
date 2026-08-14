# BACKUP & RESTORE

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `51e8dba5c47ed8ff9d1485b519e1b1586cb30522`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 2.1
**Last Verified Date:** 2026-08-14
**Status:** Current V1 + Target V2

**Document Type:** Backup, Recovery & Disaster Restoration Runbook

> تحديد ما يجب نسخه وكيفية استعادته والتحقق من consistency بين قاعدة البيانات والوسائط والخدمات.

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


## 1. Protected Assets

- Odoo PostgreSQL.
- current compatibility filestore/attachments.
- target media filesystem.
- Temporal PostgreSQL if deployed.
- deployment configuration.
- encrypted/secured secrets backup according to policy.
- migration/export mapping artifacts needed for recovery.

---

## 2. Consistency Principle

DB references and media files must restore to a mutually consistent recovery point.

A DB restore without matching evidence snapshot may create broken assets.

---

## 3. Backup Types

### Database
- periodic full/base backup.
- WAL/PITR strategy where production policy requires.

### Media
- filesystem snapshots/incremental copy.
- checksums.
- retention.

### Configuration
- versioned non-secret config.
- secure secret backup.

---

## 4. RPO/RTO

Final RPO/RTO values are business-approved SLOs.

Before Go-Live record:
- approved RPO.
- approved RTO.
- maximum tolerated media loss.
- recovery authority.

No unapproved numeric promise is assumed here.

---

## 5. Restore Order

Typical:
1. infrastructure.
2. PostgreSQL.
3. media filesystem/filestore matching restore point.
4. application code/version.
5. configuration/secrets.
6. Temporal DB/workers if applicable.

## V2.1 Classification

**CURRENT V1:** backup/restore scope is the Odoo PostgreSQL database, configured attachments/media compatibility data, repository/configuration inputs, and operational runbooks. Restore timing and end-to-end recovery proof require execution.

**TARGET V2 / CONDITIONAL:** separate media backend and Temporal persistence are included only when those target components are deployed. They are not current V1 prerequisites.
7. disable external side effects initially.
8. integrity validation.
9. re-enable integrations.

---

## 6. Post-Restore Validation

- DB starts cleanly.
- module versions match.
- account/meter/readings sample.
- media sample opens.
- posted invoice balances.
- payments/reconciliation.
- workflow command state.
- no massive duplicate retries.
- provider callbacks/routing controlled.

---

## 7. Disaster Drill

At least before Go-Live and periodically:
- restore into isolated environment.
- measure actual duration.
- verify consistency.
- document deviations.
- update RTO expectation.

---

## 8. Media Integrity

Sample/check:
- asset row exists.
- expected variant exists.
- checksum valid.
- authorized delivery works.

---

## 9. PITR Caveat

When restoring DB to time T, media written after T may exist as unreferenced files.

Recovery tooling must:
- tolerate extra files.
- detect orphan assets/files.
- never delete automatically without audit.

---

## 10. External Integrations After Restore

Prevent replay:
- pause outbox workers.
- inspect pending/processing commands.
- reset stale processing safely.
- use idempotency/provider references before resend.

---

## 11. Acceptance

Backup is not accepted until a restore succeeds and business-critical flows are verified.
