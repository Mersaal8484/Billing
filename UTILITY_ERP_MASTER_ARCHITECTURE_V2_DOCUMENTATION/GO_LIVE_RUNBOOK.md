# GO-LIVE RUNBOOK

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** Production Cutover & Hypercare Runbook

> خطة تشغيلية دقيقة للانتقال إلى الإنتاج، التحقق، قرار الاستمرار أو الرجوع، وHypercare.

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


## 1. Roles During Cutover

Assign named owners for:
- Go-Live Commander.
- Odoo/Application.
- Database.
- Media/Storage.
- Network/NGINX.
- Migration.
- Billing.
- Accounting.
- Operations/Inventory.
- Security.
- Integrations.
- Business Sign-Off.

---

## 2. T-7 Days

- release freeze for scope.
- final UAT status.
- verify migration scripts.
- confirm backup capacity.
- verify restore rehearsal result.
- validate production config.
- confirm certificates/DNS.
- provider coordination.
- finalize user/role imports.
- capacity health check.

---

## 3. T-24 Hours

- final source data quality report.
- verify target clean baseline.
- verify monitoring/alerts.
- pause nonessential changes.
- confirm rollback snapshots.
- confirm media storage sync approach.
- communicate cutover window.

---

## 4. Cutover Start

1. announce freeze.
2. stop/lock legacy writes according to plan.
3. record exact freeze timestamp.
4. disable outbound integrations in target until validation.
5. take final source backup/export.
6. take target pre-cutover snapshot.
7. run final migration/delta.

---

## 5. Migration Validation

Must check before opening:
- account counts.
- meter/serial counts.
- active meter mapping.
- reading boundary samples.
- open AR totals.
- open bill residual.
- payment totals.
- media sample.
- inventory location sample.
- period states.

Any P0 mismatch triggers stop/rollback decision.

---

## 6. Application Smoke Tests

- login.
- scoped user access.
- account lookup.
- reading create/review.
- media display.
- test bill in permitted cutover data/process.
- accounting view.
- payment test according to production validation policy.
- service order.
- stock serial lookup.
- API auth.
- integration disabled/controlled status.

---

## 7. Enable Traffic

Gradual:
1. internal users.
2. limited field users.
3. portal/API.
4. AMI.
5. payment provider callbacks.
6. remaining integrations/workers.

Observe queues/errors after each step.

---

## 8. First Billing/Collection Control

During first production cycle:
- low concurrency initially if possible.
- validate first batch.
- compare sample bill totals manually.
- validate first payment allocation.
- then scale workers.

---

## 9. Rollback Criteria

Examples:
- unreconciled financial mismatch beyond approved tolerance.
- widespread missing accounts/meters.
- DB instability/data corruption.
- unauthorized cross-region exposure.
- media systemic failure blocking required operations.
- duplicate billing/payment.

Rollback authority = Go-Live Commander + business/accounting owners.

---

## 10. Rollback Procedure

1. stop incoming traffic/workers.
2. disable provider callbacks/outbox dispatch.
3. preserve logs/evidence.
4. restore pre-cutover target snapshot or switch back legacy according to plan.
5. restore routing/DNS.
6. reconcile transactions occurring during open window.
7. communicate status.
8. root-cause before next attempt.

---

## 11. Hypercare

Suggested phases, exact duration approved by project:
- intensive first hours.
- daily war-room first business days.
- extended monitoring through first complete billing/payment cycle.

Monitor:
- reading ingestion.
- billing errors.
- payment reconciliation.
- media.
- stock operations.
- DB/connection/storage.
- provider failures.
- security incidents.

---

## 12. Daily Hypercare Report

- new defects by severity.
- unresolved P0/P1.
- batch backlog.
- billing success/error.
- payment success/reconciliation.
- storage growth.
- DB health.
- integrations.
- business sign-off concerns.

---

## 13. Go-Live Completion

Go-Live moves to normal operations only after:
- first required operational cycles stable.
- no critical data/financial defects.
- backup after cutover verified.
- support ownership transferred.
- runbooks and escalation active.
