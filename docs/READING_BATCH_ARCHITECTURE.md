# READING BATCH ARCHITECTURE

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

**Document Type:** High-Volume Reading Ingestion & Staging Specification

> تصميم رفع ومعالجة دفعات القراءات بصورة Crash-Safe، Idempotent، قابلة للفشل الجزئي والتوسع.

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


## 1. Principle

`utility.reading.batch.line` هو Persistent Staging، وليس transient upload buffer.

```text
Client Upload
 → Batch
 → Persistent Lines
 → Validation
 → Processing
 → Canonical Reading
```

---

## 2. Batch Identity

كل Batch:
- batch_uuid.
- source/user/device.
- period.
- created_at.
- state.
- counts.
- retry_count.
- checksum/metadata where useful.

كل line:
- source UUID/idempotency key.
- meter/account identifier.
- value/time.
- media reference.
- validation result.
- canonical reading link.
- error code/message.

---

## 3. States

Suggested:
```text
draft/uploading
uploaded
processing
processed
partial
failed
cancelled
```

Line:
```text
pending
valid
processed
business_error
technical_error
duplicate
```

---

## 4. Processing

1. Persist batch header.
2. Persist all accepted line payloads.
3. Commit staging.
4. Dispatch batch command.
5. Claim deterministic chunk.
6. Validate line.
7. Resolve period/meter/account.
8. Normalize media.
9. Create canonical reading idempotently.
10. store result/error.
11. aggregate counts.
12. retry only retryable subset.

---

## 5. Partial Failure

10,000 lines + 37 invalid:
```text
9,963 processed
37 isolated errors
```

لا Rollback للـ9,963.

---

## 6. Idempotency

Keys:
```text
batch_uuid
source_reading_uuid
meter + source_timestamp + provider reference (fallback policy)
```

DB constraint + application idempotency.

---

## 7. Chunking

Chunk size configurable and benchmarked.

Requirements:
- deterministic ordering by line id.
- row claim/lock strategy.
- no overlapping processing.
- bounded transaction.
- commit per chunk.

---

## 8. Workflow Scope

At low scale/local:
- local durable command/cron worker.

Target scale:
- Temporal coordinates batch/chunks/retries.
- Odoo remains canonical data writer.
- no Temporal workflow per individual reading unless benchmark proves it useful.

---

## 9. Media

Batch line does not embed canonical binary long-term.

Flow:
```text
media payload/reference
 → normalize
 → utility.media.asset
 → reading.image_asset_id
```

---

## 10. Error Codes

- BATCH_PERIOD_CLOSED
- METER_NOT_FOUND
- ACCOUNT_MISMATCH
- DUPLICATE_SOURCE_READING
- INVALID_VALUE
- INVALID_TIMESTAMP
- OUT_OF_WINDOW
- INVALID_MEDIA
- REGION_DENIED
- TECHNICAL_RETRY

---

## 11. Metrics

- uploaded lines/sec.
- processed lines/sec.
- success/error/duplicate.
- chunk latency.
- backlog depth.
- retry count.
- media processing latency.
- oldest pending age.

---

## 12. Acceptance

- 10k test with intentional partial errors.
- duplicate upload produces no duplicate reading.
- worker crash resumes safely.
- retry processes only retryable lines.
- closed period rejects appropriately.
- unauthorized region cannot inject reading.
- canonical result traceable to batch line.

## V3.2 Current Implementation and Operational UX Contract

**CURRENT V1 lifecycle:**

```text
uploaded → processing → done / partial / error
```

The implementation uses bounded Cron processing, per-row/per-record safety where applicable, `FOR UPDATE NOWAIT`, SQLSTATE `55P03` handling without broad lock-exception swallowing, reader ownership validation, `total_readings` validation, malformed JSON/limit validation, and eligible reading-period filtering.

The current UI is part of the operational contract: it exposes `total_readings`, `processed_count`, `error_count`, `image_count`, and `progress_percent`; the statusbar shows terminal/error states; the default action filter shows active batches and a needs-attention filter surfaces `partial`/`error`. Regression test files exist for API inputs and concurrency; runtime proof remains **DEFERRED**.
