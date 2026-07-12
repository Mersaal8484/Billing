# Utility ERP — Software Requirements Specification (SRS)

> **Document Version:** 1.0  
> **Date:** July 2026  
> **Classification:** Internal — Software Engineering  
> **Platform:** Odoo 16.0 Community/Enterprise  
> **ORM:** Odoo ORM (Python 3.10+)  
> **Database:** PostgreSQL 14+

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Model Specification](#2-data-model-specification)
3. [API Specification](#3-api-specification)
4. [Security Specification](#4-security-specification)
5. [Automation & Cron Specification](#5-automation--cron-specification)
6. [Formula Engine Specification](#6-formula-engine-specification)
7. [Notification System Specification](#7-notification-system-specification)
8. [Portal Specification](#8-portal-specification)
9. [Error Handling Specification](#9-error-handling-specification)
10. [Testing Requirements](#10-testing-requirements)

---

## 1. System Overview

### 1.1 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Application Framework | Odoo | 16.0 |
| Language | Python | 3.10+ |
| ORM | Odoo ORM | — |
| Database | PostgreSQL | 14+ |
| Frontend | OWL 2.0 (Odoo Web Client) | — |
| Template Engine | QWeb (XML) | — |
| JavaScript | Odoo JS + OWL | — |
| API Protocol | JSON REST (over HTTP) | — |
| External HTTP | `requests` library | — |
| Token Standard | STS (Standard Transfer Specification) | — |

### 1.2 Module Inventory

| Module | Depends On | Key Models | File Count |
|--------|-----------|------------|-----------|
| `date_range` | (OCA) | `date.range.type`, `date.range` | — |
| `utility_core` | `date_range`, `sale`, `account`, `mail`, `product`, `pos`, `base_setup` | 32+ models | ~40 |
| `utility_inventory` | `utility_core`, `stock` | 5 models | ~10 |
| `utility_prepaid` | `utility_core`, `pos` | 6 models | ~10 |
| `utility_operations` | `utility_core` | 8 models | ~12 |
| `utility_billing` | `utility_core`, `utility_prepaid`, `sale`, `account` | 16 models | ~20 |
| `utility_portal` | `utility_billing`, `utility_operations` | 1 model + 7 endpoints | ~8 |
| `utility_migration` | `utility_core`, `openpyxl` | 3 models + 1 wizard | ~5 |

---

## 2. Data Model Specification

### 2.1 utility_core — Master Data Models

#### 2.1.1 `utility.region` — Geographic Hierarchy (New Model)

**Purpose:** Commercial/Sales geographic hierarchy using a self-referential `parent_id` pattern. (Network/Distribution elements are handled by `utility.substation`, `utility.feeder`, etc.)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Region name |
| `code` | Char | Yes | Short code (unique per level) |
| `type` | Selection | Yes | `region`, `area`, `zone` |
| `parent_id` | Many2one → `utility.region` | No | Parent node (self-referential) |
| `child_ids` | One2many → `utility.region` | No | Child nodes |
| `company_id` | Many2one → `res.company` | No | Multi-company (False = global) |
| `recurring_rule_type` | Selection | No | `monthly`, `quarterly`, `annually` — billing frequency |
| `active` | Boolean | Yes | Active/deactive toggle |

**Constraints:**
- `code` unique per `type`
- `parent_id` must be one level above (region→area, area→zone, etc.)

---

#### 2.1.2 `utility.office` — Office (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Office name |
| `region_id` | Many2one → `utility.region` | Yes | Parent region |
| `area_id` | Many2one → `utility.region` | Yes | Parent area |
| `manager_name` | Char | No | Manager name |
| `phone` | Char | Yes | 9-digit phone number (regex validated) |
| `address` | Text | No | Physical address |
| `company_id` | Many2one → `res.company` | No | Multi-company |

---

#### 2.1.3 `utility.substation` — Substation (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Substation name |
| `code` | Char | Yes | Unique code |
| `office_id` | Many2one → `utility.office` | Yes | Parent office |
| `feeder_ids` | One2many → `utility.feeder` | No | Connected feeders |
| `capacity_kva` | Float | No | Capacity in kVA |
| `company_id` | Many2one → `res.company` | No | Multi-company |

---

#### 2.1.4 `utility.feeder` — Feeder (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Feeder name |
| `code` | Char | Yes | Unique code |
| `substation_id` | Many2one → `utility.substation` | Yes | Parent substation |
| `transformer_ids` | One2many → `utility.transformer` | No | Connected transformers |
| `feeder_type` | Selection | Yes | `primary`, `secondary` |
| `voltage_level` | Float | No | Voltage in kV |
| `company_id` | Many2one → `res.company` | No | Multi-company |

---

#### 2.1.5 `utility.transformer` — Transformer/Cell (New Model)

**Purpose:** Both cells (`is_cell=True`) and standalone transformers. Cells contain child transformers via `parent_id` with `_parent_store`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Transformer/cell name |
| `code` | Char | Yes | Unique code |
| `is_cell` | Boolean | Yes | True = cell, False = transformer |
| `parent_id` | Many2one → `utility.transformer` | No | Parent cell (for transformers) |
| `parent_path` | Char | No | `_parent_store` path |
| `child_ids` | One2many → `utility.transformer` | No | Child transformers (if cell) |
| `feeder_id` | Many2one → `utility.feeder` | No | Connected feeder |
| `coupling_meter_id` | Many2one → `utility.meter` | No | Cell coupling meter |
| `cell_account_ids` | Many2many → `utility.customer` | No | Cell-level accounts |
| `distribution` | Float | No | Distribution percentage |
| `loss` | Float | No | Loss percentage |
| `capacity_kva` | Float | No | Rated capacity |
| `company_id` | Many2one → `res.company` | No | Multi-company |

---

#### 2.1.6 `utility.route` — Reading Route (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Route name |
| `office_id` | Many2one → `utility.office` | Yes | Parent office |
| `transformer_ids` | Many2many → `utility.transformer` | No | Transformers on route |
| `company_id` | Many2one → `res.company` | No | Multi-company |

---

#### 2.1.7 `utility.subscriber.category` — Subscriber Categories (New Model)

**Purpose:** Main subscriber classification (فئات المشتركين الرئيسية).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Category name (e.g., Residential, Commercial) |
| `code` | Char | Yes | Unique code |
| `active` | Boolean | Yes | Active toggle |
| `company_id` | Many2one → `res.company` | No | Multi-company |

---

#### 2.1.8 `utility.subscriber` — Subscriber Types (New Model)

**Purpose:** Subscriber types within a category (انواع المشتركين).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Type name (e.g., Villa, Apartment) |
| `code` | Char | Yes | Unique code |
| `category_id` | Many2one → `utility.subscriber.category` | Yes | Parent category |
| `active` | Boolean | Yes | Active toggle |
| `company_id` | Many2one → `res.company` | No | Multi-company |

---

#### 2.1.9 `utility.customer` — Customer Account (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Computed from partner |
| `customer_number` | Char | Yes | Auto-generated unique number |
| `partner_id` | Many2one → `res.partner` | Yes | Linked partner (unique) |
| `meter_id` | Many2one → `utility.meter` | No | Current meter |
| `category_id` | Many2one → `utility.subscriber.category` | Yes | Subscriber category |
| `subscriber_id` | Many2one → `utility.subscriber` | Yes | Subscriber type |
| `contract_template_id` | Many2one → `utility.contract.template` | Yes | Active contract template |
| `region_id` | Many2one → `utility.region` | Yes | Geographic region |
| `area_id` | Many2one → `utility.region` | Yes | Geographic area |
| `cell_id` | Many2one → `utility.transformer` | Yes | Distribution cell/transformer |
| `connection_type_id` | Many2one → `utility.connection.type` | No | Connection type |
| `state` | Selection | Yes | `draft`, `active`, `suspended`, `closed` |
| `contract_state` | Selection | Yes | `draft`, `active`, `expired`, `terminated` |
| `credit_limit` | Monetary | No | Maximum allowed debt |
| `accounting_balance` | Monetary | No | Computed receivable balance from accounting documents |
| `currency_id` | Many2one → `res.currency` | Yes | Company currency |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Constraints:**
- `partner_id` unique across all customers
- `subscriber_id.category_id == category_id`
- `contract_template_id` compatible with category + subscriber + area

---

#### 2.1.10 `utility.meter` — Meter Device (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Display name |
| `meter_number` | Char | Yes | Unique meter number |
| `customer_id` | Many2one → `utility.customer` | No | Current customer |
| `transformer_id` | Many2one → `utility.transformer` | No | Connected transformer |
| `meter_type_id` | Many2one → `utility.meter.type` | Yes | Meter type |
| `meter_model_id` | Many2one → `utility.meter.model` | Yes | Meter model |
| `status_id` | Many2one → `utility.meter.status` | Yes | Current status |
| `installation_date` | Date | No | Installation date |
| `qr_code` | Binary | No | QR code image |
| `sts_serial` | Char | No | STS serial number |
| `sts_key` | Char | No | STS key |
| `readings_count` | Integer | No | Computed reading count |
| `log_ids` | One2many → `utility.meter.log` | No | Event log |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Extended by utility_inventory:** `product_id` (Many2one → `product.product`), `lot_id` (Many2one → `stock.lot`)

**Extended by utility_billing:** No additional fields.

---

#### 2.1.11 `utility.meter.log` — Meter Event Log (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Log entry title |
| `meter_id` | Many2one → `utility.meter` | Yes | Associated meter |
| `log_type` | Selection | Yes | `installation`, `removal`, `tamper`, `repair`, `inspection`, `replacement`, `other` |
| `description` | Text | No | Detailed description |
| `reading_value` | Float | No | Reading at time of event |
| `user_id` | Many2one → `res.users` | Yes | Who performed action |
| `date` | Datetime | Yes | Event timestamp |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.1.12 `utility.reading` — Unified Reading Model (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reading reference |
| `meter_id` | Many2one → `utility.meter` | Yes | Meter |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `reading_value` | Float | Yes | Current reading (kWh) |
| `previous_reading` | Float | No | Previous reading |
| `consumption` | Float | No | Computed: current - previous |
| `reading_category` | Selection | Yes | `customer`, `cell`, `feeder`, `transformer` |
| `reading_type` | Selection | Yes | `manual`, `ami`, `batch` |
| `date_range_id` | Many2one → `date.range` | Yes | Billing period |
| `reading_date` | Date | Yes | Reading date |
| `state` | Selection | Yes | `draft`, `under_review`, `approved`, `billed`, `queued`, `error` |
| `meter_image` | Binary | No | Photo of meter |
| `consumption_alert` | Boolean | No | Alert if consumption abnormal |
| `notes` | Text | No | Reader notes |
| `reviewer_id` | Many2one → `res.users` | No | Who reviewed |
| `review_date` | Datetime | No | Review timestamp |
| `batch_id` | Many2one → `utility.reading.batch` | No | Batch reference (from utility_billing) |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Index:** `index=True` on `state` field.

**Constraints:**
- `reading_value >= previous_reading` (monotonically increasing)
- Cannot edit financial fields if `state == 'billed'`

---

#### 2.1.13 `utility.formula` — Dynamic Calculation Formula (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Formula name |
| `code` | Text | Yes | Python expression (executed via `safe_eval()`) |
| `description` | Text | No | Formula description |
| `company_id` | Many2one → `res.company` | No | Multi-company |

**Sandbox Variables:** `consumption`, `previous_reading`, `current_reading`, `tariff`, `account`, `category`, `line`, `result`, `name`

**Safe Globals:** Only `abs`, `min`, `max`, `round`, `int`, `float`, `len`, `sum`, `True`, `False`, `None`, `range`, `list`, `dict`, `set`, `tuple`, `isinstance`

---

#### 2.1.14 `utility.contract.template` — Contract Template (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Template name |
| `code` | Char | Yes | Unique code |
| `pricing_mode` | Selection | Yes | `fixed`, `block`, `tier`, `formula` |
| `price_per_kwh` | Float | No | Price per kWh (fixed mode) |
| `service_charge` | Float | No | Monthly service charge |
| `local_fee_mu_allim` | Float | No | العامل fee |
| `local_fee_cleaning` | Float | No | النظافة fee |
| `local_fee_municipality` | Float | No | البلدية fee |
| `minimum_charge` | Float | No | Minimum bill amount |
| `maximum_charge` | Float | No | Maximum bill amount cap |
| `recurring_rule_type` | Selection | Yes | `monthly`, `quarterly`, `annually` |
| `category_ids` | Many2many → `utility.subscriber.category` | Yes | Compatible categories |
| `subscriber_ids` | Many2many → `utility.subscriber` | Yes | Compatible subscriber types |
| `region_ids` | Many2many → `utility.region` | No | Compatible geographic areas |
| `line_ids` | One2many → `utility.contract.template.line` | No | Billing lines |
| `block_ids` | One2many → `utility.contract.template.block` | No | Block pricing tiers |
| `formula_id` | Many2one → `utility.formula` | No | Custom formula |
| `active` | Boolean | Yes | Active toggle |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.1.15 `utility.contract.template.line` — Contract Template Line (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template_id` | Many2one → `utility.contract.template` | Yes | Parent template |
| `name` | Char | Yes | Line description |
| `meter_line_type` | Selection | Yes | `consumption`, `service_charge`, `fixed_fee`, `mu_allim`, `cleaning`, `municipality`, `discount`, `penalty`, `other` |
| `qty_formula_id` | Many2one → `utility.formula` | No | Quantity formula |
| `specific_price` | Float | No | Override price |
| `is_subsidized` | Boolean | No | Subsidized line flag |
| `sort_order` | Integer | No | Display order |

---

#### 2.1.16 `utility.contract.template.block` — Block Pricing Tier (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template_id` | Many2one → `utility.contract.template` | Yes | Parent template |
| `from_kwh` | Float | Yes | Lower bound (kWh) |
| `to_kwh` | Float | Yes | Upper bound (kWh) |
| `price_per_kwh` | Float | Yes | Price for this block |

---

#### 2.1.17 `utility.connection` / `utility.connection.type` — Connection (New Models)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Connection description |
| `customer_id` | Many2one → `utility.customer` | Yes | Customer |
| `type_id` | Many2one → `utility.connection.type` | Yes | Connection type |
| `capacity_ampere` | Float | No | Rated capacity |
| `date` | Date | Yes | Connection date |

---

#### 2.1.18 `utility.integration.provider` — External Provider (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Provider name |
| `provider_type` | Selection | Yes | `sms`, `ami`, `payment_gateway` |
| `url` | Char | Yes | API endpoint URL |
| `api_key` | Char | No | API authentication key |
| `username` | Char | No | API username |
| `password` | Char | No | API password |
| `active` | Boolean | Yes | Active toggle |

**Method:** `call_json(endpoint, payload, method='POST')` → dict

---

#### 2.1.19 `utility.notification.log` — Notification Log (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Notification reference |
| `partner_id` | Many2one → `res.partner` | Yes | Recipient |
| `channel` | Selection | Yes | `sms`, `portal`, `internal` |
| `subject` | Char | Yes | Message subject |
| `body` | Text | Yes | Message body |
| `state` | Selection | Yes | `draft`, `sent`, `failed` |
| `sent_date` | Datetime | No | Send timestamp |
| `error_message` | Text | No | Error if failed |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Cron:** `cron_dispatch_sms_notifications()` runs every 10 minutes, processes `draft` notifications via `integration.provider`.

---

#### 2.1.20 `utility.customer.wizard` — Customer Creation Wizard (Transient)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `partner_id` | Many2one → `res.partner` | Yes | Partner |
| `category_id` | Many2one → `utility.subscriber.category` | Yes | Category |
| `subscriber_id` | Many2one → `utility.subscriber` | Yes | Type |
| `contract_template_id` | Many2one → `utility.contract.template` | Yes | Contract |
| `area_id` | Many2one → `utility.region` | Yes | Area |
| `meter_id` | Many2one → `utility.meter` | Yes | Meter |

**Action:** Creates `utility.customer` with all linked records.

---

#### 2.1.21 Inherited Models

**`res.partner` (Inherited)**

| Added Field | Type | Description |
|-------------|------|-------------|
| `region_id` | Many2one → `utility.region` | Geographic region |
| `area_id` | Many2one → `utility.region` | Geographic area |
| `previous_hotline_balance` | Float | Previous balance display |

**`res.company` (Inherited)**

| Added Field | Type | Description |
|-------------|------|-------------|
| `consumption_account_id` | Many2one → `account.account` | Consumption revenue account |
| `service_charge_account_id` | Many2one → `account.account` | Service charge account |
| `penalty_account_id` | Many2one → `account.account` | Penalty revenue account |
| `fine_account_id` | Many2one → `account.account` | Fine/penalty invoice account |
| `consumption_product_id` | Many2one → `product.product` | Consumption product |
| `service_charge_product_id` | Many2one → `product.product` | Service charge product |
| `penalty_product_id` | Many2one → `product.product` | Penalty product |

**`res.users` (Inherited)**

| Added Field | Type | Description |
|-------------|------|-------------|
| `collection_journal_id` | Many2one → `account.journal` | Collection journal |
| `prevent_installment` | Boolean | Block installment access |

---

### 2.2 utility_inventory — Inventory Models

*(Note: Custom inventory models like `utility.inventory.movement` and `utility.inventory.location` have been deprecated and removed in Phase 6).*

The `utility_inventory` module now acts strictly as a bridge between Utility core models and standard Odoo inventory (`stock`).

#### 2.2.1 Core Inventory Integration
- **`product.product`**: Used to define meter models and types as trackable products.
- **`stock.lot`**: Used to track individual meter serial numbers.
- **`stock.location`**: Used to represent warehouses, branches, customer locations, and scrap.
- **`stock.picking` & `stock.move`**: Automatically generated by Service Orders and Meter Replacements to physically move meters between locations.

#### 2.2.2 `utility.meter` (Inventory Extension)
Adds fields linking to standard stock:
- `product_id`: Many2one → `product.product`
- `lot_id`: Many2one → `stock.lot`
- `stock_location_id`: Related field indicating the current stock location of the meter.

### 2.3 utility_prepaid — Prepaid Models

#### 2.3.1 `pos.order` (Inherited by utility_prepaid)

| Added Field | Type | Description |
|-------------|------|-------------|
| `account_id` | Many2one → `utility.customer` | Customer account |
| `meter_id` | Many2one → `utility.meter` | Customer meter |
| `token_id` | Many2one → `utility.token` | Generated token |
| `token_status` | Selection | Token status |
| `cashier_shift_id` | Many2one → `utility.cashier.shift` | Cashier shift |

**Key Methods:**
- `_generate_token()` — Creates STS token after payment (idempotent)
- `action_pos_order_paid()` — Override: triggers token generation after payment confirmation

---

#### 2.3.2 `utility.token` — STS Token (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Token reference |
| `token_number` | Char | Yes | 20-digit STS code |
| `pos_order_id` | Many2one → `pos.order` | Yes | Source POS order |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `amount` | Monetary | Yes | Token value |
| `units` | Float | No | kWh units loaded |
| `status` | Selection | Yes | `draft`, `active`, `used`, `expired`, `blocked` |
| `generation_date` | Datetime | Yes | When generated |
| `expiry_date` | Datetime | No | Expiration date |
| `sts_response` | Text | No | STS server response |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |
| `currency_id` | Many2one → `res.currency` | Yes | Currency |

---

#### 2.3.3 `utility.transaction` — Prepaid Token Audit Ledger (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Transaction reference |
| `pos_order_id` | Many2one → `pos.order` | No | Source POS order |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `type` | Selection | Yes | `token_purchase`, `reversal`, `adjustment` |
| `amount` | Monetary | Yes | Transaction amount |
| `date` | Datetime | Yes | Transaction date |
| `state` | Selection | Yes | `draft`, `posted`, `cancelled` |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.3.4 `utility.reversal` — Transaction Reversal (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reversal reference |
| `transaction_id` | Many2one → `utility.transaction` | Yes | Original transaction |
| `pos_order_id` | Many2one → `pos.order` | No | Source POS order |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `amount` | Monetary | Yes | Reversal amount |
| `reason` | Text | Yes | Reversal reason |
| `state` | Selection | Yes | `draft`, `approved`, `completed`, `rejected` |
| `approved_by` | Many2one → `res.users` | No | Approver |
| `approval_date` | Datetime | No | Approval timestamp |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.3.5 `utility.adjustment` — Prepaid Correction (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Adjustment reference |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `type` | Selection | Yes | `credit`, `debit`, `emergency`, `compensation`, `correction` |
| `amount` | Monetary | Yes | Adjustment amount |
| `reason` | Text | Yes | Adjustment reason |
| `state` | Selection | Yes | `draft`, `approved`, `posted` |
| `approved_by` | Many2one → `res.users` | No | Approver |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.3.6 `utility.cashier.shift` — Cashier Shift (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Shift reference |
| `user_id` | Many2one → `res.users` | Yes | Cashier |
| `state` | Selection | Yes | `open`, `closed` |
| `opening_balance` | Monetary | Yes | Starting cash |
| `closing_balance` | Monetary | No | Ending cash |
| `expected_balance` | Monetary | No | Computed expected |
| `pos_order_ids` | One2many → `pos.order` | No | POS orders in shift |
| `start_date` | Datetime | Yes | Shift start |
| `end_date` | Datetime | No | Shift end |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Constraint:** `@api.constrains('user_id', 'state')` — Only one open shift per user.

---

### 2.4 utility_operations — Operations Models

#### 2.4.1 `utility.service.order` — Service Order (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Order reference (auto-sequence) |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `meter_id` | Many2one → `utility.meter` | No | Related meter |
| `service_type` | Selection | Yes | 11 types (see Section 3.4) |
| `state` | Selection | Yes | `draft`, `assigned`, `in_progress`, `completed`, `approved`, `cancelled`, `on_hold`, `rejected`, `failed` |
| `priority` | Selection | Yes | `low`, `medium`, `high`, `urgent` |
| `assigned_team_id` | Many2one → `utility.team` | No | Assigned team |
| `assigned_user_id` | Many2one → `res.users` | No | Assigned technician |
| `request_date` | Datetime | Yes | When requested |
| `scheduled_date` | Datetime | No | Scheduled for |
| `completion_date` | Datetime | No | Completed at |
| `notes` | Text | No | Description/notes |
| `work_order_ids` | One2many → `utility.work.order` | No | Associated work orders |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Method:** `_check_state_transition(from_state, to_state)` — Validates allowed transitions.

**On Complete:** Creates `utility.meter.log` entries.

---

#### 2.4.2 `utility.installation` — Installation Order (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reference |
| `service_order_id` | Many2one → `utility.service.order` | Yes | Parent order |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `meter_id` | Many2one → `utility.meter` | Yes | Meter to install |
| `connection_type_id` | Many2one → `utility.connection.type` | No | Connection type |
| `installation_date` | Date | Yes | Installation date |
| `initial_reading` | Float | Yes | Initial meter reading |
| `state` | Selection | Yes | `draft`, `done`, `cancelled` |

---

#### 2.4.3 `utility.inspection` — Inspection (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reference |
| `service_order_id` | Many2one → `utility.service.order` | Yes | Parent order |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `meter_id` | Many2one → `utility.meter` | Yes | Meter inspected |
| `inspection_type` | Selection | Yes | 6 types: `routine`, `complaint`, `tamper`, `new_connection`, `disconnection`, `other` |
| `findings` | Text | Yes | Inspection findings |
| `action_required` | Boolean | No | Follow-up needed |
| `inspector_signature` | Binary | No | Digital signature |
| `inspection_date` | Date | Yes | Date of inspection |
| `state` | Selection | Yes | `draft`, `submitted`, `approved` |

---

#### 2.4.4 `utility.tamper.case` — Tamper Case (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Case reference |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `meter_id` | Many2one → `utility.meter` | Yes | Meter involved |
| `tamper_type` | Selection | Yes | 6 types: `bypass`, `meter_tamper`, `connection_tamper`, `seal_broken`, `wiring_fraud`, `other` |
| `severity` | Selection | Yes | `low`, `medium`, `high`, `critical` |
| `description` | Text | Yes | Case details |
| `evidence_ids` | One2many → `ir.attachment` | No | Evidence files |
| `estimated_loss` | Monetary | No | Estimated revenue loss |
| `state` | Selection | Yes | `reported`, `investigating`, `proven`, `dismissed`, `settled`, `legal` |
| `inspector_id` | Many2one → `res.users` | No | Investigating inspector |
| `report_date` | Date | Yes | Report date |
| `resolution_date` | Date | No | Resolution date |
| `resolution_notes` | Text | No | Resolution details |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.4.5 `utility.alarm` — Alarm (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Alarm reference |
| `account_id` | Many2one → `utility.customer` | No | Related customer |
| `meter_id` | Many2one → `utility.meter` | No | Related meter |
| `alarm_type` | Selection | Yes | 13 types (see Section 3.6) |
| `severity` | Selection | Yes | `info`, `warning`, `critical` |
| `description` | Text | Yes | Alarm details |
| `state` | Selection | Yes | `open`, `acknowledged`, `investigating`, `resolved`, `dismissed` |
| `service_order_id` | Many2one → `utility.service.order` | No | Auto-created service order |
| `tamper_case_id` | Many2one → `utility.tamper.case` | No | Auto-created tamper case |
| `alarm_date` | Datetime | Yes | When triggered |
| `resolution_date` | Datetime | No | When resolved |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.4.6 `utility.work.order` — Work Order (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reference |
| `service_order_id` | Many2one → `utility.service.order` | Yes | Parent service order |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `assigned_user_id` | Many2one → `res.users` | Yes | Technician |
| `state` | Selection | Yes | `draft`, `in_progress`, `completed`, `cancelled` |
| `check_in_gps` | Char | No | GPS coordinates on check-in |
| `check_out_gps` | Char | No | GPS coordinates on check-out |
| `check_in_time` | Datetime | No | Check-in timestamp |
| `check_out_time` | Datetime | No | Check-out timestamp |
| `parts_used` | Text | No | Parts/labor description |
| `labor_hours` | Float | No | Hours worked |
| `notes` | Text | No | Work notes |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.4.7 `utility.reading.settlement` — Reading Settlement (New Model)

**Purpose:** Correct readings after they have been billed, with full audit trail.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reference |
| `reading_id` | Many2one → `utility.reading` | Yes | Original reading |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `original_value` | Float | Yes | Original reading value |
| `corrected_value` | Float | Yes | Corrected reading value |
| `difference` | Float | No | Computed difference |
| `amount_adjustment` | Monetary | No | Financial impact |
| `reason` | Text | Yes | Correction reason |
| `state` | Selection | Yes | `draft`, `approved`, `posted` |
| `approved_by` | Many2one → `res.users` | No | Approver |
| `invoice_id` | Many2one → `account.move` | No | Created invoice or credit note for financial impact |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Mechanism:** Uses `_bypass_reading_protection` context flag to modify billed readings.

---

### 2.5 utility_billing — Billing Models

#### 2.5.1 `sale.order` (Inherited — Main Billing Document)

**File:** `utility_billing/models/utility_sale_order.py` (~1035 lines)

| Added Field | Type | Description |
|-------------|------|-------------|
| `account_id` | Many2one → `utility.customer` | Customer account |
| `meter_id` | Many2one → `utility.meter` | Meter |
| `reading_id` | Many2one → `utility.reading` | Source reading |
| `date_range_id` | Many2one → `date.range` | Billing period |
| `period_start` | Date | Period start (from date_range) |
| `period_end` | Date | Period end (from date_range) |
| `previous_reading` | Float | Previous reading value |
| `current_reading` | Float | Current reading value |
| `consumption` | Float | Consumption (kWh) |
| `tariff_id` | Many2one → `utility.contract.template` | Active tariff/contract |
| `amount_energy` | Monetary | Energy charge |
| `amount_service` | Monetary | Service charge |
| `amount_local_fee` | Monetary | Local fees total |
| `amount_discount` | Monetary | Discount amount |
| `amount_penalty` | Monetary | Penalty amount (computed from utility.penalty) |
| `amount_paid` | Monetary | Total paid |
| `balance_due` | Monetary | Outstanding balance |
| `is_overdue` | Boolean | Overdue flag |
| `previous_balance` | Monetary | Carried forward |
| `total_due_amount` | Monetary | Total including previous |
| `bill_state` | Selection | `draft`, `confirmed`, `sent`, `paid`, `overdue`, `cancelled` (stored computed) |
| `payment_state` | Selection | Invoice payment state |

**Index:** `bill_state` (stored computed, `index=True`), `balance_due` (`index=True`), `is_overdue` (`index=True`).

**Key Methods:**
- `_calculate_amounts()` — Dynamic bill line generation from contract template
- `action_confirm_bill()` — Transition draft → confirmed
- `action_send_bill()` — Transition confirmed → sent
- `action_create_disconnection_order()` — Creates service order for disconnection
- `action_create_reconnection_order()` — Creates service order for reconnection
- `cron_update_overdue_orders()` — Marks unpaid past-due bills as overdue
- `cron_send_due_reminders()` — SMS reminders for upcoming/past due bills
- `cron_create_disconnection_orders()` — Auto-disconnect severely overdue accounts

**Bill Protection:** `BILL_PROTECTED_FIELDS` list prevents editing on confirmed/sent bills.

---

#### 2.5.2 `sale.order.line` (Inherited)

| Added Field | Type | Description |
|-------------|------|-------------|
| `meter_line_type` | Selection | `consumption`, `service_charge`, `fixed_fee`, `mu_allim`, `cleaning`, `municipality`, `discount`, `penalty`, `other` |
| `sponsor_id` | Many2one → `res.partner` | Sponsor (for subsidized) |
| `contract_id` | Many2one → `utility.contract.template` | Contract template |

---

#### 2.5.3 `account.move` (Inherited)

| Added Field | Type | Description |
|-------------|------|-------------|
| `utility_sale_order_id` | Many2one → `sale.order` | Linked bill |
| `service_order_id` | Many2one → `utility.service.order` | Linked service order |
| `service_charge_id` | Many2one → `utility.service.charge` | Linked service charge |
| `meter_number` | Char | Meter number reference |
| `consumption_units` | Float | Consumption for this invoice |

---

#### 2.5.4 `account.payment` (Inherited)

| Added Field | Type | Description |
|-------------|------|-------------|
| `utility_sale_order_id` | Many2one → `sale.order` | Linked bill |
| `service_order_id` | Many2one → `utility.service.order` | Linked service order |
| `service_charge_id` | Many2one → `utility.service.charge` | Linked service charge |
| `utility_payment_method` | Selection | `cash`, `bank`, `online`, `pos`, `mobile` |
| `cashier_shift_id` | Many2one → `utility.cashier.shift` | POS cashier shift |
| `collector_shift_id` | Many2one → `utility.collector.shift` | Field collector shift |
| `date_range_id` | Many2one → `date.range` | Payment period |
| `qr_code` | Binary | Payment QR code |
| `is_reconciled` | Boolean | Auto-reconciled flag |

**Index:** `sale_order_id` (`index=True`).

**Method:** `_reconcile_utility_sale_order()` — Auto-reconciles payment with posted invoices via receivable account.

---

#### 2.5.5 `utility.reading` (Extended by utility_billing)

| Added Field | Type | Description |
|-------------|------|-------------|
| `batch_id` | Many2one → `utility.reading.batch` | Batch reference |

**Methods:**
- `action_generate_bill()` — Generate bill from approved reading
- `_cron_generate_bills()` — Batch bill generation (1000 per run)

---

#### 2.5.6 `utility.reading.batch` — Reading Batch Upload (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Batch reference |
| `file` | Binary | Yes | JSON file |
| `file_name` | Char | Yes | Filename |
| `state` | Selection | Yes | `draft`, `processing`, `done`, `error` |
| `total_readings` | Integer | No | Total in file |
| `processed_count` | Integer | No | Successfully processed |
| `error_count` | Integer | No | Errors |
| `reading_ids` | One2many → `utility.reading` | No | Created readings |
| `log_ids` | One2many → `utility.integration.log` | No | Processing logs |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Crons:**
- `_cron_process_readings()` — Process readings in configurable batches (every 10 min)
- `_cron_cleanup_old_batches()` — Archive old batches (daily)

---

#### 2.5.7 `date.range` (Extended by utility_billing)

| Added Field | Type | Description |
|-------------|------|-------------|
| `sale_order_ids` | One2many → `sale.order` | Bills in this period |
| `total_bills` | Integer | Computed bill count |
| `total_amount` | Monetary | Computed total amount |

**Method:** `action_generate_bills()` — Generate all bills for readings in this period.

---


#### 2.5.8 `utility.service.charge` — Service Order Charge (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Charge reference |
| `service_order_id` | Many2one → `utility.service.order` | Yes | Source service order |
| `account_id` | Many2one → `utility.customer` | Yes | Customer account |
| `partner_id` | Many2one → `res.partner` | Yes | Accounting partner |
| `product_id` | Many2one → `product.product` | Yes | Service fee product |
| `billing_method` | Selection | Yes | `none`, `invoice`, `direct_payment`, `next_bill` |
| `state` | Selection | Yes | `draft`, `confirmed`, `invoiced`, `payment_requested`, `paid`, `deferred`, `cancelled` |
| `invoice_id` | Many2one → `account.move` | No | Generated invoice |
| `payment_id` | Many2one → `account.payment` | No | Direct payment |
| `billing_charge_id` | Many2one ? `sale.order.line` | No | Next-bill sale order line |
| `amount_untaxed` | Monetary | No | Untaxed amount |
| `amount_tax` | Monetary | No | Tax amount |
| `amount_total` | Monetary | Yes | Total charge amount |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Rules:** Chargeable service orders must be financially cleared through an invoice, a direct payment, or deliberate next-bill deferral before completion. No customer credit ledger is created.

---

#### 2.5.9 `utility.penalty` — Late Payment Penalty (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reference |
| `sale_order_id` | Many2one → `sale.order` | Yes | Overdue bill |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `penalty_type_id` | Many2one → `utility.penalty.type` | Yes | Penalty type |
| `amount` | Monetary | Yes | Penalty amount |
| `days_overdue` | Integer | No | Days past due |
| `state` | Selection | Yes | `draft`, `posted`, `paid`, `cancelled` |
| `invoice_id` | Many2one → `account.move` | No | Generated penalty invoice |
| `currency_id` | Many2one → `res.currency` | Yes | Currency |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Index:** `sale_order_id` (`index=True`).

**Cron:** `cron_calculate_late_penalties()` — Daily, 500 per batch, enforces max penalty cap.

---

#### 2.5.10 `utility.penalty.type` — Penalty Type Catalog (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Type name |
| `code` | Char | Yes | Unique code |
| `default_amount` | Monetary | No | Default penalty amount |
| `max_percentage` | Float | No | Max % of bill amount |
| `active` | Boolean | Yes | Active toggle |

---

#### 2.5.11 `utility.writeoff` — Debt Write-off (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reference |
| `sale_order_id` | Many2one → `sale.order` | Yes | Bill to write off |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `amount` | Monetary | Yes | Write-off amount |
| `reason` | Text | Yes | Write-off reason |
| `state` | Selection | Yes | `draft`, `approved`, `posted` |
| `credit_note_id` | Many2one → `account.move` | No | Created credit note |
| `approved_by` | Many2one → `res.users` | No | Approver |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Action:** Creates `account.move` (out_refund) and reconciles with original invoice.

---

#### 2.5.12 `utility.deposit` — Customer Deposit (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reference |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `amount` | Monetary | Yes | Deposit amount |
| `state` | Selection | Yes | `received`, `released`, `forfeited` |
| `receipt_invoice_id` | Many2one → `account.move` | No | Receipt invoice |
| `release_invoice_id` | Many2one → `account.move` | No | Release invoice |
| `date_received` | Date | Yes | Receipt date |
| `date_released` | Date | No | Release date |
| `reason` | Text | No | Release/forfeit reason |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.5.13 `utility.financial.settlement` — Financial Settlement (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Reference |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `type` | Selection | Yes | `credit`, `debit` |
| `amount` | Monetary | Yes | Settlement amount |
| `reason` | Text | Yes | Settlement reason |
| `state` | Selection | Yes | `draft`, `approved`, `posted` |
| `invoice_id` | Many2one → `account.move` | No | Created invoice/credit note |
| `approved_by` | Many2one → `res.users` | No | Approver |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

**Action:** Credit → `out_refund`, Debit → `out_invoice`.

---

#### 2.5.14 `utility.installment.plan` / `utility.installment.plan.line` (New Models)

**Plan Fields:** `name`, `sale_order_id`, `account_id`, `total_amount`, `num_installments`, `state` (computed from lines), `company_id`.

**Line Fields:** `plan_id`, `installment_number`, `amount`, `due_date`, `state` (`pending`, `paid`, `overdue`), `payment_id`.

---

#### 2.5.15 `utility.collector.shift` — Collector Shift (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Shift reference |
| `user_id` | Many2one → `res.users` | Yes | Collector |
| `state` | Selection | Yes | `open`, `closed` |
| `opening_amount` | Monetary | Yes | Starting collection amount |
| `closing_amount` | Monetary | No | Ending amount |
| `payment_ids` | One2many → `account.payment` | No | Collected payments |
| `start_date` | Datetime | Yes | Start |
| `end_date` | Datetime | No | End |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

#### 2.5.16 `utility.cashier.shift` (Extended by utility_billing)

| Added Field | Type | Description |
|-------------|------|-------------|
| `payment_ids` | One2many → `account.payment` | Bill collection payments |
| `total_collections` | Monetary | Computed total |
| `total_cash_collections` | Monetary | Computed cash total |

---

#### 2.5.17 `sale.workflow.process` / `automatic.workflow.job` (New Models)

**Workflow Process:** `name`, `validate_order` (bool), `create_invoice` (bool), `validate_picking` (bool), `company_id`.

**Workflow Job:** Runs configured workflows periodically. Processes unprocessed `sale.order` records matching workflow criteria.

---

### 2.6 utility_portal — Portal Models

#### 2.6.1 `utility.payment.gateway.transaction` — Payment Gateway (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Transaction reference |
| `sale_order_id` | Many2one → `sale.order` | Yes | Bill |
| `account_id` | Many2one → `utility.customer` | Yes | Customer |
| `amount` | Monetary | Yes | Payment amount |
| `gateway_ref` | Char | No | Gateway reference |
| `state` | Selection | Yes | `pending`, `success`, `failed` |
| `payment_id` | Many2one → `account.payment` | No | Created payment |
| `response_data` | Text | No | Gateway response |
| `company_id` | Many2one → `res.company` | Yes | Multi-company |

---

### 2.7 utility_migration — Migration Models

#### 2.7.1 `utility.migration.customer` — Staging Table (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Legacy name |
| `legacy_code` | Char | Yes | Legacy system code |
| `partner_id` | Many2one → `res.partner` | No | Created partner |
| `customer_id` | Many2one → `utility.customer` | No | Created customer |
| `meter_id` | Many2one → `utility.meter` | No | Created meter |
| `region_code` | Char | No | Legacy region code |
| `area_code` | Char | No | Legacy area code |
| `category_code` | Char | No | Legacy category code |
| `subscriber_code` | Char | No | Legacy subscriber code |
| `contract_code` | Char | No | Legacy contract code |
| `state` | Selection | Yes | `draft`, `validated`, `imported`, `error` |
| `error_log` | Text | No | Import errors |
| `import_date` | Datetime | No | When imported |

**Methods:**
- `action_validate()` — Validate legacy codes against mapping table
- `action_import_data()` — Create partner/customer/meter/reading records
- `action_create_opening_balances()` — Generate `account.move` for opening balances

---

#### 2.7.2 `utility.migration.mapping` — Code Mapping (New Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Mapping name |
| `mapping_type` | Selection | Yes | `region`, `area`, `category`, `subscriber`, `contract` |
| `legacy_code` | Char | Yes | Legacy system code |
| `odoo_id` | Integer | Yes | Odoo record ID |
| `odoo_model` | Char | Yes | Target model name |
| `description` | Text | No | Mapping notes |

---

## 3. API Specification

### 3.1 Authentication

All API endpoints use **API key authentication** via HTTP header:
```
Authorization: Bearer <api_key>
```

### 3.2 Response Format

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

Error response:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Arabic error message"
  }
}
```

### 3.3 Endpoint Specification

#### 3.3.1 GET `/api/v1/utility/billing/balance`

**Purpose:** Get customer account balance and debt summary.

**Request:**
```json
{
  "partner_id": 123,
  "api_key": "xxx"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "customer_number": "CU-00001",
    "customer_name": "أحمد محمد",
    "outstanding_amount": 3200.50,
    "total_due_amount": 4700.50,
    "bills_count": 3,
    "overdue_bills_count": 1,
    "last_bill_date": "2026-06-01",
    "meter_number": "MTR-001234",
    "area_name": "المنطقة الأولى",
    "contract_template": "سكني قياسي"
  }
}
```

**Validation:** `partner_id` must match an active customer. Ownership check enforced.

---

#### 3.3.2 POST `/api/v1/utility/billing/bills`

**Purpose:** Get bill history for a customer.

**Request:**
```json
{
  "partner_id": 123,
  "limit": 10,
  "offset": 0,
  "date_from": "2026-01-01",
  "date_to": "2026-06-30"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "bills": [
      {
        "bill_number": "BILL/2026/001",
        "date": "2026-06-01",
        "period": "June 2026",
        "consumption": 450,
        "amount_energy": 2250.00,
        "amount_service": 150.00,
        "amount_penalty": 0.00,
        "amount_total": 2400.00,
        "amount_paid": 2400.00,
        "balance_due": 0.00,
        "bill_state": "paid"
      }
    ],
    "total_count": 6,
    "has_more": false
  }
}
```

---

#### 3.3.3 POST `/api/v1/utility/billing/pay`

**Purpose:** Record a direct payment against a bill.

**Request:**
```json
{
  "partner_id": 123,
  "sale_order_id": 456,
  "amount": 1000.00,
  "payment_method": "bank",
  "reference": "BANK-2026-001"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "payment_id": 789,
    "payment_reference": "PAY/2026/001",
    "amount": 1000.00,
    "remaining_balance": 1400.00,
    "bill_fully_paid": false
  }
}
```

**Side Effects:** Creates `account.payment`, triggers auto-reconciliation.

---

#### 3.3.4 POST `/api/v1/utility/billing/payment_intent`

**Purpose:** Initiate a payment through the payment gateway.

**Request:**
```json
{
  "partner_id": 123,
  "sale_order_id": 456,
  "amount": 2400.00
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "transaction_id": "TXN-2026-001",
    "gateway_url": "https://gateway.example.com/pay?token=xxx",
    "amount": 2400.00,
    "expires_at": "2026-07-12T15:00:00Z"
  }
}
```

---

#### 3.3.5 POST `/api/v1/utility/payment_gateway/webhook/<ref>`

**Purpose:** Payment gateway callback to confirm payment.

**Request:** Gateway sends payment confirmation with status.

**Response:**
```json
{
  "success": true,
  "data": {
    "transaction_id": "TXN-2026-001",
    "status": "success",
    "payment_id": 789
  }
}
```

**Side Effects:** Updates transaction state, creates payment, reconciles with bill.

---

#### 3.3.6 POST `/api/v1/utility/operations/service_request`

**Purpose:** Create a service order from customer request.

**Request:**
```json
{
  "partner_id": 123,
  "service_type": "complaint",
  "description": "rupted meter display",
  "priority": "medium"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "service_order_id": 101,
    "order_number": "SO/2026/001",
    "state": "draft",
    "service_type": "complaint",
    "estimated_response": "48 hours"
  }
}
```

---

#### 3.3.7 POST `/api/v1/utility/ami/reading_callback`

**Purpose:** Receive automated readings from AMI system.

**Request:**
```json
{
  "readings": [
    {
      "meter_number": "MTR-001234",
      "reading_value": 15750.5,
      "reading_date": "2026-07-12T08:00:00Z",
      "meter_status": "normal"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "processed": 1,
    "errors": 0,
    "readings_created": [
      {
        "meter_number": "MTR-001234",
        "reading_id": 2001,
        "consumption": 150.5,
        "status": "approved"
      }
    ]
  }
}
```

---

#### 3.3.8 POST `/api/v1/utility/reports/daily`

**Purpose:** Generate daily summary report.

**Request:**
```json
{
  "date": "2026-07-11",
  "api_key": "xxx"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "report_date": "2026-07-11",
    "total_bills_generated": 150,
    "total_amount_billed": 450000.00,
    "total_payments_received": 380000.00,
    "new_customers": 5,
    "tokens_generated": 230,
    "token_revenue": 115000.00,
    "service_orders_created": 12,
    "service_orders_completed": 8,
    "alarms_triggered": 3,
    "penalties_applied": 25
  }
}
```

---

## 4. Security Specification

### 4.1 Security Groups

```
نظام إدارة الكهرباء (Utility Management)
├── group_utility_readonly        — قارئ فقط
├── group_utility_cashier         — أمين صندوق (→ readonly)
├── group_utility_collector       — cobuctor (→ readonly)
├── group_utility_technician      — فني (→ readonly)
├── group_utility_field_inspector — مفتش ميداني (→ technician)
├── group_utility_supervisor      — مشرف (→ cashier + collector + technician)
├── group_utility_billing_manager — مدير الفوكرة (→ supervisor)
├── group_utility_revenue_manager — مدير الإيرادات (→ billing_manager)
├── group_utility_auditor         — مراجع (→ readonly)
└── group_utility_admin           — مدير النظام (→ revenue_manager + auditor + field_inspector)

 utilities (Inventory)
├── group_utility_inventory_user  — مستخدم المخزون (→ readonly)
└── group_utility_inventory_manager — مدير المخزون (→ inventory_user)
```

### 4.2 Access Control Matrix

| Model | admin | readonly | cashier | collector | technician | billing_manager | auditor |
|-------|-------|----------|---------|-----------|------------|-----------------|---------|
| utility.customer | CRUD | R | R | R | R | CRUD | R |
| utility.meter | CRUD | R | R | R | R/W | CRUD | R |
| utility.reading | CRUD | R | R | R | R/W | CRUD | R |
| sale.order (bills) | CRUD | R | R | R | R | CRUD | R |
| account.payment | CRUD | R | CRUD | CRUD | R | CRUD | R |
| utility.token | CRUD | R | CRUD | R | R | CRUD | R |
| utility.service.order | CRUD | R | R | R | CRUD | CRUD | R |
| utility.tamper.case | CRUD | R | R | R | CRUD | CRUD | R |
| utility.penalty | CRUD | R | R | R | R | CRUD | R |
| utility.writeoff | CRUD | R | R | R | R | CRUD | R |
| utility.deposit | CRUD | R | R | R | R | CRUD | R |
| utility.inventory.* | CRUD | R | R | R | R | R | R |
| utility.region | CRUD | R | R | R | R | R | R |
| utility.formula | CRUD | R | R | R | R | R | R |
| utility.contract.template | CRUD | R | R | R | R | CRUD | R |

### 4.3 Record Rules

All models with `company_id` have the standard multi-company rule:
```xml
<record model="ir.rule" id="rule_model_multi_company">
    <field name="name">Multi-company</field>
    <field name="model_id" ref="model_utility_customer"/>
    <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
</record>
```

### 4.4 API Security

1. **Token Authentication** — All REST API endpoints require valid API key
2. **Partner Ownership Validation** — `sudo()` + partner_id check ensures users only access their own data
3. **Input Validation** — All inputs validated against schema before processing
4. **Rate Limiting** — Configurable per-endpoint (recommended: 100 req/min per API key)

### 4.5 Formula Sandbox Security

```python
_FORMULA_SAFE_GLOBALS = {
    "__builtins__": {
        "abs": abs, "min": min, "max": max, "round": round,
        "int": int, "float": float, "len": len, "sum": sum,
        "range": range, "list": list, "dict": dict, "set": set,
        "tuple": tuple, "isinstance": isinstance,
        "True": True, "False": False, "None": None,
    }
}
# Only primitive values passed — no ORM context
safe_eval(expr, _FORMULA_SAFE_GLOBALS, mode="exec")
```

---

## 5. Automation & Cron Specification

| # | Cron Name | Module | Model | Method | Interval | Batch Size |
|---|-----------|--------|-------|--------|----------|-----------|
| 1 | Daily Bill Generation | billing | `date.range` | `cron_generate_bills_daily()` | Daily | — |
| 2 | Recurring Invoices | billing | `utility.contract.template` | `cron_generate_recurring_invoices()` | Hourly | — |
| 4 | Overdue Order Update | billing | `sale.order` | `cron_update_overdue_orders()` | Daily | — |
| 5 | Auto-pay Retry | billing | `utility.customer` | `cron_retry_auto_pay()` | 30 min | — |
| 6 | Batch Reading Invoicing | billing | `utility.reading` | `cron_queue_approved_readings()` | Daily | — |
| 7 | Late Penalties | billing | `utility.penalty` | `cron_calculate_late_penalties()` | Daily | 500 |
| 8 | Due Bill Reminders | billing | `sale.order` | `cron_send_due_reminders()` | Daily | — |
| 9 | Auto Disconnection | billing | `sale.order` | `cron_create_disconnection_orders()` | Daily | — |
| 10 | SMS Dispatch | core | `utility.notification.log` | `cron_dispatch_sms_notifications()` | 10 min | — |
| 11 | Batch Bill Generation | billing | `utility.reading` | `_cron_generate_bills()` | 15 min | 1000 |
| 12 | Process Batch Readings | billing | `utility.reading.batch` | `_cron_process_readings()` | 10 min | Configurable |
| 13 | Cleanup Old Batches | billing | `utility.reading.batch` | `_cron_cleanup_old_batches()` | Daily | — |

---

## 6. Formula Engine Specification

### 6.1 Supported Variables

| Variable | Type | Description |
|----------|------|-------------|
| `consumption` | float | kWh consumed in period |
| `previous_reading` | float | Previous meter reading |
| `current_reading` | float | Current meter reading |
| `tariff` | dict | `{'name': str, 'price_per_kwh': float}` |
| `account` | dict | `{'id': int, 'name': str}` |
| `category` | dict | `{'id': int, 'name': str}` |
| `line` | dict | `{'name': str, 'meter_line_type': str}` |
| `result` | float | Accumulator for computed amount |
| `name` | str | Formula/line name |

### 6.2 Example Formulas

```python
# Simple per-kwh
consumption * tariff['price_per_kwh']

# Block pricing
if consumption <= 100:
    result = consumption * 0.05
elif consumption <= 300:
    result = 100 * 0.05 + (consumption - 100) * 0.08
else:
    result = 100 * 0.05 + 200 * 0.08 + (consumption - 300) * 0.12
```

---

## 7. Notification System Specification

### 7.1 Notification Channels

| Channel | Transport | Use Case |
|---------|-----------|----------|
| `sms` | HTTP API to SMS provider | Bill alerts, token delivery, low credit, reminders |
| `portal` | In-app notification | Dashboard alerts, system messages |
| `internal` | Odoo chatter | Internal team notifications |

### 7.2 Dispatch Flow

```
Notification Created (state=draft)
        │
        ▼
cron_dispatch_sms_notifications() [every 10 min]
        │
        ▼
integration.provider.call_json() → SMS Provider API
        │
        ├── Success → state=sent, sent_date=now()
        └── Failure → state=failed, error_message=...
```

### 7.3 Key Notification Events

| Event | Channel | Template |
|-------|---------|----------|
| Bill generated | SMS | "Your bill for {period} is {amount}" |
| Bill overdue | SMS | "Your bill is overdue. Amount: {amount}" |
| Payment received | SMS | "Payment of {amount} received. Balance: {balance}" |
| Low credit | SMS | "Your balance is {balance}. Please recharge." |
| Token generated | SMS | "Your token is: {token}" |
| Service order update | SMS/Portal | "Your service order {ref} is now {state}" |

---

## 8. Portal Specification

### 8.1 Customer Portal Pages

| Route | Page | Content |
|-------|------|---------|
| `/my/utility/accounts` | Accounts | List of customer accounts with balance |
| `/my/utility/bills` | Bills | Bill history with details |
| `/my/utility/payments` | Payments | Payment history |
| `/my/utility/readings` | Readings | Reading history |

### 8.2 Portal Access Rules

- Portal users can only see records where `partner_id = current_user.partner_id`
- Read-only access (no create/edit/delete from portal)
- Service requests create backend records via API

---

## 9. Error Handling Specification

### 9.1 Exception Types

| Exception | Usage |
|-----------|-------|
| `UserError` | Business logic errors shown to user |
| `ValidationError` | Data validation failures (`@api.constrains`) |
| `AccessError` | Permission denied |

### 9.2 Error Message Standards

- All error messages in Arabic
- Include clear description of what went wrong
- Suggest how to fix the issue
- Example: `"لا يمكن تعديل فاتورة مؤكدة. يجب إلغاء التأكيد أولاً."` (Cannot edit a confirmed bill. Cancel confirmation first.)

### 9.3 API Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Input validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `ACCESS_DENIED` | 403 | No permission |
| `AUTHENTICATION_REQUIRED` | 401 | Missing/invalid API key |
| `INTERNAL_ERROR` | 500 | Server error |
| `PARTNER_MISMATCH` | 403 | API key owner doesn't match requested resource |

---

## 10. Testing Requirements

### 10.1 Test Coverage Targets

| Module | Minimum Coverage |
|--------|-----------------|
| utility_core | 80% |
| utility_billing | 85% |
| utility_prepaid | 80% |
| utility_operations | 75% |
| utility_portal | 80% |
| utility_inventory | 70% |
| utility_migration | 60% |

### 10.2 Required Test Scenarios

| Category | Test Cases |
|----------|-----------|
| **Billing** | Formula execution, block pricing, minimum/maximum charge, penalty calculation, write-off, installment plan |
| **Prepaid** | Token generation (idempotent), POS payment confirmation, reversal workflow |
| **Readings** | State transitions, consumption calculation, batch upload, settlement correction |
| **Security** | Multi-company isolation, API authentication, ownership validation, role-based access |
| **Crons** | Overdue detection, penalty calculation, batch processing, SMS dispatch |
| **API** | All 7 endpoints with valid/invalid inputs, authentication, error responses |
| **Formulas** | Block pricing, tier pricing, edge cases, zero consumption, maximum values |

### 10.3 Performance Test Scenarios

| Scenario | Target |
|----------|--------|
| Generate 1000 bills | < 5 minutes |
| Upload 1000 readings | < 3 minutes |
| API 95th percentile response | < 500ms |
| Dashboard load | < 3 seconds |
| Single bill generation | < 2 seconds |

---

*End of Software Requirements Specification*
