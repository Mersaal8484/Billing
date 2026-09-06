---
name: utility-inventory
description: Use for Utility ERP meters, products, lots, serial numbers, stock custody, replacements, transfers, inventory views, and inventory performance review.
---

# Utility inventory

Apply this skill to meter custody, replacement, stock movement, lot or serial tracking, and inventory-facing UX.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/INVENTORY_CUSTODY.md`
- `docs/METER_REPLACEMENT.md`
- `docs/TECHNICAL_ARCHITECTURE.md`

## Rules

- Standard Odoo stock, quants, pickings, lots, and valuation remain the physical custody truth.
- `utility.meter` is the logical operational record; `utility_inventory` is the stock bridge.
- Replacement actions must validate the workflow, confirm before real stock movement, and remain auditable.
- Do not add a parallel quantity or custody ledger to make a screen convenient.
- Treat `stock.quant` N+1 as performance debt until production profiling proves impact.

## Electrical compatibility

For meter assignment, the technical phase comes from `utility.meter.model.phase`. A meter attached to a transformer or private transformer must match `utility.transformer.phase`; a meter attached to a feeder must match the explicit `utility.feeder.phase`. For a subscriber, validate the meter against `utility.connection.type.phase` on the subscriber connection. Filter compatible meter models and meter types in the form, clear stale choices after a parent phase changes, and enforce the same compatibility in model constraints so imports and RPC cannot bypass it. Do not silently assume every feeder is three-phase.

## Workflow

1. Trace product, lot, serial, picking, and meter links before changing fields.
2. Check state guards, company context, inventory permissions, and rollback behavior.
3. Use batch ORM operations and indexed domains; never add a search inside a record loop.
4. Add tests for invalid replacements, duplicate execution, missing stock links, and confirmation behavior.
