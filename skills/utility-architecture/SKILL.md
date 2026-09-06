---
name: utility-architecture
description: Use for Utility ERP architecture, ownership, dependency, source-of-truth, and current-versus-target design decisions before changing models, modules, or workflows.
---

# Utility architecture

Apply this skill when a request could change module ownership, model boundaries, accounting or inventory truth, dependency order, or the V1/V2 scope.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/ARCHITECTURE_DECISION_LOG.md`
- The relevant domain document named by the index

## Workflow

1. Inspect the live code and classify the request as CURRENT V1, V1 hardening, or TARGET V2.
2. Check the module dependency chain and existing model ownership before proposing a new model or duplicate ledger.
3. Preserve standard Odoo truth: `sale.order` for utility bills, `account.move` for invoices, `account.payment` for payments, and standard stock for custody.
4. Record any boundary or lifecycle change in the appropriate architecture document when documentation is in scope.
5. Implement only the requested scope, then run focused static checks and tests.

## Hard boundaries

- `utility_core` owns master data and the base unified `utility.reading` model.
- Keep the geographic Zone and the technical Transformer as separate Core master-data entities, linked bidirectionally one-to-one. Do not merge their responsibilities: the Zone remains the geographic hierarchy node and the Transformer remains the electrical asset.
- The contract template's cadence is a Core configuration invariant that must remain compatible with the customer's geographic cadence and the reading/payment periods used to bill it. `utility_billing` enforces this when generating bills; do not create a separate billing-period ledger.
- `utility_billing` owns billing extensions and payment APIs; it must not create a parallel bill or payment ledger.
- `utility_inventory` bridges meters to stock and lots; it must not replace stock valuation or custody.
- Do not introduce prepaid vending into the V1 postpaid architecture.
- Treat `CURRENT` facts as code-verified; label proposals as `TARGET` and do not present them as implemented.
