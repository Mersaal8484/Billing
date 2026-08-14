# Current V1 Implementation Baseline

**Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Branch:** `development`
**Reviewed SHA:** `51e8dba5c47ed8ff9d1485b519e1b1586cb30522`
**Commit:** `dev ++ ----------- enhance lifecycle impv 13 ui ux +1`
**Reviewed Date:** 2026-08-14
**Documentation Version:** 2.1
**Status:** CURRENT V1 implementation truth

This document answers: **what is actually implemented now?** It does not describe speculative V2 scale infrastructure.

## 1. Current module chain

```text
date_range
    ↓
utility_core
    ↓
utility_inventory
    ↓
utility_operations
    ↓
utility_billing
```

`utility_prepaid` is **OUT OF SCOPE** for the V1 release boundary.

## 2. Sources of truth and ownership

- Odoo/PostgreSQL is the operational System of Record.
- `utility_core` owns the persisted operational `utility.reading` model and core validation hooks.
- `utility_billing` extends the same model with commercial fields and behavior: `is_billable`, `billing_anchor_id`, `billing_component_ids`, `included_sale_order_id`, `carried_consumption`, `billing_consumption`, and `billing_error`.
- Billing does not move commercial reading fields back into Core and Core does not dynamically detect whether Billing is installed.
- Standard Odoo `stock.lot`/stock movements remain physical inventory truth; `utility.meter` is the logical operational meter identity.
- Standard Odoo `account.move` and `account.payment` remain financial truth. There is no parallel ledger and no customer wallet.

## 3. Current workflows

### Reading

The compatible V1 state set is:

```text
draft → under_review → approved → queued → billed
                         └──────→ error
```

`billing_state` is not a current implementation field; any separation is TARGET / FUTURE OPTIONAL DESIGN.

### Reading Batch

`utility.reading.batch` uses bounded background processing through Cron, ownership validation, total validation, malformed JSON validation, eligible-period filtering, and concurrency control using `FOR UPDATE NOWAIT` with SQLSTATE `55P03` handling. The lifecycle is:

```text
uploaded → processing → done
                    ├── partial
                    └── error
```

The current operational UI exposes `total_readings`, `processed_count`, `error_count`, `image_count`, `progress_percent`, active-batch default filtering, and a needs-attention filter.

### Billing and accounting

The commercial Bill is represented by `sale.order`; an Accounting Invoice is `account.move`. The current Bill form provides direct navigation to related accounting invoices, payments, and billing adjustments. Payment allocation is explicit to the selected utility invoice; partner-wide arbitrary reconciliation is rejected.

### Payment gateway

The callback path verifies the transaction and token before taking the row lock, uses constant-time comparison where applicable, allows only pending transitions, sanitizes callback payloads, requires a provider reference for successful settlement where applicable, and is idempotent for repeated successful callbacks. The intended artifact invariant is one successful callback → one `account.payment`.

### Write-off

```text
draft → approved → applied → linked Credit Note
           └──────→ draft   (only before financial application)
```

Approval requires `draft`; application requires `approved`; `FOR UPDATE`, existing `move_id`, `copy=False`, readonly evidence, and restricted deletion prevent duplicate financial artifacts. After application, reopening, re-approval, and re-application are forbidden. One write-off creates at most one generated Credit Note.

### Operations and inventory

Critical operational forms use named action transitions with readonly state fields and non-clickable statusbars. Installation, work order, inspection, and alarm lifecycles expose terminal/error paths in the UI. Meter replacement is an operational orchestration over standard stock movements and requires explicit confirmation before immediate execution.

## 4. Security and migration

- Sensitive operational wizards no longer grant broad `base.group_user` access. Supervisor-access operations are separated from admin-only network/master creation.
- Important operations include server-side `AccessError` guards where implemented; UI groups are not the sole security boundary.
- API ownership checks restrict records to the authorized customer/user scope.
- Migration staging is persistent, bounded, retryable, lock-aware, and traceable to source data. Manual Run Now remains an admin-only/test-oriented path where present; normal processing is background-driven.

## 5. Current API contract

Verified billing and Reader API hardening uses this normalized error envelope on updated endpoints:

```json
{
  "success": false,
  "code": "VALIDATION_ERROR",
  "error": "..."
}
```

Reader confirmation translates expected `AccessError`, `UserError`, and `ValidationError` into deterministic business errors. Unexpected database/integrity/programming failures are not the desired generic business response. This contract is verified for the updated billing/reader scope, not assumed for every endpoint in the repository.

## 6. Evidence and limits

Regression test files exist for core/billing ownership, Reader/API hardening, gateway idempotency, payment allocation, financial lifecycle, write-off, sensitive wizard permissions, and reading-batch concurrency. This document records test existence only; it does not claim that a full runtime suite, CI, concurrency proof, upgrade rehearsal, or production load test passed at this SHA.

**DEFERRED:** runtime/CI proof, production-scale load validation, and `stock.quant` N+1 optimization until profiling confirms meaningful impact.

## Security baseline qualification

Functional roles are CURRENT V1. The current code also has user-assigned Regions and Routes plus selected company/region/route rules. A complete unified `GLOBAL/RESTRICTED` Region/Branch isolation layer is not currently implemented/proven; it is **TARGET V1 SECURITY HARDENING**. The canonical `utility.region` hierarchy is `region/area/zone`, where `area` is the organizational Branch; there is no separate Branch model or user-level explicit Branch assignment yet.
