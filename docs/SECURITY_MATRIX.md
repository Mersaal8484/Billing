# SECURITY MATRIX

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `51e8dba5c47ed8ff9d1485b519e1b1586cb30522`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 2.1
**Last Verified Date:** 2026-08-14
**Status:** Current V1 + Target V2

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

## V2.1 Current Implementation Synchronization

**CURRENT V1:** broad `base.group_user` access was removed from sensitive operational creation wizards. Supervisor-access operations cover approved operational mutations; private transformer, transformer, and feeder creation remain admin-only network/master mutations. Important actions use server-side `AccessError` guards where implemented.

The governing rule is: wizard access must not be broader than the most sensitive model mutation it performs. UI groups improve permission UX but are not the sole security control. API ownership checks and callback authentication are part of the same boundary.

For gateway callbacks, authentication/token verification occurs before row-level locking; repeated authenticated success is idempotent and must not create a second payment. Sensitive callback payloads are sanitized before persistence/logging.

## Organizational Security & Data Isolation — V2.1

Security has two independent axes:

```text
Role Permissions ∩ Company Scope ∩ Organizational Scope
```

### CURRENT V1 evidence

- Functional role groups are authoritative in `utility_core/security/utility_security.xml` and remain independent of geography.
- `res.users.assigned_region_ids` and `assigned_route_ids` exist.
- Company boundaries use standard `company_ids` rules on many models.
- Route/region rules exist for selected Customer, Reading, Sale Order, Payment Allocation/Settlement, Auditor, Collector, and Technician paths.
- API ownership checks exist for selected customer, billing, service-request, media, and Reader flows.

### TARGET V1 Security Hardening

The following are not claimed as fully implemented: explicit `GLOBAL/RESTRICTED` scope mode, user-level `allowed_branch_ids`, Region-to-Branch automatic expansion, explicit extra-branch assignment, and a complete organizational Record Rule layer across every operational and financial relation.

The canonical hierarchy is `utility.region(type=region → area → zone)`: `type='region'` is Region, `type='area'` is the organizational Branch, and `type='zone'` is the lower operational zone. A separate Branch model must not be introduced. What remains TARGET is user-level Branch assignment, Region-to-area expansion, and comprehensive enforcement.

| Role | Functional capability | Target scope |
|---|---|---|
| Meter Reader | Submit readings | Assigned Regions/Branches |
| Technician | Execute field work | Assigned Regions/Branches |
| Supervisor | Assign/approve operations | Assigned Regions/Branches |
| Billing User | Billing operations | Assigned Regions/Branches |
| Billing Manager | Billing approval/management | Assigned scope or explicit Global |
| Auditor | Read-only audit | Assigned scope or explicit Global |
| Utility Admin | System administration | Explicit Global by policy |

Empty restricted scope must be default-deny, never implicit global. Do not create geographic groups such as `Billing Manager Sana'a`.
