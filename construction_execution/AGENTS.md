# AGENTS.md — construction_execution

> 📖 **دليل سير العمل المتكامل** متوفر في:
> `C:\Users\TUF\AppData\Local\Temp\opencode\end_to_end_flow.md`
> ويوثق الـ 13 خطوة من CRM ← 42% إنجاز ← محاسبة مع التواريخ والمبالغ والتسلسل المنطقي.

## Module Identity
- **Model prefix**: `construction.*` (no underscore: `construction.project`, `construction.boq`, `construction.ipc`, `construction.boq.item`, etc.)
- **Manifest**: `__manifest__.py`, version `16.0.X.Y.Z`, depends on `report_xlsx`
- **Entry point**: `__init__.py` imports `models`, `report`, `wizard`, and `post_init_hook`

## Commands
```powershell
# Install
python odoo-bin -d <db> -i construction_execution --stop-after-init

# Upgrade
python odoo-bin -d <db> -u construction_execution --stop-after-init

# Test
python odoo-bin -d <db> --test-enable --test-tags=construction_execution --stop-after-init
```

## Architecture

### Model count: 30+ models across 18 Python files in `models/`

### Dashboard is a raw SQL view
- `construction.dashboard` uses `_auto = False` with `init()` that runs `CREATE OR REPLACE VIEW`
- SQL view reads `p.progress_percent` (stored) and `c.currency_id` via `LEFT JOIN res_company` — **not** from project model's `related` field
- `post_init_hook.py` calls `env['construction.dashboard'].init()` on install; must be run after every upgrade that changes the view

### Security: 10 groups, strict chain hierarchy
Ordered from lowest to highest privilege (must stay in this order to avoid `External ID not found`):
```
auditor → finance → store_keeper → procurement → cost_controller → site_engineer → qs → engineer → manager → director → admin
```
- `group_construction_admin` is implied on `base.group_system` so admins see everything
- Access CSV has a row per model per group; maintain the same pattern when adding models

### Manifest load order matters
Report files (`report/construction_*.xml`) must load **before** `views/construction_menu.xml` and wizard views. Current order in `__manifest__.py` is correct.

### Key computed-field patterns
- **Stored compute**: `store=True` on performance-critical fields (`progress_percent`, `amount`, `total_amount`, etc.)
- **Count fields via `_read_group`**: `_compute_*_count` uses `self.env['model']._read_group(...)` to avoid N+1 queries
- **Monetary fields**: Use `currency_id` field with `related='company_id.currency_id'` and `Monetary` type

### Multi-company
All models set `_check_company_auto = True`. `company_id` is either:
- `related='project_id.company_id', store=True, index=True` (child models)
- `default=lambda self: self.env.company` (standalone models like Resource, Issue, Return)

### Wizards
- `construction.boq.import.wizard` — CSV import (cols: Code, Description, Unit, Qty, Rate)
- `construction.progress.generate.wizard` — generates progress lines from approved BOQ items
- `construction.ipc.generate.wizard` — generates IPC lines from a progress record
- XML views must **not** use dotted paths (e.g., `ipc_id.project_id`); use a `related` field instead (`project_id` related to `ipc_id.project_id`)

### Cron jobs (in `data/construction_cron.xml`, all `noupdate="1"`)
| Method | Model | Interval |
|---|---|---|
| `cron_update_costs()` | `construction.cost.control` | Daily |
| `cron_send_ipc_reminder()` | `construction.ipc` | Weekly |
| `cron_create_monthly_snapshot()` | `construction.progress` | Monthly |
| `cron_update_from_actuals()` | `construction.forecast` | Weekly |

**No `dayofmonth` field** on `ir.cron` in Odoo 16 — don't use it.

### Workflow states
- **BOQ**: draft → submitted → approved → revised
- **Progress**: draft → submitted → approved → cancelled
- **Variation**: draft → submitted → review → approved/rejected → implemented → cancelled
- **IPC**: draft → submitted → reviewed → certified → approved → paid → cancelled
- **Material Request**: draft → submitted → approved → ordered → received → cancelled
- **Budget**: draft → submitted → approved → frozen → cancelled
- **Material Issue / Return**: draft → confirmed → done → cancelled

### Reports (via `report_xlsx`)
- `construction.boq.report` — BOQ with items and sections
- `construction.ipc.report` — IPC with lines
- `construction.progress.report` — Progress measurement

### Translation
- Arabic: `i18n/ar_001.po`
- Bi-lingual models have `arabic_name` / `arabic_description` fields

### Seed data (`noupdate="1"`)
- 7 resource types (Material, Labor, Equipment, Subcontract, Overhead, Profit, Miscellaneous)
- 4 BOQ statuses, 6 MR statuses, 7 IPC statuses
- 8 sequences with prefixes: PRJ-, BOQ-, MR-, MI-, MRT-, VO-, PRG-, IPC-
- 8 config parameters (`ir.config_parameter`) in `construction_config_data.xml`:
  `auto_create_analytic`, `auto_create_project`, `auto_create_tasks`, `default_retention`,
  `default_tax`, `default_analytic_plan_id`, `income_account_id`, `expense_account_id`

### Count fields via `search_count` (not `_read_group`)
`_compute_*_count` methods use `self.env['model'].search_count(...)` per record — simpler
than `_read_group` and avoids cross-version compatibility issues with aggregate specs.

### Count fields via `search_count`
All `_compute_*_count` methods use `search_count` per record after Odoo 16 Community
`_read_group` with `__count` had inconsistent return key format.

### Integration — Inherited Models
| Model | File | Key Fields |
|---|---|---|
| `project.project` | `project_project_inherit.py` | `construction_project_id`, `analytic_account_id` (linked) |
| `project.task` | `project_project_inherit.py` | `boq_item_id`, `construction_project_id` (related) |
| `sale.order` | `sale_order_inherit.py` | `construction_project_id`, `construction_project_code` (related) |
| `sale.order.line` | `sale_order_inherit.py` | `construction_project_id`, `boq_item_id`, `ipc_id` |
| `purchase.order` | `purchase_order_inherit.py` | `construction_project_id`, `construction_project_code` (related) |
| `purchase.order.line` | `purchase_order_inherit.py` | `construction_project_id`, `boq_item_id`, `mr_line_id` |
| `stock.picking` | `stock_picking_inherit.py` | `construction_project_id`, `construction_material_issue_id`, `material_return_id` |
| `stock.move` | `stock_picking_inherit.py` | `construction_project_id`, `boq_item_id` (related), `mr_line_id` |
| `account.analytic.line` | `account_analytic_line_inherit.py` | `construction_project_id`, `boq_item_id`, `cost_type` |
| `crm.lead` | `crm_lead_inherit.py` | `construction_project_id`, `is_converted_to_construction` |

### Res.config.settings — `res_config_settings.py`
Settings stored as `ir.config_parameter` keys (accessible via Settings > Construction):

| Config Key | Field | Type | Default |
|---|---|---|---|
| `construction.auto_create_analytic` | `construction_auto_create_analytic` | Boolean | True |
| `construction.auto_create_project` | `construction_auto_create_project` | Boolean | True |
| `construction.auto_create_tasks` | `construction_auto_create_tasks` | Boolean | False |
| `construction.default_retention` | `construction_default_retention` | Float | 5.0 |
| `construction.default_tax` | `construction_default_tax` | Float | 0.0 |
| `construction.default_analytic_plan_id` | `construction_default_analytic_plan_id` | M2O | — |
| `construction.income_account_id` | `construction_income_account_id` | M2O | — |
| `construction.expense_account_id` | `construction_expense_account_id` | M2O | — |

### Auto-creation Logic
- **On project create** (if `construction.auto_create_analytic`): auto-creates `account.analytic.account` via `action_create_analytic_account()`
- **On stage → execution/awarded** (if `construction.auto_create_project`): auto-creates `project.project` via `action_create_project_project()`
- **On BOQ approve** (if `construction.auto_create_tasks`): auto-creates `project.task` from approved BOQ items via `action_create_tasks_from_boq()`
- All auto-creation wrapped in `SAVEPOINT/ROLLBACK` to prevent failures from blocking the main operation
- `action_create_analytic_account()` uses the configured `construction.default_analytic_plan_id`, falling back to first available plan for the company

### Demo data (`data/demo_data.xml`)
Creates resources (cement, rebar, labor, excavator), a demo project, BOQ items, and rate analysis. Only loads with `--demo` flag.

## Gotchas
- `progress_percent` on `construction.project` is `store=True` (dashboard SQL view needs it in DB)
- IPC `create()` auto-computes `ipc_number` (sequential per project) and `prev_work_done` (from last paid IPC)
- `construction.material.request` has `action_create_purchase_order()` that creates `purchase.order`
- `construction.material.issue` has `action_create_stock_picking()` that creates `stock.picking`
- Tests use `TransactionCase` in `tests/test_construction_models.py`
