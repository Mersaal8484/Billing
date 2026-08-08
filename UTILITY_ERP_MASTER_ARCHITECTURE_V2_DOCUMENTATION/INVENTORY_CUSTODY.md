# INVENTORY & CUSTODY

**Platform:** Odoo 16 Community  
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`  
**Repository Baseline Commit:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`  
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)  
**Architecture Version:** 2.0  
**Date:** 2026-08-09  
**Status:** Target / Production-Hardening  

**Document Type:** Serialized Meter Inventory & Custody Specification

> بناء دورة فيزيائية كاملة للعداد من الاستلام إلى التركيب ثم الإزالة والإصلاح أو الإهلاك.

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


## 1. Canonical Relationship

```text
utility.meter = logical utility device
stock.lot = physical serialized device
```

Target one-to-one active mapping.

---

## 2. Locations

Configurable locations:
- central meter warehouse.
- regional warehouse.
- technician custody.
- installed/customer logical destination.
- removed meter.
- quarantine.
- testing/repair.
- return-to-vendor.
- scrap.

No unconditional reliance on `stock.stock_location_stock/customers/scrap`.

---

## 3. Lifecycle

```text
Supplier Receipt
 → Available Warehouse
 → Reserved
 → Technician Custody
 → Installed
 → Removed
 → Quarantine
 → Test
    ├── Return to Stock
    ├── Repair
    ├── Return Vendor
    └── Scrap
```

---

## 4. Stock Truth vs Business View

Stock quantities/locations come from Odoo Stock.

Utility-specific display statuses are derived where possible, not duplicated as independent quantity engine.

---

## 5. Reservation

Before install/replacement:
- serial available.
- correct company/warehouse.
- not installed.
- not reserved by another open operation.
- correct product/type policy.

---

## 6. Technician Custody

A technician custody location or controlled ownership relation represents handover.

Transfer documents:
```text
Warehouse → Technician
Technician → Customer Installation
Technician → Warehouse/Quarantine
```

---

## 7. Installation

Installation completion must be atomic at business level:
- stock move validated.
- meter logical connection updated.
- operation completed only after both succeed or compensating policy exists.

---

## 8. Removal

Old meter returns to controlled location, not silently to scrap.

Disposition decided after inspection:
- reusable.
- calibration.
- repair.
- vendor return.
- scrap.

---

## 9. Serialized Controls

- lot/serial required for stocked meters.
- unique serial.
- no duplicate active logical meter.
- no install from unavailable location.
- physical and logical states consistency check.

---

## 10. Stock Service

One reusable service:
- reserve_meter.
- move_to_custody.
- install_meter.
- remove_meter.
- move_to_quarantine.
- return_to_stock.
- scrap_meter.

Operations and Replacement call this service.

---

## 11. Inventory Audit

Each movement traceable:
```text
Service Order/Replacement
 → Picking
 → Move
 → Move Line
 → Lot
 → Meter
```

---

## 12. Acceptance

- supplier receipt serial.
- warehouse transfer.
- technician issue/return.
- install.
- replacement.
- removal/quarantine.
- scrap.
- duplicate serial blocked.
- unavailable meter blocked.
- custody reconciliation report.
