# SECURITY MATRIX

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** Role, Geographic Scope & Authorization Matrix

> توحيد الصلاحيات الوظيفية والجغرافية بين الواجهة والـAPI والـMedia والعمليات.

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


## 1. Roles

| Role | Primary Responsibility |
|---|---|
| Readonly | view permitted data |
| Cashier | manual collection |
| Collector | field collection / routes |
| Technician | service operations |
| Field Inspector | inspection/review evidence |
| Supervisor | operational supervision |
| Billing Manager | billing/period operations |
| Revenue Manager | revenue controls/adjustments |
| Auditor | read-only controlled audit |
| Utility Admin | system administration |

---

## 2. Geographic Rule

Source:
```text
res.users.assigned_region_ids
```

Non-admin with empty regions:
```text
DENY geographic records
```

Utility Admin:
```text
unrestricted
```

---

## 3. Domain Matrix

Legend: R read, C create, W write, A approve/action, — denied, S scoped.

| Domain | Readonly | Cashier | Collector | Technician | Inspector | Supervisor | Billing Mgr | Revenue Mgr | Auditor | Admin |
|---|---|---|---|---|---|---|---|---|---|---|
| Customers | R/S | R/S | R/S | R/S | R/S | R/S | R/S | R/S | R/S | RW |
| Meters | R/S | R/S | R/S | RW/S | RW/S | RW/S | R/S | R/S | R/S | RW |
| Readings | R/S | R/S | CRW/S | CRW/S | RW/A/S | RW/A/S | RW/A/S | R/S | R/S | RW/A |
| Media | R/S | R/S | CR/S | CR/S | RW/S | RW/S | R/S | R/S | R/S | RW |
| Periods | R | R | R | R | R | R | RW/A | RW/A | R | RW/A |
| Utility Bills | R/S | R/S | R/S | R/S | R/S | R/S | RW/A/S | RW/A/S | R/S | RW/A |
| Payments | R/S | CRW/S | CRW/S | R/S | R/S | R/S | R/S | RW/A/S | R/S | RW/A |
| Adjustments | R/S | — | — | — | — | R/S | R/A/S | RW/A/S | R/S | RW/A |
| Service Orders | R/S | R/S | R/S | RW/A/S | RW/A/S | RW/A/S | R/S | R/S | R/S | RW/A |
| Replacement | R/S | — | R/S | RW/A/S | RW/A/S | RW/A/S | R/S | R/S | R/S | RW/A |
| Inventory | R | — | — | RW/S | R/S | RW/A/S | R | R | R | RW/A |
| Integration Config | — | — | — | — | — | R | R | R | R | RW |
| Audit Logs | R/S | — | — | R/S | R/S | R/S | R/S | R/S | R/S | R |

المصفوفة النهائية يجب أن تتحول إلى ACL/Record Rules/Action Guards واختبارات، ولا تعتمد على UI hide وحده.

---

## 4. Authorization Resolution

Unified helpers:
- `get_user_region_domain`.
- `check_account_access`.
- `check_meter_access`.
- `check_reading_access`.
- `check_media_access`.
- `check_replacement_access`.
- `check_service_order_access`.

---

## 5. Route vs Region

Route restrictions يمكن أن تضيق العمل الميداني، لكنها لا تلغي Region policy.

Effective access:
```text
Region Scope
AND
Role Permission
AND
Route/Assignment restriction where applicable
```

---

## 6. API

Internal user لا يعني automatic full `sudo().search([])`.

API:
1. authenticate.
2. build authorized domain.
3. use sudo only after domain/ownership policy resolved.
4. validate resource relation.

---

## 7. Media

Media follows linked business object geography.

No link/unresolved geography:
- admin may inspect.
- non-admin default deny unless explicit policy.

---

## 8. Audit Role

Auditor:
- read-only.
- region scoped.
- cannot approve/alter.
- can access immutable historical evidence within scope.

---

## 9. Security Tests

For each role:
- allowed record.
- other region.
- no-region user.
- forbidden action.
- direct RPC.
- JSON API.
- media URL.
- portal ownership.
- sudo-resistant controller policy.

---

## 10. Secrets

Provider secrets:
- restricted fields.
- masked in UI/logs.
- not returned by API.
- rotated with operational procedure.
