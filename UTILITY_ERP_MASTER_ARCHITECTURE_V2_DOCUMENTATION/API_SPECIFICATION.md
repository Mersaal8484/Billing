# API SPECIFICATION

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** External & Internal API Contract

> توحيد عقود API للمشترك، القراءة، الدفع، AMI، العمليات، التقارير والـMedia.

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


## 1. API Principles

- Version prefix: `/api/v1/utility/...`
- JSON for business APIs.
- HTTP for media bytes.
- authenticated by `auth=user` where session/user context applies.
- public webhooks require cryptographic provider authentication.
- consistent error codes.
- idempotency key for create/retry-sensitive endpoints.
- pagination with bounded maximum.
- no raw `sudo()` authorization bypass.

---

## 2. Standard Error

```json
{
  "success": false,
  "error": {
    "code": "PAYMENT_OVER_ALLOCATION",
    "message": "Human-readable message",
    "details": {}
  },
  "request_id": "..."
}
```

Business errors use stable code, not string matching.

---

## 3. Idempotency Header

Recommended:
```text
Idempotency-Key: <client-generated-uuid>
```

Server stores/reuses result for sensitive POST where applicable.

---

## 4. Account APIs

### Balance
`POST /api/v1/utility/billing/balance`

Input:
```json
{"customer_number":"..."}
```

Authorization:
- portal owns account.
- internal scoped by policy.

### Bills
`POST /api/v1/utility/billing/bills`

Supports:
- pagination.
- period/state filters.
- no unbounded result.

---

## 5. Payment Intent

`POST /api/v1/utility/billing/payment_intent`

Input:
- order reference/id.
- amount.
- provider.
- inbound/outbound where permitted.

Validation:
- bill belongs to caller scope.
- provider active and permitted.
- amount valid.
- current residual under lock at confirmation.

---

## 6. Payment Webhook

`POST /api/v1/utility/payment_gateway/webhook/<reference>`

Target security:
- HMAC signature.
- timestamp.
- nonce.
- replay window.
- provider reference uniqueness.
- idempotent done response.

Never rely only on a secret included in body long-term.

---

## 7. AMI Callback

`POST /api/v1/utility/ami/reading_callback`

Required:
- authenticated provider.
- meter identifier.
- value.
- timestamp/provider reading ID.
- optional explicit period subject to validation.

Server:
- validates provider.
- resolves meter/period.
- creates reading idempotently.
- runs VEE policy.

---

## 8. Reading Batch Upload

Target endpoints:
```text
POST /api/v1/utility/readings/batches
POST /api/v1/utility/readings/batches/<uuid>/lines
POST /api/v1/utility/readings/batches/<uuid>/finalize
GET  /api/v1/utility/readings/batches/<uuid>/status
```

Payload format may use JSON/NDJSON/multipart according to client benchmark.

Batch finalize dispatches durable processing after staging is persistent.

---

## 9. Service Request

`POST /api/v1/utility/operations/service_request`

Portal:
- only own account.
- allowed service types policy.
- no ability to force internal state/technician/region.

---

## 10. Media

```text
GET /utility/media/<asset_uuid>/<variant>
```

Variants allowlist:
- original.
- review.
- thumbnail.

Authentication + business/geographic authorization required.

Target bytes delivered by NGINX internal redirect.

---

## 11. Reports

Internal reports must honor assigned region scope even when filters are omitted.

Do not let caller-supplied `region_id` broaden access.

Effective domain:
```text
authorized_regions ∩ requested_filter
```

---

## 12. Pagination

Response:
```json
{
  "items": [],
  "pagination": {
    "limit": 40,
    "next_cursor": "..."
  }
}
```

Prefer cursor/keyset for very large queues; avoid large OFFSET under scale.

---

## 13. Rate Limiting

Redis-backed target rate limits:
- batch upload.
- AMI callback.
- payment intent.
- public webhook by provider/IP/reference policy.

429 includes retry guidance.

---

## 14. API Audit

Record:
- request ID.
- actor/provider.
- endpoint/event.
- business reference.
- status.
- duration.
- idempotency key.
- sanitized error.

Never log full secrets or sensitive payload unnecessarily.

---

## 15. API Acceptance

- authorization isolation.
- duplicate idempotency.
- replay webhook.
- pagination.
- oversized payload rejection.
- invalid media.
- closed period reading.
- concurrent payment intent confirmation.
