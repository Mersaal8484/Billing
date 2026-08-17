# MEDIA ARCHITECTURE

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `51e8dba5c47ed8ff9d1485b519e1b1586cb30522`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 2.1
**Last Verified Date:** 2026-08-14
**Status:** Current V1 + Target V2

**Document Type:** Canonical Evidence & Media Storage Specification

> تحديد Media Asset، التخزين، variants، security، delivery، revisions، repair والأداء.

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
utility.media.asset
```

يحفظ identity/metadata/business linkage.

`ir.attachment` Backend توافق حالي، وليس Source of Truth النهائي.

---

## 2. Variants

- Original: evidence master.
- Review: optimized reviewer image.
- Thumbnail: queues/lists.

Rule:
```text
List → Thumbnail
Reviewer → Review
Full-resolution → Original on explicit request only
```

---

## 3. Internal Contract

```python
store_media(raw_bytes, ...)
```

Media Service accepts raw bytes only.

Boundary adapters are responsible for:
- Base64 decode.
- HTTP multipart extraction.
- API payload decode.

---

## 4. Validation

Before ready:
- decode successful.
- supported image format.
- Pillow verify.
- MIME detection from bytes.
- max size/dimensions policy.
- optional rotation/orientation normalization.
- generate variants.

Invalid bytes never become Ready.

---

## 5. Revision

Evidence replacement:
```text
Asset v1
 → New Upload
 → Asset v2
```

No destructive overwrite of historical evidence.

Store:
- revision number.
- previous asset/revision linkage or auditable history.
- replaced_by/replaced_at/reason where required.

---

## 6. Target Storage

Current:
```text
Attachment Adapter
```

Target:
```text
Organized Filesystem outside Odoo
 + NGINX delivery
```

Future:
```text
S3-compatible adapter
```

Business/UI do not change.

---

## 7. Authorized Delivery

```text
Browser
 → /utility/media/<asset_uuid>/<variant>
 → auth=user
 → asset lookup
 → geographic/business access
 → internal storage reference
 → X-Accel-Redirect
 → NGINX bytes
```

Never expose filesystem path directly.

---

## 8. Geographic Security

Media access follows linked reading/replacement/service geography.

- Admin unrestricted.
- non-admin requires assigned region.
- unresolved region defaults deny.
- unlinked/orphan asset cannot silently become public.

---

## 9. ETag & Cache

- ETag based on asset UUID/revision/variant.
- auth/security before disclosure.
- 304 supported.
- `private` cache policy.
- revision in URL/query may bust stale cache.

---

## 10. Legacy Repair

Scanner classification:
- VALID
- DOUBLE_BASE64
- INVALID_IMAGE
- MISSING_VARIANT
- ORPHAN
- BROKEN_ATTACHMENT

Repair:
1. dry run.
2. identify recoverable.
3. decode once if double base64.
4. validate.
5. regenerate variants.
6. preserve asset identity/audit.
7. report unrecoverable.

---

## 11. Performance

Do not read binary to calculate `has_image`.

Use:
- image_asset_id.
- state.
- variant presence.

Reviewer prefetch:
```text
current ±1 ±2 Review
```

No Original prefetch.

---

## 12. Retention

Retention policy must be approved by business/legal before destructive deletion.

Architecture supports:
- hot review storage.
- historical archive.
- checksum/integrity verification.
- restoration of archived evidence.

For the initial annual-rotation sizing target, image bytes have a maximum retention of 365 days. This does not delete `utility.media.asset`, reading metadata, or audit history. Database archive retention is independent from image-byte retention; an archived yearly database may therefore show expired evidence rather than expose the original file.

Deletion must be a bounded, resumable, audited job with dry-run reporting, checksum/state checks, and an exception path for legal holds or an explicitly approved business retention override.

---

## 13. Acceptance

- JPEG/PNG/WebP upload.
- raw-byte validation.
- Base64 boundary normalize.
- re-upload revision.
- 403 outside region.
- 404 missing asset.
- 200 valid image body.
- ETag 304.
- legacy double-base64 repair.
- NGINX/X-Accel target delivery.

## V2.1 Current vs Target

**CURRENT V1:** media is represented through the current `utility.media.asset`/attachment compatibility path and protected by ownership/geographic authorization. Reading and batch UIs expose operational image evidence without making media storage a second business truth.

**TARGET V2 / CONDITIONAL:** organized filesystem/NGINX or S3-compatible storage behind a storage-agnostic Media Adapter. Delivery scaling is triggered by measured attachment volume, latency, or backup impact; it is not a current V1 deployment assumption.

**TARGET V2 / CONDITIONAL:** the initial recommendation is `ir.attachment` backed by a shared Odoo Filestore with 4 TB usable capacity. MinIO is intentionally deferred until measured storage/IOPS, retention, public-upload, object-size, or immutability triggers justify it.
