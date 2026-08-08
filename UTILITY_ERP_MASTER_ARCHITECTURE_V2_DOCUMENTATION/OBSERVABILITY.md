# OBSERVABILITY

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** Logging, Metrics, Alerting & Operational Telemetry Specification

> تعريف القياسات والسجلات والإنذارات اللازمة لتشغيل النظام والتحقيق في المشاكل دون تخمين.

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


## 1. Objectives

Observability يجب أن تجيب:
- ماذا تعطل؟
- منذ متى؟
- كم سجلًا تأثر؟
- هل المشكلة Business أم Technical؟
- هل البيانات آمنة؟
- هل يمكن Retry؟
- ما الـrequest/batch/account/period المتأثر؟

---

## 2. Correlation IDs

استخدم:
- request_id.
- batch_uuid.
- command_uuid.
- workflow_run_id.
- payment reference.
- asset_uuid.
- period code.

تظهر في logs/metrics/events حسب السياق.

---

## 3. Application Logs

Structured fields:
- timestamp.
- severity.
- module.
- operation.
- user/provider.
- model/res_id.
- company/region where safe.
- correlation ID.
- duration.
- error code.

Never log:
- passwords.
- API secrets.
- full auth tokens.
- unnecessary personal data.

---

## 4. Business Metrics

### Reading
- batches uploaded.
- lines pending/processed/error/duplicate.
- readings under review.
- exception counts.

### Billing
- bills generated/min.
- billing errors by code.
- duplicate prevention count.
- posting failures.

### Payment
- intents.
- callbacks.
- successful/failed.
- allocation latency.
- duplicate callbacks.
- reconciliation failures.

### Operations
- open by state/type.
- aging.
- replacements completed.
- stock blockers.

---

## 5. Infrastructure Metrics

- CPU/memory.
- disk capacity/IOPS/latency.
- DB connections.
- PgBouncer pool wait.
- DB TPS.
- long queries.
- lock waits/deadlocks.
- WAL.
- replica lag.
- Redis memory/evictions.
- NGINX latency/5xx.
- Temporal queue/backlog.
- worker heartbeat.

---

## 6. Media Metrics

- upload count/bytes.
- validation errors.
- variant generation latency.
- media GET latency/status.
- cache/304 ratio.
- storage growth.
- broken/orphan assets.

---

## 7. Alerts

Critical:
- DB unavailable.
- storage unavailable/full.
- payment reconciliation failure spike.
- duplicate financial processing.
- billing halted.
- backup failed.
- media corruption spike.

Warning:
- growing queues.
- high p95.
- pool wait.
- high retry.
- disk forecast threshold.
- replica lag.

---

## 8. Dashboards

1. Executive cycle.
2. Reading ingestion/review.
3. Billing generation.
4. Collections/payment gateway.
5. Media/storage.
6. Operations/inventory.
7. PostgreSQL/PgBouncer.
8. Integration/Temporal.

---

## 9. Audit vs Operational Logs

Audit logs immutable/business-oriented.

Operational logs may rotate.

Do not rely on application log as only audit source.

---

## 10. Runbook Linkage

Every actionable alert must link/identify:
- probable owner.
- first diagnostic query.
- safe retry action.
- escalation.
- rollback if applicable.

---

## 11. Acceptance

Before Go-Live trigger synthetic failures and confirm:
- alert fires.
- operator identifies affected component.
- trace/correlation reaches business record.
- no secret exposed.
