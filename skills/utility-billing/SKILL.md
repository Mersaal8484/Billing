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
- For billing configuration forms with dependent selectors, enforce the business hierarchy in both the view and model. Apply the relevant chain—`recurring_rule_type → region → area → zone → route`, `substation → feeder → transformer → route`, or `utility.subscriber.category → utility.subscriber`—using the model's actual relations. Show only compatible choices, clear stale choices on parent changes, and reject incompatible RPC/import values server-side.
- Contract-template eligibility is multi-factor rather than a simple chain: `utility.subscriber.category + utility.subscriber + region/area → utility.contract.template`. Filter by all supplied factors, clear a stale template, and verify the template cadence is compatible with the selected geographic cadence.
- Treat the billing cadence as an end-to-end compatibility chain: `utility.contract.template.recurring_rule_type → utility.customer effective cadence → date.range(billing_cadence, reading role) → utility.reading → sale.order bill → linked payment period`. Filter candidates at each selector and enforce the same cadence in server-side constraints; a payment period must inherit the linked reading period's cadence.

## Workflow

1. Trace reading state, batch state, bill state, invoice creation, payment allocation, and error handling.
2. Keep batch operations bounded, idempotent, auditable, and explicit about `partial` or `error` outcomes.
3. Review search views, default filters, smart buttons, and role visibility with the same rigor as backend code.
4. Add focused tests for invalid input, duplicate webhook or billing execution, ownership, and financial links.
