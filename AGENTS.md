# AGENTS.md — Utility ERP

## Project

Odoo 16.0 ERP for electricity distribution companies. 6 addon modules under `utility_erp/`.

## Module dependency order

1. `date_range` — Odoo standard date_range module (required by utility_core for billing periods)
2. `utility_core` — master data: customers, accounts, meters, tariffs, 8-level NUTS hierarchy (region→area→zone→office→substation→feeder→transformer→route), subscriber categories, contract templates, formulas, settings, migration staging models, dashboard
3. `utility_inventory` — inventory bridge: adds `product_id` and `lot_id` to meters (depends on stock & product)
4. `utility_operations` — field ops: service orders, inspections, tamper cases, meter replacement, reading/financial settlements
5. `utility_billing` — postpaid billing: meter readings, billing cycles, sale orders, penalties, recurring invoices, reading batches, payment gateway REST API (`/api/v1/utility/billing/*`), Odoo portal templates, AMI reading callback endpoint
6. `utility_prepaid` — prepaid vending: STS tokens, sales, payments, cashier shifts, POS integration

Install in that order. `utility_core` must always be first. `utility_migration` does not exist as a standalone module — migration staging models live inside `utility_core`. **`utility_portal` was removed** — its contents were merged into `utility_billing` (payment gateway model + REST API controllers + portal templates).

## Test commands

Tests exist in `utility_core/tests/` and `utility_billing/tests/`. Run with standard Odoo test runner:
```bash
odoo-bin -d <db> -i <module> --test-enable --stop-after-init
```

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
- **Communication & Notifications** — Do NOT use Odoo's standard email functionality, as there is no mail server configured. All customer notifications must be routed through SMS or a local WhatsApp provider. The `mail` module IS used internally for `mail.thread` chatter and `mail.activity.mixin` tracking on backend models.
- **Subscriber Terminology & Rules**:
  - `utility.subscriber.category` = **فئات المشتركين الرئيسية** (Subscriber Categories)
  - `utility.subscriber` = **انواع المشتركين** (Subscriber Types)
  - Both fields are mandatory on contract templates (`utility.contract.template`) and subscriber accounts (`utility.customer`). The selected type must belong to the selected category, and both must be compatible with the selected contract template.
  - In `utility.customer` and `utility.customer.wizard`, the contract template field (`contract_template_id`) must only display and accept templates that are suitable for both the selected subscriber classification (categories & types) and the geographic location (regions & areas).

## Organized 2-Column Layout for Settings & Forms

All `res.config.settings` views and complex forms MUST use an organized 2-column card layout:

```xml
<div class="row">
    <div class="col-12 col-lg-6">
        <div class="card o_settings_card">
            <div class="card-header">
                <div class="d-flex align-items-center">
                    <i class="fa fa-[icon] fa-2x text-[color] me-3"/>
                    <div>
                        <h4 class="mb-0">عنوان القسم</h4>
                        <small class="text-muted">وصف مختصر</small>
                    </div>
                </div>
            </div>
            <div class="card-body">
                <!-- settings fields -->
            </div>
        </div>
    </div>
    <div class="col-12 col-lg-6">
        <!-- second card -->
    </div>
</div>
```

Rules:
- Group related settings into cards with descriptive headers and Font Awesome icons
- Use 2-column layout (`col-12 col-lg-6`) for side-by-side cards on desktop
- Use `o_light_label` class for form labels
- Add `text-muted` helper text below fields when needed
- Use `attrs="{'invisible': [...]}"` to conditionally hide dependent fields
- Each card should have a clear icon: `fa-shopping-cart`, `fa-cloud`, `fa-key`, `fa-calculator`, `fa-money`, `fa-bell`, etc.
- Icon colors: `text-primary`, `text-success`, `text-warning`, `text-info`, `text-danger`, `text-purple`
- Boolean fields: `<field/>` then `<label for="..." class="ms-2"/>`
- Selection/Many2one fields: `<label for="..." class="o_light_label"/>` then `<field/>`



## Important files

- `EXECUTION_PLAN.md` — Arabic implementation plan (reading workflow, contracts, discounts)
- `GAP_ANALYSIS_PLAN.md` — gap analysis vs legacy PEC system
- `utility_core/security/utility_security.xml` — all 9 security groups
- `utility_core/views/utility_settings_views.xml` — settings form view
- `utility_billing/models/utility_sale_order.py` — main billing model (sale.order inherit, `_calculate_amounts()` for dynamic line computation)
- `utility_billing/data/utility_cron_extras.xml` — cron jobs including `cron_update_overdue_orders`, `cron_send_due_reminders`
- `utility_billing/views/utility_sale_order_views.xml` — sale.order tree/form/search views with utility fields

## Resolved & Pending Gaps (from GAP_ANALYSIS_PLAN.md)

| Gap | Priority | Status |
|-----|----------|--------|
| Recurring contracts automation | 🔴 Critical | ✅ Completed (`utility.recurring.invoice`) |
| Settings & configuration | 🟡 Medium | ✅ Completed (`res.config.settings` inherits) |
| Analytic account integration | 🟡 Medium | ✅ Completed (Integrated in billing) |
| Meter replacement module | 🟡 Medium | ✅ Completed (`utility.meter.replacement`) |
| Reading/financial settlements | 🟢 Nice-to-have | ✅ Completed (`utility.reading.settlement`) |
| Advanced reports (transformer balance, customer statement) | 🟢 Nice-to-have | ✅ Completed (Custom Wizards) |
| Barcode OCR service | 🟢 Nice-to-have | 🟡 Pending |

## Development commands

Standard Odoo 16.0 addon path. No custom Makefile, pre-commit, linter, or typecheck configuration exists. No CI workflows detected.

## Dependencies & Requirements

All third-party Python packages required by any module must be tracked in the global `requirements.txt` located at `c:\odoo\odoo\odoo\utility_erp\requirements.txt`. Current dependencies include:
- `xlsxwriter` (for Excel generation)
- `openpyxl` (for reading uploaded Excel templates in migration)
- `requests` (for external API integration)
- `odoo-test-helper` (for unit tests, primarily in date_range module)


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
1. **Module Count**: The project has 7 addon modules (adding `utility_inventory` for storage and tracking, and `utility_migration` for staging and mapping legacy data).
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
8. **Migration Templates & Deduplicated Staging Models (نماذج الميجريشن النظيفة والخالية من التكرار)**:
   - **Feeder Migration (`utility.migration.feeder`)**: Deduplicated to 10 clean columns (`legacy_region`, `legacy_area`, `is_active`, `feeder_code`, `feeder_name`, `meter_number`, `meter_multiplier`, `current_reading`, `is_calculation_cell`, `description`).
   - **Transformer Migration (`utility.migration.transformer`)**: Deduplicated to 14 clean columns (`legacy_region`, `legacy_area`, `is_active`, `transformer_code`, `transformer_name`, `meter_number`, `meter_multiplier`, `current_reading`, `total_consumption`, `image_status`, `cell_meter_number`, `cell_meter_multiplier`, `reference`, `description`). `reference` retained exclusively for Transformers.
   - **Flexible Boolean Parser**: `parse_bool()` supports all boolean formats (`True`/`False`, `true`/`false`, `1`/`0`, `yes`/`no`, `y`/`n`, `نعم`/`لا`, `صح`/`خطأ`).
   - **Updated Excel Templates**: Generated via `openpyxl` with Cairo typography, pastel banners, and `تعليمات الاستيراد` sheet.
9. **Dedicated Postpaid Dashboard (لوحة قيادة الفوترة والتحصيل الآجل)**:
   - **Strict Postpaid Scope**: Removed all prepaid vending (`pos.order`, STS tokens) from `dashboard_api.py` and `utility_dashboard.js`. Dedicated 100% to postpaid billing (`sale.order` & `account.payment`).
   - **Postpaid KPIs**: `today_postpaid` (inbound postpaid payments), `today_billed` (postpaid invoices issued today), `total_debt` (open residual debt), and `overdue_debt` (overdue debt).
   - **SearchModel & Event Protection**: Prevented `TypeError: Cannot read properties of undefined (reading 'toString') at SearchModel._getDomain` by type-checking `regionId` parameters and using explicit arrow functions `() => this.openPostpaidOrders()` on click events. Fixed `sale.order` field name from `account_id` to `customer_id`.
   - **Manual Fetch & Empty State**: Removed auto-load on start (`onWillStart`). Dashboard displays a clean prompt requiring the user to select a region and click "تحديث" to fetch data.
   - **RTL & FontAwesome Protection**: Enforced `direction: rtl !important; text-align: right !important;` with explicit `text-start` for Bootstrap 5 RTL alignment. Excluded FontAwesome icons from Cairo font override (`font-family: FontAwesome !important;`).
   - **Smooth Scrollbar**: Applied `position: absolute; overflow-y: auto !important; scroll-behavior: smooth;` with custom sleek webkit scrollbar.

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

# Odoo 16 UI/UX Design Instructions for Any Module

You are working on an **Odoo 16 Community/Enterprise** project.
For every module, feature, model, menu, wizard, dashboard, or report you build, you must produce a **high-quality Odoo-native UI/UX** that is practical, clean, fast, and consistent with Odoo 16 design patterns.

These instructions apply to **any Odoo 16 application**, regardless of business domain.

---

## 1. Core UI/UX Principles

Always design for:

* fast daily operations
* minimal clicks
* clear navigation
* clean forms
* readable list views
* useful search filters
* meaningful group-by options
* smart buttons for drill-downs
* clear workflow states
* strong auditability
* low user training cost
* Odoo-native look and behavior

Do not create cluttered screens.
Do not expose technical fields unless they are truly useful for the user.

---

## 2. Menu Design

Every module must have a clear menu hierarchy.

Use this structure when suitable:

```text
App / Main Menu
├── Operations
├── Master Data
├── Reports
└── Configuration
```

Guidelines:

* Put daily-use screens under **Operations**.
* Put setup records under **Master Data** or **Configuration**.
* Put analysis, pivots, dashboards, and summaries under **Reports**.
* Do not bury common actions too deep.
* Use short, business-friendly menu names.
* Avoid duplicate menus with similar meanings.

---

## 3. List / Tree View Design

Every important model must have a useful tree view.

Include:

* reference/name
* date
* main partner/entity
* important amount/status fields
* responsible user/team if applicable
* company if multi-company matters
* state
* linked document if useful

Rules:

* Put the most important fields first.
* Use `widget="monetary"` for amounts.
* Use `widget="badge"` where helpful.
* Use decorations for states:

  * draft / cancelled → muted
  * confirmed / posted / done → success
  * waiting / pending / partial → warning
  * error / rejected / overdue → danger
* Avoid too many columns.
* Default sort should match daily work, usually newest first.

---

## 4. Form View Design

Every form should be easy to understand in the first 5 seconds.

Use this structure:

```xml
<header>
    <!-- action buttons -->
    <field name="state" widget="statusbar"/>
</header>

<sheet>
    <div class="oe_button_box" name="button_box">
        <!-- smart buttons -->
    </div>

    <group>
        <group>
            <!-- primary business fields -->
        </group>
        <group>
            <!-- dates, responsible user, company, references -->
        </group>
    </group>

    <notebook>
        <!-- details, lines, accounting, notes, technical info -->
    </notebook>
</sheet>

<div class="oe_chatter">
    <field name="message_follower_ids"/>
    <field name="activity_ids"/>
    <field name="message_ids"/>
</div>
```

Rules:

* Put essential business fields in the first visible area.
* Put secondary details in notebook tabs.
* Put technical/accounting/debug fields in a separate tab.
* Use readonly rules after confirmation/posting.
* Use domains and context defaults to reduce user mistakes.
* Use onchange/helper fields where they improve clarity.
* Use `mail.thread` and chatter for important business documents.

---

## 5. Header Buttons & States

Every workflow document should have a clear state machine.

Common states:

```text
Draft → Confirmed → Posted/Done → Cancelled
```

or:

```text
Draft → Submitted → Approved → Done → Cancelled
```

Button rules:

* Show only valid actions for the current state.
* Use clear verbs: Confirm, Approve, Post, Validate, Cancel, Reset to Draft.
* Avoid too many buttons.
* Dangerous actions should be restricted and clear.
* Posted/done documents should mostly be readonly.

---

## 6. Search View Design

Every operational model must have a strong search view.

Include search by:

* reference/name
* partner/customer/vendor/employee
* date
* state
* responsible user
* company
* currency if relevant
* related document if relevant

Add filters such as:

```text
Today
This Week
This Month
Draft
Confirmed
Posted
Done
Cancelled
My Records
Overdue
Needs Attention
```

Add group-by options such as:

```text
State
Date
Partner
Responsible User
Company
Currency
Category
```

Search views must be designed for real users, not generated mechanically.

---

## 7. Smart Buttons

Use smart buttons to make drill-downs easy.

Good smart buttons include:

* Journal Entries
* Invoices
* Payments
* Orders
* Pickings
* Attachments
* Tasks
* Related Records
* Ledger / Statement
* History
* Reports

Rules:

* Only add smart buttons that users actually need.
* Smart buttons should show counts where useful.
* Place them inside `oe_button_box`.
* Use clear icons and labels.

---

## 8. Notebook Tabs

Use notebook tabs to organize information.

Common tabs:

```text
Lines
Details
Accounting
Logistics
Approvals
Attachments
Notes
Technical
```

Rules:

* Do not use tabs for 2 or 3 fields only.
* Keep the first tab focused on the main business content.
* Put notes and chatter lower in the form.
* Put technical fields in a Technical tab and restrict if needed.

---

## 9. Wizards

Use wizards for guided actions.

Good wizard use cases:

* confirmation actions
* bulk updates
* posting/validation with options
* cancellations with reason
* approvals
* settlement/allocation
* report generation

Wizard design rules:

* Keep wizards short.
* Show only fields needed for the decision.
* Add clear helper text.
* Validate before applying changes.
* Return the user to a useful view after completion.

---

## 10. Dashboards, Kanban, Pivot, Graph

Use analytical views where they add value.

Recommended:

* Kanban for operational stages or visual cards.
* Pivot for financial/quantitative analysis.
* Graph for trends and summaries.
* Dashboard for KPIs and “needs attention” records.

Dashboard cards may include:

```text
Today
This Month
Pending
Approved
Posted
Overdue
Outstanding
Total Amount
```

Do not create dashboards that duplicate list views without adding insight.

---

## 11. Reporting UX

Reports must be easy to find.

Place reports under:

```text
Reports
```

Good reports include:

* daily summary
* monthly summary
* outstanding balances
* activity by user/team
* financial summary
* status report
* exceptions/errors report

Each report should support filters by date, state, partner/entity, company, and currency where relevant.

---

## 12. Configuration UX

Configuration screens must be clean and grouped.

Typical sections:

```text
General Settings
Accounting
Sequences
Journals
Approvals
Notifications
Security
Integrations
```

Rules:

* Use clear labels.
* Add help text for risky settings.
* Do not expose technical parameters without explanation.
* Keep configuration separate from daily operations.
* Reuse existing settings fields when they already exist.

---

## 13. Field Naming & Labels

Use business-friendly labels.

Examples:

* `partner_id` → Customer / Vendor / Contact depending on context
* `user_id` → Responsible
* `move_id` → Journal Entry
* `picking_id` → Delivery / Transfer
* `amount_total` → Total
* `state` → Status

Labels must match the business process, not just the technical model.

---

## 14. Readonly, Required, Domains

Apply field behavior carefully.

Rules:

* Required fields must be truly required.
* Fields should become readonly after confirmation/posting.
* Use domains to filter valid records.
* Use context defaults to reduce manual entry.
* Prevent editing posted accounting-sensitive records unless using controlled reversal/reset flows.

---

## 15. Multi-Company & Multi-Currency UX

If the module supports multi-company or multi-currency:

* Show company only where it matters.
* Default company from the environment.
* Use currency fields consistently.
* Put currency next to amount fields.
* Use `widget="monetary"` for all money values.
* Avoid mixing amounts without clear currency context.

---

## 16. Error Prevention

The UI must prevent mistakes before they happen.

Use:

* domains
* warnings
* onchange validations
* clear button visibility
* readonly states
* confirmation wizards
* business constraints

Error messages must be human-readable and explain how to fix the issue.

---

## 17. Auditability

Important business documents should include:

* creator
* responsible user
* confirmation user/date
* posting user/date
* cancellation user/date/reason
* linked accounting/logistics documents
* chatter tracking
* activities if follow-up is needed

---

## 18. Odoo XML Quality Rules

When writing XML:

* use clean `record` IDs
* use clear action names
* define tree, form, search views for core models
* define menus in logical order
* use `attrs` / modifiers correctly
* use `context` and `domain` intentionally
* avoid duplicated XML
* avoid huge unreadable forms
* keep view inheritance minimal and targeted

---

## 19. Access & Security UX

Security should support the user experience.

Typical groups:

```text
User
Manager
Accountant
Administrator
```

Rules:

* Users should see only actions they can perform.
* Managers can approve/cancel.
* Accountants can post or review accounting entries.
* Technical settings should be restricted.
* Record rules must not break operational usability.

---

## 20. Final Quality Standard

For every Odoo 16 feature, deliver UI/UX that feels:

* native to Odoo
* clean
* fast
* business-friendly
* auditable
* scalable
* easy to train
* safe for accounting and operations

Never produce only backend models without considering:

* menus
* actions
* views
* filters
* group-bys
* smart buttons
* states
* reports
* configuration
* user workflow.

# Odoo 16 ORM & Performance Guidelines

## 1. Avoid N+1 Queries
* NEVER place `search()`, `search_count()`, or `browse()` inside a `for` loop. 
* Fetch all needed records in a single query before the loop, or use `.mapped()` and `.filtered()`.

## 2. Bulk Operations
* Always use bulk `create()` and `write()` operations instead of iterating over records to write one by one.
* Example: `self.env['model'].create([{'val': 1}, {'val': 2}])`

## 3. Efficient Data Processing
* Use `read_group()` when aggregating data (SUM, COUNT, AVG) instead of searching all records and looping through them in Python.
* Use `search_read()` instead of `search()` followed by a loop if you only need dictionary data for an API response.

## 4. Compute Fields Optimization
* Heavy compute fields MUST use `compute_sudo=True` carefully and rely on indexed fields.
* Always define proper `inverse` methods if the field should be editable.
* Use `@api.depends_context('company')` if the compute field result depends on the active company.

## 5. SQL Queries
* Avoid raw SQL (`self.env.cr.execute`) unless absolutely necessary for complex joins or extreme performance bottlenecks.
* If raw SQL is used, ALWAYS use parameterized queries to prevent SQL Injection (e.g., `execute("SELECT id FROM table WHERE name = %s", [name])`).
* Always call `self.env.flush_all()` before executing raw SQL to ensure ORM changes are committed to the DB first.

# Odoo 16 Security & Multi-Company Guidelines

## 1. Multi-Company Compliance
* EVERY new model containing business data MUST have a `company_id` field.
* `company_id` should default to `lambda self: self.env.company`.
* Always add the standard multi-company record rule to new models:
  `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`

## 2. Use of sudo()
* Use `.sudo()` ONLY when crossing access rights boundaries intentionally (e.g., a portal user submitting a form that creates a backend record).
* NEVER use `.sudo()` just to bypass poor access right design. Explain why `.sudo()` is used in a comment.

## 3. Exceptions and Error Handling
* NEVER use Python's generic `Exception` or `print()` statements for business logic errors.
* Always import and raise `from odoo.exceptions import UserError, ValidationError, AccessError`.
* Error messages must be clear, human-readable, and ideally translated.

# Odoo 16 Clean Code & Internationalization (i18n)

## 1. Translation Ready
* Hardcoded strings in Python that appear to users MUST be wrapped in the translation function `_()`. 
* Example: `raise UserError(_("The requested quantity is not available."))`

## 2. Logging vs Printing
* NEVER leave `print()` statements in production code. 
* Use Python's `logging` module (`_logger = logging.getLogger(__name__)`) for debugging and system warnings.

## 3. Code Documentation
* Every non-standard or complex method must have a Python docstring briefly explaining the expected inputs, outputs, and side effects.
