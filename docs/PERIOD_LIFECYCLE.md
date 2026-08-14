# PERIOD LIFECYCLE

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `51e8dba5c47ed8ff9d1485b519e1b1586cb30522`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 2.1
**Last Verified Date:** 2026-08-14
**Status:** Current V1 + Target V2

**Document Type:** Operational Period & Cycle Lifecycle Specification

> تثبيت دورة Reading/Payment، generation، scope، transitions، reopen، audit وإغلاق الفترة.

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


## 1. Cycle Structure

```text
cycle_key
├── Reading & Review Period
└── Payment Period
```

Examples:
```text
MONTHLY-2026-08
SEMI-2026-08-H1
SEMI-2026-08-H2
```

---

## 2. Reading Period Semantics

- `date_start/date_end`: consumption bounds.
- `reading_window_start/end`: operational intake/review window.
- Reading + Review = one phase.

State machine:

```text
planned → open → closing → closed → locked
```

---

## 3. Payment Period Semantics

- independent payment window.
- exact scope snapshot from Reading period.

State machine:

```text
planned → open → closing → reconciled → locked
```

---

## 4. Reopen

Allowed source:
- `closing`
- `closed`
- `reconciled`

Action:
```text
action_reopen_period(reason)
```

Result:
```text
open
```

Must audit reason/user/timestamp.

Locked normally cannot reopen.

---

## 5. Generator

Only `utility.period.generator` creates cycle pairs in normal operation.

Atomic process:
1. resolve strict period types.
2. calculate consumption bounds.
3. calculate timezone-aware windows.
4. resolve authoritative regions.
5. create Reading period.
6. create Payment period linked to Reading.
7. return both in same transaction.

No manual commit.

---

## 6. Offsets

Relative to `consumption_end`.

Defaults:
- reading start -2.
- reading end +3.
- payment start +1.
- payment end +13.

Zero is valid and must not be replaced by falsy fallback.

---

## 7. Geographic Authority

Reading:
```text
all active root regions matching cadence
```

Payment:
```text
exact Reading.region_ids snapshot
```

At planned→open:
- final sync.
- reject zero matching regions.
- freeze scope.

---

## 8. Protected Fields

After planned:
- cycle_key.
- region_ids.
- billing_cadence.
- period_role.
- reading_period_id.

No bypass except named internal operation with audit.

---

## 9. Closing Rules

### Reading
Before `closing → closed`:
- no processing/uploaded batches.
- no unresolved draft/under_review/error/queued readings.
- no approved periodic reading without bill.
- every Utility Bill has posted accounting invoice.

### Payment
Before `closing → reconciled`:
- payment reconciliation policy must validate configured outstanding/exception conditions.
- unresolved payment exceptions require explicit policy/waiver.

---

## 10. Period Impact Engine

Target helper:
```text
_get_period_impact()
```

Returns:
- readings.
- approved.
- bills.
- posted invoices.
- payments.
- batches.
- exceptions.

Adjust Wizard uses impact policy, not scattered queries.

---

## 11. Migration

Legacy states must map to new state model in upgrade migration, followed by validation report.

No stale legacy-state checks may remain in runtime code.

---

## 12. Audit Log

`date.range.log` must capture:
- action type.
- old/new state.
- changed fields.
- old/new values.
- reason.
- user.
- timestamp.
- workflow IDs.

---

## 13. Acceptance Scenarios

- monthly pair.
- semi H1/H2 pair.
- idempotent regeneration.
- regeneration rejection after open.
- zero-offset windows.
- timezone correctness.
- region freeze.
- audited reopen.
- locked rejection.
- closing with unresolved readings rejects.
- close after fully billed/posted succeeds.

## V2.1 Current Implementation Synchronization

**CURRENT V1:** reading periods and payment periods remain distinct concepts linked by the accepted cycle semantics. Eligibility, open/closed/locked checks, billing-period validation, and controlled correction paths remain in the Odoo domain models. Period closure must not be represented as a destructive rewrite of historical billing evidence.

**TARGET V2:** larger-scale period partitioning and long-running workflow coordination are conditional scale decisions, not current lifecycle states.
