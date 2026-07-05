# AGENTS.md — Utility ERP

## Project

Odoo 16.0 ERP for electricity distribution companies. 6 addon modules under `utility_erp/`.

## Module dependency order

1. `utility_core` — master data: customers, accounts, meters, tariffs, 8-level NUTS hierarchy (region→area→zone→office→substation→feeder→transformer→route), subscriber categories, contract templates, formulas, settings
2. `utility_inventory` — inventory & warehouse management: storage locations, stock items, movements, physical counts, meter serialization & tracking
3. `utility_prepaid` — prepaid vending: STS tokens, sales, payments, cashier shifts
4. `utility_operations` — field ops: service orders, inspections, tamper cases, meter replacement, reading/financial settlements
5. `utility_billing` — postpaid billing: meter readings, billing cycles, sale orders, penalties, recurring invoices
6. `utility_portal` — customer portal + REST API (depends on everything above)

Install in that order. `utility_core` must always be first.

## Test commands

No test infrastructure exists yet. All `tests/` directories are empty. Do not run `odoo-test` or similar — there is nothing to execute.

## Key workflows & quirks

- **`utility.bill` replaced by `sale.order` inheritance** — `utility_billing/models/utility_sale_order.py` inherits `sale.order` and adds all utility billing fields (`account_id`, `meter_id`, `reading_id`, `date_range_id`, `period_start/end`, `previous_reading`, `current_reading`, `consumption`, `tariff_id`, `amount_energy/fixed/service/penalty`, `amount_paid`, `balance_due`, `is_overdue`, `bill_state`).
- **`utility.bill.line` replaced by `sale.order.line` inheritance** — adds `is_tax` field only.
- **`utility.collection` replaced by `account.payment`** — `utility.collection` model deleted. Payments tracked via `account.payment` with `utility_sale_order_id` link.
- **`utility.payment.allocation` deleted** — no longer needed.
- **`utility.writeoff` kept** but `bill_id` → `sale_order_id`.
- **`utility.deposit` kept** unchanged.
- **`utility.penalty` kept** but `bill_id` → `sale_order_id`; `cron_calculate_late_penalties` searches `sale.order`.
- **`bill_state` field** (separate from `sale.order.state`) controls utility lifecycle: `draft → confirmed → sent → paid → overdue → cancelled`.
- **`_calculate_amounts()`** creates `sale.order.line` records from tariff/contract template; `order_line` replaces `line_ids`.
- **Meter reading state machine**: `draft → under_review → approved → billed` (not Odoo default `draft→validated→billed`). Rejection returns to `draft`.
- **8-level NUTS hierarchy** — uses flat `parent_id` fields (no `parent_store`/`parent_path` like legacy PEC system did).
- **Dynamic billing formulas** — `utility.formula` model executes Python via `safe_eval()`. Variables: `consumption`, `previous_reading`, `current_reading`, `tariff`, `account`, `category`, `line`, `result`, `name`.
- **Security groups** are flat (all imply `group_utility_admin`). Not a proper hierarchy — a known issue from the gap analysis.
- **Arabic UI** — model descriptions, field strings, menu labels, and view content are in Arabic (using `translate=True` on many fields).
- **Config settings** live in `utility_core/models/utility_settings.py` as `res.config.settings` inherit with `config_parameter` keys (`utility.*`).
- **Communication & Notifications** — NEVER use Odoo's standard `mail` module or email functionality, as there is no mail server. All customer notifications must be routed through SMS or a local WhatsApp provider.
- **Subscriber Terminology & Rules**:
  - `utility.subscriber.category` = **فئات المشتركين الرئيسية** (Subscriber Categories)
  - `utility.subscriber` = **انواع المشتركين** (Subscriber Types)
  - Both fields are mandatory on contract templates (`utility.contract.template`) and subscriber accounts (`utility.customer`). The selected type must belong to the selected category, and both must be compatible with the selected contract template.
  - In `utility.customer` and `utility.customer.wizard`, the contract template field (`contract_template_id`) must only display and accept templates that are suitable for both the selected subscriber classification (categories & types) and the geographic location (regions & areas).



## Important files

- `EXECUTION_PLAN.md` — Arabic implementation plan (reading workflow, contracts, discounts)
- `GAP_ANALYSIS_PLAN.md` — gap analysis vs legacy PEC system
- `utility_core/security/utility_security.xml` — all 9 security groups
- `utility_core/views/utility_settings_views.xml` — settings form view
- `utility_billing/models/utility_sale_order.py` — main billing model (sale.order inherit, `_calculate_amounts()` for dynamic line computation)
- `utility_billing/data/utility_cron_extras.xml` — cron jobs including `cron_update_overdue_orders`, `cron_send_due_reminders`
- `utility_billing/views/utility_sale_order_views.xml` — sale.order tree/form/search views with utility fields

## Known gaps (from GAP_ANALYSIS_PLAN.md)

| Gap | Priority |
|-----|----------|
| Rule engine (7 models) | 🔴 Critical |
| Recurring contracts automation | 🔴 Critical |
| Settings & configuration | 🟡 Medium |
| Analytic account integration | 🟡 Medium |
| Meter replacement module | 🟡 Medium |
| Reading/financial settlements | 🟢 Nice-to-have |
| Advanced reports (transformer balance, customer statement) | 🟢 Nice-to-have |
| Barcode OCR service | 🟢 Nice-to-have |

## Development commands

Standard Odoo 16.0 addon path. No custom Makefile, pre-commit, linter, or typecheck configuration exists. No CI workflows detected.

## date_range model

`utility_core` inherits Odoo's standard `date.range.type` and `date.range` (`utility_core/models/utility_date_range.py`). Adds: `parent_type_id`, `fiscal_year` to type; `parent_id`, `previous_range_id`, `billing_period`, `work_type`, `is_current_period` to range. Requires the `date_range` Odoo module as a dependency.

## Unified Reading Model (Transformer/Cell/Subscriber Readings)

The old `utility.transformer.reading` model has been deleted. Reading of transformers, cells, and subscribers is now unified under the main `utility.reading` model in `utility_core` (with financial extensions in `utility_billing`). Each `utility.reading` supports reading classifications (subscriber, cell, feeder, transformer). Refer to `docs/MOVE_READING_MODEL_TO_CORE.md` for details.

## Transformer/cell hierarchy (`utility.transformer`)

Both cells and transformers share the same model `utility.transformer` with `_parent_store` hierarchy. A cell (`is_cell=True`) can have multiple child transformers (`parent_id` → cell). Cell-specific fields (`coupling_meter_id`, `cell_account_ids`, distribution, loss) apply to both cells and standalone transformers. Customers link to their transformer via `cell_id`.

## Deleted models (replaced by Odoo standards)

| Deleted Model | Replaced By |
|---|---|
| `utility.bill` | `sale.order` (inherited) |
| `utility.bill.line` | `sale.order.line` (inherited) |
| `utility.collection` | `account.payment` |
| `utility.payment.allocation` | *(removed)* |
| `utility.sale` | `pos.order` (inherited) |
| `utility.sale.line` | `pos.order.line` (inherited) |
| `utility.payment` | POS payment methods |
| `utility.receipt` | POS receipt |
| `utility.transformer.reading` | `utility.reading` (unified) |


## Prepaid via POS

- **`utility.token`** retains STS token logic but links to `pos.order` (via `pos_order_id`)
- **`utility.cashier.shift`** now `pos_order_ids` (One2many to `pos.order`) replaces old `sale_ids`
- **`utility.transaction`** `pos_order_id` replaces `sale_id`/`payment_id`
- **`utility.reversal`** `pos_order_id` replaces `sale_id`/`payment_id`
- **Billing cashier shift extension** adds `payment_ids` (account.payment) to track bill collections alongside prepaid POS orders
- **`pos.order`** inherits utility fields (`account_id`, `meter_id`, `tariff_id`, token fields)
- Token generation triggered via `_generate_token()` on `pos.order` completion

## Project Status & Recent Improvements (وضع المشروع الحالي وتحديثات منطق الأعمال)

As of July 2026, the following major updates and architectural improvements have been implemented:
1. **Module Count**: The project has 6 addon modules (adding `utility_inventory` for storage locations, stock items, serialization, and physical count management).
2. **Unified Readings**: `utility.reading` was moved to `utility_core` as the base model, and `utility_billing` extends it. The old `utility.transformer.reading` was deleted, and all reading types (subscriber, cell, feeder, transformer) are now unified under `utility.reading`.
3. **Security & Sandbox**:
   - `safe_eval` on dynamic formulas is isolated to pass only primitive values (`id`, `name`), preventing ORM context leakage to the formula execution sandbox.
   - API endpoints use `sudo()` coupled with strict ownership validation (`partner_id`) to ensure users can only access their own records.
4. **Operations & States**:
   - Meter replacement conflicts between `utility_core` and `utility_operations` models resolved (using non-conflicting field names).
   - Added `_check_state_transition()` to enforce correct sequential workflow on service orders.
   - Restrict edits on billed readings and enforce settlement-only corrections via `utility.reading.settlement`.
5. **Postpaid Billing & Penalties**:
   - Replaced direct writes of penalty amounts to the sale order inside crons. `amount_penalty` is now a computed field reflecting actual `utility.penalty` records.
   - Penalties generate separate accounting invoices (`account.move`) containing proper partner and product parameters (`fine_account_id`).
6. **Cashier/Collector Shifts**:
   - Added `@api.constrains` validation to prevent overlapping open shifts for the same user.
7. **Performance & Indexes**:
   - Added database indexes (`index=True`) on critical fields: `bill_state`, `balance_due`, `is_overdue` on `sale.order`, `state` on `utility.reading`, and `sale_order_id` on `utility.penalty`.
   - Optimized crons with batching limits (e.g. 500 for penalties, 1000 for overdue orders) and optimized reading computations using bulk queries.

## Odoo 16 Development Squad Role


Act as an Elite Odoo 16 Development Squad, blending the expertise of a Principal Odoo Architect, a Senior Python/Odoo Developer, and a QA/Performance Engineer. Your goal is to deliver production-ready, clean, and highly optimized Odoo 16 source code following the DRY (Don't Repeat Yourself) principle and Odoo/OCA best practices.

When I provide a requirement or a feature request, process it through the following personas internally and output the structured response:

1. [Odoo 16 Solution Architect]
- Analyze the requirement and determine the best approach (Inheritance vs. New Model).
- Define the data model architecture, relationships (m2o, o2m, m2m), and security rules (ir.model.access.csv & record rules).
- Ensure the solution respects Odoo 16's multi-company environment and core framework design.

2. [Senior Odoo 16 Developer]
- Provide clean, modular, and PEP8-compliant Python code.
- Write properly structured XML for views (Form, Tree, Search, Kanban), actions, and menus.
- Use Odoo 16 API decorators correctly (@api.model, @api.depends, @api.onchange, @api.constrains).
- Avoid SQL injection by using proper ORM methods, and optimize queries using read_group, mapped, or filtered where necessary.
- Ensure efficient compute fields (always include tracking/store appropriately and utilize prefetching).

3. [QA & Performance Engineer]
- Identify potential bottlenecks (e.g., heavy loops, missing database indexes on fields used in domains).
- Provide a brief unit test snippet (Odoo TransactionCase) to validate the business logic.
- Highlight any security or performance risks.

Output Format:
- **Architecture Overview**: Brief explanation of the technical design.
- **Python Code**: The complete, production-ready backend code (models, wizards, or controllers).
- **XML Code**: The clean frontend definitions (views, security, data files).
- **Security (CSV/XML)**: Precise security definitions if new models are introduced.
- **Developer Notes & Optimization**: Tips on performance, indexing, and scalability.

Maintain a professional, highly technical, and direct tone. Do not write placeholders like "# TODO: implement this". Provide fully realized code.

