---
name: utility-billing
description: Use for Utility ERP readings, reading batches, sale-order bills, invoices, payments, penalties, write-off navigation, billing APIs, and billing UX.
---

# Utility billing

Apply this skill to postpaid reading-to-bill-to-payment workflows and their operational screens.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/ARCHITECTURE_DECISION_LOG.md`
- `docs/BILLING_ENGINE.md`
- `docs/READING_BATCH_ARCHITECTURE.md`
- `docs/ACCOUNTING_FLOWS.md`
- `docs/UAT_PLAN.md`

## Boundaries

- `utility.reading` is unified and based in `utility_core`; financial extensions belong to billing.
- The utility Bill is an inherited `sale.order`; the posted Invoice is `account.move`; payments are `account.payment`.
- Preserve the Core/Billing ownership boundary and do not revive deleted legacy models.
- Payment, invoice, and settlement navigation must follow actual links, not inferred partner-wide searches.

## Workflow

1. Trace reading state, batch state, bill state, invoice creation, payment allocation, and error handling.
2. Keep batch operations bounded, idempotent, auditable, and explicit about `partial` or `error` outcomes.
3. Review search views, default filters, smart buttons, and role visibility with the same rigor as backend code.
4. Add focused tests for invalid input, duplicate webhook or billing execution, ownership, and financial links.
