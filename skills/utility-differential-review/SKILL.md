---
name: utility-differential-review
description: Use when reviewing a Utility ERP diff, commit, branch, or pull request for security regressions, financial or stock integrity risks, authorization changes, API exposure, workflow bypasses, or test gaps.
---

# Utility differential review

Apply a risk-first, evidence-based review to changed code. Adapt the differential-review method from Trail of Bits to Odoo's ORM, security model, accounting truth, stock custody, and postpaid billing boundaries.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `AGENTS.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/ARCHITECTURE_DECISION_LOG.md`
- `skills/utility-security-scope/SKILL.md`
- `skills/utility-architecture/SKILL.md`
- The routed domain skill for the changed files

## Review method

1. Establish the exact diff, parent commit, changed-file scope, and relevant history. Do not review only the visible hunk when callers, inherited models, XML data, ACLs, or migrations may be affected.
2. Classify risk before depth: highest risk includes `sudo()`, ACL/record rules, public routes, webhooks, payment/invoice/stock effects, state transitions, imports, and secrets.
3. Trace callers, inherited models, XML IDs, security files, scheduled jobs, APIs, and downstream accounting/inventory effects. Record the blast radius with file and line evidence.
4. Check authorization and ownership separately from UI visibility. Check company and geographic scope, empty-scope behavior, idempotency, concurrency, rollback, and audit links.
5. Check tests for positive, negative, duplicate, wrong-state, cross-scope, and failure-path coverage. Missing tests increase risk; they are not proof of a bug by themselves.
6. Report only actionable findings with severity, evidence, impact, reproduction or attack scenario, and a bounded remediation. State reviewed areas and confidence limits.

## Utility-specific checks

- Preserve `sale.order` as Utility Bill truth, `account.move` as invoice truth, `account.payment` as payment truth, and standard stock as custody truth.
- Reject duplicate ledgers, partner-wide payment allocation, unscoped `sudo()`, bypassed workflow guards, mutable posted history, and silent retry duplication.
- Distinguish CURRENT V1 from TARGET V2 and do not mark a proposal as implemented.
- Do not modify code during review unless the user explicitly requests remediation. Keep the report as an artifact when the review is substantial.
