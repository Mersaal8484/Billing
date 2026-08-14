---
name: utility-accounting
description: Use for Utility ERP invoices, payments, allocations, write-offs, penalties, journal entries, reconciliation, accounting permissions, and financial lifecycle reviews.
---

# Utility accounting

Apply this skill to any change that creates, links, posts, allocates, reverses, or restricts a financial artifact.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/ARCHITECTURE_DECISION_LOG.md`
- `docs/ACCOUNTING_FLOWS.md`
- `docs/PAYMENT_ALLOCATION.md`
- `docs/ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION.md`

## Rules

- `account.move` is the invoice and journal-entry truth; `account.payment` is the payment truth.
- Utility bill lifecycle data belongs on the inherited `sale.order`; never create a parallel invoice or payment ledger.
- Payment allocation must target explicit bills or invoices and must not silently apply partner-wide.
- Write-offs need guarded lifecycle transitions, exactly-once financial artifacts, permanent links, and safe re-open rules.
- Posted accounting documents are not ordinary editable business records; use controlled reversal or settlement flows.
- Analyze the impact on `account.move`, `account.payment`, allocation, and write-off before any geographic Record Rule is introduced; naive restrictions can break standard accounting workflows.

## Workflow

1. Trace the existing artifact creation and link fields in code.
2. Define valid transitions, idempotency, concurrency behavior, permissions, and failure rollback.
3. Add regression tests for duplicate execution, wrong-state actions, and missing or stale links.
4. Verify monetary fields, company/currency context, journal configuration, and accounting access without broad `sudo()`.
