# API SPECIFICATION

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

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

## V3.2 Current API Contract

**CURRENT V1 verified scope:** updated Billing and Reader endpoints use:

```json
{"success": false, "code": "VALIDATION_ERROR", "error": "..."}
```

Verified stable codes include `VALIDATION_ERROR`, `CUSTOMER_NOT_FOUND`, `ORDER_NOT_FOUND`, `INVALID_LIMIT`, `INVALID_INVOICE`, `INVOICE_REQUIRED`, `AMOUNT_EXCEEDS_RESIDUAL`, `BILL_NOT_PAYABLE`, `PAYMENT_PROVIDER_UNAVAILABLE`, `PAYMENT_DIRECTION_UNSUPPORTED`, `TRANSACTION_NOT_FOUND`, `AUTHENTICATION_REQUIRED`, `INVALID_TOKEN`, `INVALID_TRANSACTION_STATE`, `PAYMENT_FAILED`, `BATCH_NOT_FOUND`, `BATCH_NOT_EDITABLE`, `INVALID_BASE64`, `IMAGE_TOO_LARGE`, and `BUSINESS_RULE_ERROR`. This is not an unverified claim that every repository endpoint has identical payloads.

- **Reader & Customer APIs (`/api/v1/reader/customers`, `/api/v1/reader/reading_batches`):**
  - Resolves assigned routes via `utility.meter.reader` and `res.users.assigned_route_ids`.
  - Returns paginated subscriber lists filtered by assigned routes, active status, and address details.
- **Authentication & Dynamic Roles (`/api/v1/auth/profile`, `/api/v1/auth/token`):**
  - Exposes user metadata, assigned groups, active company, and assigned geographical scopes.
  - Dynamically informs client UI of operational capabilities (Collector, Reader, Supervisor).

Reader confirmation translates expected `AccessError`, `UserError`, and `ValidationError` into deterministic business errors. `IntegrityError`, `OperationalError`, unexpected database exceptions, and programming failures are not the desired generic business response.

Gateway callback order is authentication/token verification, constant-time comparison where applicable, then `FOR UPDATE`; only pending transactions transition. Successful callbacks require a provider reference where applicable and are idempotent, producing one `account.payment`.

## Organizational Scope and API Isolation

**CURRENT V1:** authenticated customer ownership and selected company/region checks are implemented for the verified endpoint scope. Internal account resolution still follows the current Odoo environment/rules; the repository does not yet prove a unified user `GLOBAL/RESTRICTED` Region/Branch scope for every endpoint.

**TARGET V1 Security Hardening:** when `sudo()` is required, resolve the authenticated user's allowed company and organizational scope first, include that scope in the lookup/domain, and reject valid-but-out-of-scope identifiers. Never use `sudo().browse(user_supplied_id)` as sufficient authorization.

API acceptance must cover same-role different-region users, multiple regions, region plus explicit branch, empty restricted scope, out-of-scope IDs, dashboards/aggregates, and exports.
