---
name: odoo-framework-best-practices
description: >-
  Technical Odoo 16 ORM standards, OCA code quality rules, N+1 query prevention,
  safe sudo() scoping, multi-company/branch record rules, XML load ordering, and
  OWL JS component best practices for Utility ERP.
---

# Odoo 16 Framework & OCA Best Practices

This skill defines technical engineering guardrails, ORM performance patterns, security boundaries, and OCA quality standards for developing and maintaining Odoo 16 addons in `utility_erp`.

---

## 1. ORM Performance & Query Optimization

- **Avoid N+1 Queries**:
  - Avoid ORM searches or SQL inside per-record loops when they produce N+1 behavior.
  - Batch/prefetch whenever practical.
  - Do not refactor a loop solely on static appearance; profile or verify query behavior when performance impact is uncertain.
  - Use `.mapped()`, `.filtered()`, or `.filtered_domain()` for recordset filtering in memory.
  - Use `search_count(domain)` instead of `len(search(domain))`.
- **Field Indexing**:
  - Add `index=True` to Foreign Key fields (`Many2one`) that are heavily queried in domains, search views, or record rules (e.g., `meter_id`, `contract_id`, `area_id`).
- **Batching Operations**:
  - Perform record creation and updates in batch where possible (`create([{...}, {...}])` or `.write({...})` on a recordset).

---

## 2. Security, Sudo Scoping & Multi-Branch Safety

- **Scoped `sudo()`**:
  - Avoid unscoped `sudo()` calls across business logic.
  - When bypassing security for automated tasks (e.g., cron jobs or webhooks), explicitly scope down using `.with_user()` or limit the accessed field set to prevent privilege escalation.
- **Multi-Company & Branch Isolation**:
  - Every scoped business model must have a deterministic company/organizational scope path.
  - Do NOT add `branch_id` mechanically to every model. Prefer canonical related/derived scope from the owning business entity. Add a stored readonly/indexed scope field only when security or performance evidence justifies it.
  - Add explicit record rules in `security/ir_rule.xml` enforcing company and branch data isolation.

---

## 3. XML Loading Sequence & Manifesto Management

- **Manifest Load Order (`__manifest__.py`)**:
  1. Security files: `security/ir.model.access.csv`, `security/ir_rule.xml`
  2. Data files: `data/ir_sequence_data.xml`, default records
  3. Views & Actions: `views/*.xml`
  4. Menus: `views/menu_views.xml` (placed at the bottom to ensure referenced actions exist)
  5. Wizards & Reports: `wizards/*.xml`, `reports/*.xml`
- **XML ID Namespacing**:
  - Prefix XML IDs with module-specific prefixes (e.g., `utility_core_`, `utility_billing_`) to avoid cross-module ID collisions.

---

## 4. Exception Contracts & Logging

- **Business Errors vs Systems Failures**:
  - Use Odoo native `UserError` for expected user mistakes, `ValidationError` for field constraint failures, and `AccessError` for security violations.
  - Do NOT catch generic `Exception` around ORM transactions; let database rollbacks execute naturally.
- **Logging**:
  - Use `logging.getLogger(__name__)` instead of `print()`. Log critical operational events at `info` or `warning` level.

---

## 5. UI/UX & Translation Standards

- **Odoo-Native Views**:
  - Statusbar for state fields (`widget="statusbar"`).
  - Clear workflow action buttons with `states` or `attrs` visibility guards.
  - Search views must include relevant `filters`, `group_by`, and search fields.
- **Arabic Translation**:
  - Wrap user-facing string literals in `_('String')` for translation support.
