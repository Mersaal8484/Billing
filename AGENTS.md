# AGENTS.md — Utility ERP

## Project

Odoo 16.0 ERP for electricity distribution companies. 5 addon modules under `utility_erp/`.

## Module dependency order

1. `utility_core` — master data: customers, accounts, meters, tariffs, 8-level NUTS hierarchy (region→area→zone→office→substation→feeder→transformer→route), subscriber categories, contract templates, formulas, settings
2. `utility_prepaid` — prepaid vending: STS tokens, sales, payments, cashier shifts
3. `utility_operations` — field ops: service orders, inspections, tamper cases, meter replacement, reading/financial settlements
4. `utility_billing` — postpaid billing: meter readings, billing cycles, sale orders, penalties, recurring invoices
5. `utility_portal` — customer portal + REST API (depends on everything above)

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

`utility_core` inherits Odoo's standard `date.range.type` and `date.range` (`utility_core/models/utility_date_range.py`). Adds: `parent_type_id`, `fiscal_year` to type; `parent_id`, `previous_range_id`, `region_id`, `billing_period`, `work_type`, `is_current_period` to range. Requires the `date_range` Odoo module as a dependency.

## Transformer/cell readings

`utility.transformer.reading` (`utility_core/models/utility_cell_reading.py`) is a separate model from `utility.reading`. Used for coupling meter readings and cell/subscriber readings under a transformer. States: `draft → confirmed → cancelled`. Linked to `date.range` via `date_range_id`. Each `utility.transformer` has One2many `coupling_reading_ids` and `cell_reading_ids`.

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

## Prepaid via POS

- **`utility.token`** retains STS token logic but links to `pos.order` (via `pos_order_id`)
- **`utility.cashier.shift`** now `pos_order_ids` (One2many to `pos.order`) replaces old `sale_ids`
- **`utility.transaction`** `pos_order_id` replaces `sale_id`/`payment_id`
- **`utility.reversal`** `pos_order_id` replaces `sale_id`/`payment_id`
- **Billing cashier shift extension** adds `payment_ids` (account.payment) to track bill collections alongside prepaid POS orders
- **`pos.order`** inherits utility fields (`account_id`, `meter_id`, `tariff_id`, token fields)
- Token generation triggered via `_generate_token()` on `pos.order` completion
