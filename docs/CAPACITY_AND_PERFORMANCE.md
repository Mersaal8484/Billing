# CAPACITY & PERFORMANCE

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

**Document Type:** Capacity Planning, Performance & Load Test Specification

> تحويل هدف المليون مشترك إلى أحمال قابلة للقياس وتصميم batching/partitioning/connections.

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


## 1. Planning Baseline

هذه Planning Assumptions وليست SLA نهائية:

| Metric | Planning Value |
|---|---:|
| subscribers | 1,000,000 |
| readings/month | 1,000,000 |
| realistic peak readings/day | ~50,000–65,000 |
| new media/month | ~1,000,000 |
| media growth/month | ~90–110 GB |
| media growth/year | ~1.1–1.3 TB |
| reading rows/year | ~12M |
| reading rows/5 years | 60M+ |
| bills/month | up to 1M |
| collections/month | up to 1M |

### Initial 300k-Customer Sizing Baseline

The separate production sizing target is 300,000 customers, 1,100–2,500 internal users, 600–750 concurrent users, and up to 7.2 million readings/year. With annual database rotation, the active Odoo PostgreSQL database contains one operational year rather than a multi-year live working set.

Initial planning resources are 24–32 vCPU / 128 GB RAM / 2 TB enterprise NVMe for each Odoo PostgreSQL Primary/Standby, and 4 TB usable shared Filestore. These are planning values, not capacity proof; retain 4 TB PostgreSQL only if yearly growth, WAL, maintenance headroom, or index/bloat measurements require it.

---

## 2. Critical Workloads

1. Morning batch upload.
2. Reviewer media browsing.
3. Billing window.
4. `account.move`/`account.move.line` creation.
5. Payment concurrency.
6. penalty/disconnection crons.
7. reports during billing.

---

## 3. Billing Micro-Batch

Starting benchmark:
```text
500–1000 accounts/transaction
```

Tune based on:
- DB transaction duration.
- lock wait.
- WAL.
- CPU.
- ORM memory.
- invoice lines per bill.

No million-account transaction.

---

## 4. PgBouncer

Measure:
- client connections.
- server connections.
- pool wait.
- transaction time.

Goal:
Application worker count can scale without linear PostgreSQL backend explosion.

---

## 5. Partitioning

Primary:
- `utility_reading`
- `utility_reading_batch_line`

Monthly/time partition recommended starting design.

Evaluate accounting table partitioning separately with Odoo upgrade compatibility tests.

---

## 6. Indexing

Candidate composites:
- reading period/state/purpose.
- reading meter/state/date.
- reading account/state/date.
- media reading/state.
- batch period/state.
- payment order/state/date.
- service customer/type/state.

Every index justified by query plan/production-like load.

---

## 7. Media Performance

- thumbnails in list.
- review variant in reviewer.
- original explicit.
- NGINX delivery.
- ETag/private cache.
- no binary fetch for counters.

---

## 8. Queue Backpressure

Define maximum pending:
- reading batch lines.
- media processing.
- billing chunks.
- integration commands.

When threshold exceeded:
- slow/reject new batch according to policy.
- alert.
- scale workers.
- protect DB.

---

## 9. Load Test Stages

### LT-1 Walking Skeleton
single end-to-end.

### LT-2 10k Reading Batch
partial failure.

### LT-3 Review UI
40+ rapid reviewer actions/min target experiment, measure rather than assume final SLA.

### LT-4 100k Bills
no duplicates, bounded failures.

### LT-5 Concurrent Payments
hot accounts/bills.

### LT-6 Million-scale Rehearsal
synthetic equivalent monthly workload.

---

## 10. Metrics

- request p50/p95/p99.
- DB query time.
- lock waits/deadlocks.
- connections/pool wait.
- transactions/sec.
- reading throughput.
- billing bills/min.
- payment confirms/sec.
- media MB/sec and latency.
- queue age/depth.
- CPU/memory/I/O.
- WAL generation.
- replica lag.

---

## 11. SLO Policy

Final SLO numbers are approved only after:
- Walking Skeleton.
- synthetic benchmark.
- pilot telemetry.

Architecture document does not invent final latency promises.

---

## 12. Performance Gate

Before Go-Live:
- no unbounded queue.
- no giant transaction.
- no recurring sequential query hotspot.
- restore performance validated.
- report workload separated/throttled as required.

## V3.2 Classification

**CURRENT V1:** bounded jobs, indexed critical fields, bulk-oriented reading computations, structured `ir.attachment` filesystem storage, and operational search defaults are implemented. The current static review records one deferred performance debt: physical meter-state computation may issue per-meter `stock.quant` queries.

**DEFERRED:** optimize that path only after profiling demonstrates production impact. Runtime load benchmarking, million-subscriber capacity claims, partition rollout, PgBouncer validation, and horizontal topology are not proven by this documentation update.

**TARGET V2:** partition planning, micro-batch billing, connection pooling, and scale observability remain conditional roadmap items.

**TARGET V2 / CONDITIONAL:** the 300k-customer annual-rotation sizing is a deployment target that requires production-like load tests, annual-close rehearsal, media-retention tests, and restore measurements. It must not be presented as a verified capacity claim before those gates pass.
