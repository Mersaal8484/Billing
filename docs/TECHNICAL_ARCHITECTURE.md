# Utility ERP — Technical Architecture Document

> **Document Version:** 1.0  
> **Date:** July 2026  
> **Classification:** Internal — Software Architecture  
> **Platform:** Odoo 16.0  
> **Database:** PostgreSQL 14+  
> **Runtime:** Python 3.10+

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [System Architecture](#2-system-architecture)
3. [Database Architecture](#3-database-architecture)
4. [Module Architecture](#4-module-architecture)
5. [API Architecture](#5-api-architecture)
6. [Security Architecture](#6-security-architecture)
7. [Integration Architecture](#7-integration-architecture)
8. [Performance Architecture](#8-performance-architecture)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Data Flow Diagrams](#10-data-flow-diagrams)
11. [Development Standards](#11-development-standards)
12. [Monitoring & Observability](#12-monitoring--observability)

---

## 1. Architecture Overview

### 1.1 Architectural Principles

| Principle | Description |
|-----------|-------------|
| **Modularity** | 7 independent addon modules with clear dependency boundaries |
| **Convention over Configuration** | Leverage Odoo 16 ORM conventions; minimize custom configuration |
| **Single Responsibility** | Each module owns one business domain |
| **DRY** | Reuse Odoo core models via inheritance instead of duplication |
| **Defense in Depth** | Security at model, record, API, and UI layers |
| **Eventual Consistency** | Cron-based batch processing for non-real-time operations |
| **Sandbox Isolation** | Formula execution completely isolated from ORM context |

### 1.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │
│  │  Odoo Web UI  │  │  POS Terminal  │  │ Customer      │          │
│  │  (OWL 2.0)    │  │  (Odoo POS)    │  │ Portal (QWeb) │          │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘          │
│          │                  │                   │                   │
├──────────┼──────────────────┼───────────────────┼───────────────────┤
│          │           API LAYER                  │                   │
│  ┌───────▼───────┐  ┌───────▼───────┐  ┌───────▼───────┐          │
│  │   XML-RPC     │  │ JSON REST API │  │  Webhook      │          │
│  │  (Odoo Core)  │  │ (Controllers) │  │ (Payment GW)  │          │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘          │
│          │                  │                   │                   │
├──────────┼──────────────────┼───────────────────┼───────────────────┤
│                    APPLICATION LAYER                                │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                   Odoo 16 ORM Engine                      │      │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │      │
│  │  │ utility  │ │ utility  │ │ utility  │ │ utility  │   │      │
│  │  │  _core   │ │_inventory│ │ _prepaid │ │operations│   │      │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │      │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                │      │
│  │  │ utility  │ │ utility  │ │ utility  │                │      │
│  │  │_billing  │ │ _portal  │ │_migration│                │      │
│  │  └──────────┘ └──────────┘ └──────────┘                │      │
│  └──────────────────────────┬───────────────────────────────┘      │
│                             │                                      │
├─────────────────────────────┼──────────────────────────────────────┤
│                      DATA LAYER                                    │
│  ┌──────────────────────────▼──────────────────────────────┐      │
│  │                  PostgreSQL 14+                          │      │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │      │
│  │  │  Utility     │  │  Standard    │  │  ir.*        │  │      │
│  │  │  Models      │  │  Odoo Models │  │  Registry    │  │      │
│  │  │  (71 models) │  │  (sale, acct)│  │  (security)  │  │      │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │      │
│  └─────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌──────────────────┐              ┌──────────────────┐
│  External Systems │              │  File Storage    │
│  • STS Server     │              │  • Attachments   │
│  • SMS Provider   │              │  • QR Codes      │
│  • Payment GW     │              │  • Meter Images  │
│  • AMI System     │              │  • Batch Files   │
└──────────────────┘              └──────────────────┘
```

### 1.3 Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ERP Platform | Odoo 16.0 | Rich built-in modules (sale, account, POS, stock), mature ORM, Arabic RTL support |
| Billing Model | `sale.order` inheritance | Leverages Odoo's sale workflow, invoice generation, payment reconciliation |
| POS Model | `pos.order` inheritance | Native POS UI, token generation on order completion |
| Payment Model | `account.payment` inheritance | Automatic journal entry creation and reconciliation |
| Geographic Hierarchy | Self-referential `utility.region` | Flexible 8-level tree without hardcoding levels |
| Formula Engine | `safe_eval()` | Dynamic billing without code deployment; sandboxed for security |
| Notifications | SMS only (no email) | No email server available; SMS + portal for customer comms |
| API | JSON REST controllers | Lightweight integration for AMI, payment gateway, portal |
| Batch Processing | Cron-based | Handles large volumes (1000+ bills) without blocking UI |

---

## 2. System Architecture

### 2.1 Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Presentation                              │
│  • OWL 2.0 widgets (Forms, Trees, Kanban, Search)  │
│  • QWeb templates (Portal, Reports)                 │
│  • POS UI (native Odoo POS)                         │
├─────────────────────────────────────────────────────┤
│  Layer 2: API                                       │
│  • XML-RPC (Odoo standard)                          │
│  • JSON REST (utility_portal controllers)           │
│  • Webhook receivers (payment gateway, AMI)         │
├─────────────────────────────────────────────────────┤
│  Layer 3: Business Logic (Models)                   │
│  • Domain models (71 new + 12 inherited)            │
│  • Computed fields and constraints                  │
│  • Workflow state machines                          │
│  • Formula engine (safe_eval)                       │
├─────────────────────────────────────────────────────┤
│  Layer 4: ORM / Data Access                         │
│  • Odoo ORM (read, write, search, create)           │
│  • Computed stored fields                           │
│  • Record rules (multi-company)                     │
│  • Access control lists (ir.model.access)           │
├─────────────────────────────────────────────────────┤
│  Layer 5: Database                                  │
│  • PostgreSQL 14+                                   │
│  • JSONB for flexible data                          │
│  • Indexes on critical fields                       │
│  • Backups (daily automated)                        │
└─────────────────────────────────────────────────────┘
```

### 2.2 Module Interaction Diagram

```
                    utility_core (Foundation)
                    ┌──────────────────────┐
                    │ Customers            │
                    │ Meters               │
                    │ Readings             │
                    │ Regions              │
                    │ Contracts            │
                    │ Formulas             │
                    │ Notifications        │
                    │ Settings             │
                    └──────────┬───────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
    utility_inventory    utility_prepaid    utility_operations
    ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
    │ Locations    │    │ POS Orders   │   │ Service Orders│
    │ Items        │    │ Tokens       │   │ Inspections   │
    │ Movements    │    │ Transactions │   │ Tamper Cases  │
    │ Counts       │    │ Reversals    │   │ Alarms        │
    │ Meter Lots   │    │ Cashier Shift│   │ Work Orders   │
    └──────┬───────┘    │ + extend POS │   │ Settlements   │
           │            └──────┬───────┘   └──────┬───────┘
           │                   │                  │
           └───────────────────┼──────────────────┘
                               │
                               ▼
                    utility_billing
                    ┌──────────────────────┐
                    │ Bills (sale.order)    │
                    │ Batch Readings        │
                    │ Billing Cycles        │
                    │ Penalties             │
                    │ Write-offs            │
                    │ Deposits              │
                    │ Installment Plans     │
                    │ Financial Settlements │
                    │ Cashier/Collector Shift│
                    │ Workflow Automation   │
                    └──────────┬───────────┘
                               │
                    ┌──────────┼──────────┐
                    │                     │
                    ▼                     ▼
            utility_portal         utility_migration
            ┌──────────────┐     ┌──────────────┐
            │ REST API     │     │ Staging      │
            │ Portal Pages │     │ Mapping      │
            │ Payment GW   │     │ Excel Import │
            └──────────────┘     └──────────────┘
```

---

## 3. Database Architecture

### 3.1 Schema Overview

**Total Tables:** ~85 (71 new models + 12 inherited + 2 transient)

#### New Table Categories

| Category | Count | Examples |
|----------|-------|---------|
| Geographic | 6 | `utility_region`, `utility_office`, `utility_substation`, `utility_feeder`, `utility_transformer`, `utility_route` |
| Customer | 5 | `utility_customer`, `utility_customer_balance_transaction`, `utility_subscriber_category`, `utility_subscriber`, `utility_connection` |
| Metering | 7 | `utility_meter`, `utility_meter_type`, `utility_meter_model`, `utility_meter_status`, `utility_meter_log`, `utility_reading`, `utility_reading_batch` |
| Contracts | 4 | `utility_contract_template`, `utility_contract_template_line`, `utility_contract_template_block`, `utility_formula` |
| Billing | 12 | `utility_penalty`, `utility_penalty_type`, `utility_writeoff`, `utility_deposit`, `utility_financial_settlement`, `utility_installment_plan`, `utility_installment_plan_line`, `utility_collector_shift`, `sale_workflow_process`, `automatic_workflow_job`, `utility_reading_settlement`, `utility_recurring_invoice` |
| Prepaid | 5 | `utility_token`, `utility_transaction`, `utility_reversal`, `utility_adjustment`, `utility_cashier_shift` |
| Operations | 7 | `utility_service_order`, `utility_installation`, `utility_inspection`, `utility_tamper_case`, `utility_alarm`, `utility_work_order`, `utility_reading_settlement` |
| Inventory | 4 | `utility_inventory_location`, `utility_inventory_item`, `utility_inventory_movement`, `utility_inventory_count` (+ `_count_line`) |
| Integration | 4 | `utility_integration_provider`, `utility_integration_log`, `utility_notification_log`, `utility_payment_gateway_transaction` |
| Migration | 2 | `utility_migration_customer`, `utility_migration_mapping` |
| Portal | 1 | `utility_payment_gateway_transaction` |

### 3.2 Inherited Table Extensions

| Odoo Table | Extended By | Added Columns |
|------------|-------------|---------------|
| `res_partner` | utility_core | `region_id`, `area_id`, `previous_hotline_balance` |
| `res_company` | utility_core | 7 accounting/product FKs |
| `res_users` | utility_core | `collection_journal_id`, `prevent_installment` |
| `sale_order` | utility_billing | ~40 fields (account, meter, reading, amounts, bill_state, etc.) |
| `sale_order_line` | utility_billing | `meter_line_type`, `sponsor_id`, `contract_id` |
| `account_move` | utility_billing | `utility_sale_order_id`, `meter_number`, `consumption_units` |
| `account_payment` | utility_billing | `utility_sale_order_id`, payment method, shift IDs, QR |
| `pos_order` | utility_prepaid | `account_id`, `meter_id`, `token_id`, `cashier_shift_id` |
| `pos_order_line` | utility_prepaid | (empty extension) |
| `date_range` | utility_billing | `sale_order_ids`, totals |
| `utility_meter` | utility_inventory | `product_id`, `lot_id` |
| `utility_meter_replacement` | utility_operations | `action_complete_replacement()` |
| `utility_contract_template` | utility_billing | `_prepare_sale_order_data()`, `cron_generate_recurring_invoices()` |
| `utility_cashier_shift` | utility_prepaid/billing | `payment_ids`, totals |

### 3.3 Key Indexes

| Table | Column | Type | Purpose |
|-------|--------|------|---------|
| `sale_order` | `bill_state` | B-tree | Fast bill state filtering |
| `sale_order` | `balance_due` | B-tree | Outstanding balance queries |
| `sale_order` | `is_overdue` | B-tree | Overdue bill identification |
| `utility_reading` | `state` | B-tree | Reading workflow filtering |
| `utility_penalty` | `sale_order_id` | B-tree | Penalty-to-bill lookup |
| `account_payment` | `utility_sale_order_id` | B-tree | Payment-to-bill lookup |
| `utility_customer` | `customer_number` | B-tree (unique) | Customer lookup |
| `utility_meter` | `meter_number` | B-tree (unique) | Meter lookup |
| `utility_token` | `token_number` | B-tree (unique) | Token lookup |
| `utility_region` | `type` | B-tree | Hierarchy type filtering |
| `utility_region` | `parent_id` | B-tree | Parent-child traversal |

### 3.4 Entity Relationship Diagram (Key Entities)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   res.partner   │1───1│utility.customer  │N───1│  utility.meter   │
│                 │     │                 │     │                 │
│  - name         │     │  - customer_no  │     │  - meter_number │
│  - email        │     │  - state        │     │  - meter_type   │
│  - phone        │     │  - prepaid_bal  │     │  - meter_model  │
│  - region_id    │     │  - category_id  │     │  - status_id    │
│  - area_id      │     │  - subscriber_id│     │  - qr_code      │
└─────────────────┘     │  - contract_tmpl│     └────────┬────────┘
                        │  - cell_id      │              │
                        └────────┬────────┘              │
                                 │                       │
                    N:1          │          N:1          │
                        ┌────────▼────────┐              │
                        │utility.region   │              │
                        │(8-level NUTS)   │              │
                        │  - type         │              │
                        │  - parent_id    │              │
                        └─────────────────┘              │
                                                         │
                        N:1                              │
                ┌─────────────────┐                      │
                │utility.transformer│◄────────────────────┘
                │  - is_cell      │
                │  - parent_id    │
                │  - _parent_store│
                └─────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   sale.order    │1───1│  sale.order     │N───1│  utility.reading │
│  (inherited)    │     │  .line (inherited)    │                 │
│                 │     │                 │     │  - reading_value │
│  - bill_state   │     │  - meter_line_  │     │  - consumption   │
│  - amount_energy│     │    type         │     │  - state         │
│  - amount_paid  │     │  - sponsor_id   │     │  - batch_id      │
│  - balance_due  │     └─────────────────┘     └─────────────────┘
│  - is_overdue   │
│  - account_id   │──────► utility.customer
│  - meter_id     │──────► utility.meter
│  - date_range_id│──────► date.range
│  - tariff_id    │──────► utility.contract.template
└────────┬────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐     ┌─────────────────┐
│ account.payment │     │ utility.penalty  │
│  (inherited)    │     │                 │
│                 │     │  - amount       │
│  - utility_     │     │  - days_overdue │
│    sale_order_id│     │  - state        │
│  - payment_     │     │  - invoice_id   │
│    method       │     └─────────────────┘
│  - qr_code      │
└─────────────────┘
```

### 3.5 Key Computed Fields & Dependencies

| Field | Model | Depends | Storage | Notes |
|-------|-------|---------|---------|-------|
| `consumption` | `utility.reading` | `reading_value`, `previous_reading` | Stored | Simple subtraction |
| `balance` | `utility.customer` | `balance_transaction_ids.amount` | Stored | Sum of transactions |
| `bill_state` | `sale.order` | `state`, `is_overdue`, `balance_due`, `invoice_payment_state` | Stored, indexed | Complex multi-source |
| `balance_due` | `sale.order` | `amount_total`, `amount_paid`, `previous_balance` | Stored, indexed | Financial calculation |
| `is_overdue` | `sale.order` | `date_order`, `invoice_payment_state`, `bill_state` | Stored, indexed | Overdue detection |
| `total_collections` | `utility.cashier.shift` | `payment_ids.amount` | Computed | Shift totals |
| `total_bills` | `date.range` | `sale_order_ids` | Computed | Period totals |

---

## 4. Module Architecture

### 4.1 Module Structure Pattern

Each module follows the standard Odoo 16 addon structure:

```
utility_<module>/
├── __init__.py                    # Module root
├── __manifest__.py                # Module metadata & dependencies
├── models/
│   ├── __init__.py                # Model imports
│   └── utility_<model>.py         # Model definitions
├── views/
│   ├── utility_<model>_views.xml  # Form, Tree, Search views
│   ├── utility_<menu>.xml         # Menu definitions
│   └── utility_<action>.xml       # Action definitions
├── security/
│   ├── ir.model.access.csv        # Access control lists
│   └── utility_security.xml       # Security groups & record rules
├── data/
│   ├── utility_sequence.xml       # Auto-numbering sequences
│   ├── utility_cron.xml           # Cron job definitions
│   └── utility_<data>.xml         # Seed data (catalogs, etc.)
├── wizard/
│   ├── __init__.py
│   └── utility_<wizard>.py        # Transient model wizards
├── controllers/
│   ├── __init__.py
│   └── utility_api.py             # REST API endpoints
├── static/
│   └── description/
│       └── icon.png               # Module icon
├── README.rst
└── tests/
    └── __init__.py                # Test modules
```

### 4.2 Module Dependency Graph (Detailed)

```
date_range (OCA)
    │
    ▼
utility_core ─────────────────────────────────────────┐
    │                                                  │
    ├──► utility_inventory                             │
    │        (extends utility.meter)                   │
    │                                                  │
    ├──► utility_prepaid                               │
    │        (extends pos.order, pos.order.line)       │
    │                                                  │
    └──► utility_operations                            │
             (extends utility.meter.replacement)       │
                                                      │
    ┌─────────────────────────────────────────────────┘
    │
    ▼
utility_billing ───────────────────────────────┐
    │  (extends sale.order, sale.order.line,    │
    │   account.move, account.payment,         │
    │   date.range, utility.contract.template,  │
    │   utility.reading, utility.cashier.shift) │
    │                                           │
    ├──► utility_portal                         │
    │        (controllers + portal templates)   │
    │                                           │
    └──► utility_migration
             (staging + import wizards)
```

### 4.3 Inheritance Strategy

| Strategy | When Used | Examples |
|----------|-----------|---------|
| **New Model** | New business entity | `utility.customer`, `utility.meter`, `utility.token` |
| **Inherit (classical)** | Extending existing Odoo model | `sale.order` → billing, `pos.order` → prepaid, `account.payment` → collections |
| **Abstract Mixin** | Shared behavior | `utility.dropdown.mixin` — shared date range filtering |
| **Transient Model** | Wizards, temporary data | `utility.customer.wizard`, `utility.migration.import.wizard` |

---

## 5. API Architecture

### 5.1 API Design

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Odoo Controllers)            │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Authentication Middleware                           │   │
│  │  • Extract API key from Authorization header         │   │
│  │  • Validate key against utility.integration.provider │   │
│  │  • Set request context (company, user)               │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────▼─────────────────────────────┐   │
│  │  Validation Layer                                    │   │
│  │  • Schema validation (required fields, types)        │   │
│  │  • Partner ownership check                           │   │
│  │  • Business rule validation                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────▼─────────────────────────────┐   │
│  │  Business Logic Layer                                │   │
│  │  • Model operations (create, read, update)           │   │
│  │  • Workflow state transitions                        │   │
│  │  • Amount calculations                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────▼─────────────────────────────┐   │
│  │  Response Layer                                      │   │
│  │  • Standardized JSON response format                 │   │
│  │  • Error handling and formatting                     │   │
│  │  • Audit logging                                     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Controller Pattern

```python
class UtilityAPIController(http.Controller):

    @http.route('/api/v1/utility/<domain>/<action>', type='json',
                auth='public', methods=['POST'], csrf=False)
    def handle_request(self, domain, action, **kwargs):
        # 1. Authentication
        api_key = request.httprequest.headers.get('Authorization')
        provider = self._authenticate(api_key)
        if not provider:
            return self._error_response('AUTHENTICATION_REQUIRED', 401)

        # 2. Parse & Validate
        data = request.jsonrequest
        self._validate_schema(domain, action, data)

        # 3. Partner Ownership
        partner = self._get_partner(data.get('partner_id'))
        if not partner or not self._check_ownership(partner, api_key):
            return self._error_response('PARTNER_MISMATCH', 403)

        # 4. Execute Business Logic
        result = self._execute(domain, action, data, partner)

        # 5. Audit Log
        self._log_request(domain, action, partner, result)

        return self._success_response(result)
```

### 5.3 Authentication Flow

```
Client Request
    │
    ├─ Header: Authorization: Bearer <api_key>
    │
    ▼
┌──────────────────────────┐
│ Parse API key            │
│                          │
│ Query utility.integration│
│ .provider where:         │
│   api_key = <key>        │
│   provider_type = 'api'  │
│   active = True          │
└──────────┬───────────────┘
           │
    ┌──────▼──────┐
    │  Key Valid?  │
    └──────┬──────┘
       Yes │    No → 401 Unauthorized
           ▼
┌──────────────────────────┐
│ Set request context:     │
│   company = provider.co  │
│   user = system user     │
└──────────────────────────┘
```

### 5.4 Webhook Processing (Payment Gateway)

```
Payment Gateway
    │
    ├─ POST /api/v1/utility/payment_gateway/webhook/<ref>
    │
    ▼
┌──────────────────────────┐
│ 1. Validate webhook ref  │
│ 2. Parse callback data   │
│ 3. Find transaction by   │
│    gateway_ref           │
│ 4. Update transaction    │
│    state                 │
│ 5. Create account.payment│
│ 6. Reconcile with bill   │
│ 7. Update bill state     │
│ 8. Return confirmation   │
└──────────────────────────┘
```

---

## 6. Security Architecture

### 6.1 Security Layers

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Authentication                            │
│  • API key authentication (REST endpoints)          │
│  • Session-based auth (Odoo web client)             │
│  • POS authentication (local network)               │
├─────────────────────────────────────────────────────┤
│  Layer 2: Authorization (Groups)                    │
│  • 10 utility groups + 2 inventory groups           │
│  • Hierarchical implication chain                   │
│  • Group-based menu/view visibility                 │
├─────────────────────────────────────────────────────┤
│  Layer 3: Access Control (ACL)                      │
│  • ir.model.access.csv per model per group          │
│  • CRUD permissions per group                       │
│  • ~113 ACL rules                                   │
├─────────────────────────────────────────────────────┤
│  Layer 4: Record Rules                              │
│  • Multi-company isolation                          │
│  • Domain: ['|', ('company_id','=',False),          │
│             ('company_id','in',company_ids)]         │
├─────────────────────────────────────────────────────┤
│  Layer 5: Business Logic Security                   │
│  • Partner ownership validation on API              │
│  • Bill field protection on confirmation            │
│  • Reading edit protection after billing            │
│  • Formula sandbox (safe_eval + _FORMULA_SAFE_GLOBALS)│
│  • State transition validation                      │
│  • Single-open-shift constraint                     │
├─────────────────────────────────────────────────────┤
│  Layer 6: Audit                                     │
│  • Chatter tracking on critical models              │
│  • Meter event logging (utility.meter.log)          │
│  • Integration API call logging                     │
│  • Notification dispatch logging                    │
│  • Migration import logging                         │
└─────────────────────────────────────────────────────┘
```

### 6.2 Security Group Hierarchy

```
group_utility_admin
├── implies: group_utility_revenue_manager
│   └── implies: group_utility_billing_manager
│       └── implies: group_utility_supervisor
│           ├── implies: group_utility_cashier
│           │   └── implies: group_utility_readonly
│           ├── implies: group_utility_collector
│           │   └── implies: group_utility_readonly
│           └── implies: group_utility_technician
│               └── implies: group_utility_readonly
├── implies: group_utility_auditor
│   └── implies: group_utility_readonly
└── implies: group_utility_field_inspector
    └── implies: group_utility_technician

group_utility_inventory_manager
└── implies: group_utility_inventory_user
    └── implies: group_utility_readonly
```

### 6.3 Formula Sandbox Details

```python
# Isolation boundaries:
# 1. No ORM objects passed (no env, no self)
# 2. Only primitive values (id, name, numeric)
# 3. Restricted builtins (math functions only)
# 4. No import, no eval, no exec within formula
# 5. Execution timeout via safe_eval limits

_FORMULA_SAFE_GLOBALS = {
    "__builtins__": {
        # Math only
        "abs": abs, "min": min, "max": max,
        "round": round, "int": int, "float": float,
        "len": len, "sum": sum, "range": range,
        # Data structures (safe)
        "list": list, "dict": dict, "set": set,
        "tuple": tuple, "isinstance": isinstance,
        # Constants
        "True": True, "False": False, "None": None,
    }
}
```

---

## 7. Integration Architecture

### 7.1 Integration Topology

```
┌─────────────────────────────────────────────────────┐
│                    UTILITY ERP                       │
│                                                     │
│  ┌───────────────────┐   ┌───────────────────┐     │
│  │  utility_core      │   │  utility_prepaid   │     │
│  │  (SMS Dispatch)   │   │  (Token Gen)       │     │
│  └─────────┬─────────┘   └─────────┬─────────┘     │
│            │                       │                 │
│            ▼                       ▼                 │
│  ┌───────────────────┐   ┌───────────────────┐     │
│  │ integration.      │   │ integration.      │     │
│  │ provider.call_json│   │ provider.call_json│     │
│  └─────────┬─────────┘   └─────────┬─────────┘     │
└────────────┼───────────────────────┼─────────────────┘
             │                       │
             ▼                       ▼
┌────────────────────┐   ┌────────────────────┐
│   SMS Provider     │   │   STS Token Server  │
│   (HTTP API)       │   │   (HTTP API)        │
└────────────────────┘   └────────────────────┘

┌─────────────────────────────────────────────────────┐
│  INBOUND INTEGRATIONS                                │
│                                                     │
│  ┌───────────────────┐   ┌───────────────────┐     │
│  │  AMI Callback     │   │  Payment Gateway   │     │
│  │  (REST Webhook)   │   │  Webhook           │     │
│  └─────────┬─────────┘   └─────────┬─────────┘     │
│            │                       │                 │
│            ▼                       ▼                 │
│  ┌───────────────────┐   ┌───────────────────┐     │
│  │ utility_portal     │   │ utility_portal     │     │
│  │ /ami/reading_     │   │ /payment_gateway/  │     │
│  │ callback          │   │ webhook/<ref>      │     │
│  └─────────┬─────────┘   └─────────┬─────────┘     │
│            │                       │                 │
│            ▼                       ▼                 │
│  ┌───────────────────┐   ┌───────────────────┐     │
│  │ utility.reading   │   │ gateway.transaction│     │
│  │ (create/update)   │   │ (update + pay)    │     │
│  └───────────────────┘   └───────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 7.2 Integration Patterns

| Integration | Pattern | Direction | Failure Handling |
|-------------|---------|-----------|-----------------|
| STS Token Server | Sync HTTP Request | Outbound | Token marked `error`, retry via cron |
| SMS Provider | Async Cron Dispatch | Outbound | Notification marked `failed`, logged |
| Payment Gateway | Sync + Webhook | Bidirectional | Transaction stuck in `pending`, timeout after 24h |
| AMI System | Webhook Callback | Inbound | Reading queued in `error` state, manual retry |
| POS Terminal | Internal Odoo | Internal | POS offline mode, sync on reconnect |

### 7.3 Integration Configuration

All external providers configured via `utility.integration.provider`:

```python
# Example provider configuration
{
    'name': 'SMS Provider Alpha',
    'provider_type': 'sms',
    'url': 'https://sms-api.example.com/send',
    'api_key': 'sk_live_xxxxx',
    'active': True,
}
```

### 7.4 Integration Logging

Every external API call logged to `utility.integration.log`:
- Request URL, method, payload (sanitized)
- Response status, body
- Duration (ms)
- Success/failure
- Provider reference

---

## 8. Performance Architecture

### 8.1 Performance Targets

| Operation | Target | Current Strategy |
|-----------|--------|-----------------|
| Single bill generation | < 2s | `_calculate_amounts()` with bulk line creation |
| Batch bill (1000) | < 5min | Cron with batch limit, ORM prefetch |
| Reading upload (1000) | < 3min | Configurable batch size, offset-based processing |
| Token generation | < 5s | Idempotent check + STS API call |
| API response (p95) | < 500ms | Indexed queries, `search_read()` |
| Dashboard load | < 3s | `read_group()` aggregation, stored computed fields |

### 8.2 Performance Optimizations

#### N+1 Query Prevention

```python
# BAD: N+1 queries
for reading in readings:
    customer = reading.account_id  # Separate query each iteration

# GOOD: Prefetch
readings = self.env['utility.reading'].search([...])
# ORM automatically prefetches Many2one fields
for reading in readings:
    customer = reading.account_id  # Already prefetched
```

#### Bulk Operations

```python
# BAD: Individual creates
for data in batch:
    self.env['sale.order.line'].create(data)

# GOOD: Bulk create
self.env['sale.order.line'].create([data for data in batch])
```

#### Aggregation Queries

```python
# BAD: Search + loop + sum
bills = self.env['sale.order'].search([('state', '=', 'posted')])
total = sum(bills.mapped('amount_total'))

# GOOD: read_group
result = self.env['sale.order'].read_group(
    [('state', '=', 'posted')],
    ['amount_total'],
    [],
)
total = result[0]['amount_total']
```

#### Computed Field Optimization

```python
# Stored computed fields for frequently queried fields
bill_state = fields.Selection(
    [...],
    compute='_compute_bill_state',
    store=True,  # Stored for search performance
    index=True,  # Indexed for filtering
)

# depends() chain optimized to minimum necessary fields
@api.depends('state', 'is_overdue', 'balance_due', 'invoice_payment_state')
def _compute_bill_state(self):
    # Batch computation for all records
    for record in self:
        # Fast inline logic
        pass
```

### 8.3 Database Index Strategy

| Index Type | Columns | Rationale |
|------------|---------|-----------|
| B-tree (default) | `bill_state`, `balance_due`, `is_overdue` | High-frequency filter/sort |
| B-tree | `utility.reading.state` | Workflow filtering |
| B-tree | `utility.penalty.sale_order_id` | FK lookup |
| B-tree | `account.payment.utility_sale_order_id` | FK lookup |
| Unique B-tree | `customer_number`, `meter_number`, `token_number` | Business key uniqueness |
| B-tree | `utility.region.type`, `utility.region.parent_id` | Hierarchy traversal |

### 8.4 Batch Processing Architecture

```
┌─────────────────────────────────────────────────────┐
│              BATCH PROCESSING ENGINE                 │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  Cron Trigger (configurable interval)       │   │
│  └──────────────────────┬──────────────────────┘   │
│                         │                           │
│  ┌──────────────────────▼──────────────────────┐   │
│  │  Query Pending Records                      │   │
│  │  search([...], limit=batch_size)            │   │
│  │  batch_size from: res.config.settings       │   │
│  │    reading_upload_batch_size: default 100    │   │
│  │    penalty_batch_size: default 500          │   │
│  │    bill_generation_batch: default 1000      │   │
│  └──────────────────────┬──────────────────────┘   │
│                         │                           │
│  ┌──────────────────────▼──────────────────────┐   │
│  │  Process Batch (with savepoint)             │   │
│  │  for record in batch:                       │   │
│  │      try:                                   │   │
│  │          record.process()                    │   │
│  │      except Exception:                      │   │
│  │          record.log_error()                 │   │
│  └──────────────────────┬──────────────────────┘   │
│                         │                           │
│  ┌──────────────────────▼──────────────────────┐   │
│  │  Commit / Rollback                          │   │
│  │  If all OK: commit                          │   │
│  │  If partial: commit processed, log errors   │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 9. Deployment Architecture

### 9.1 Deployment Topology

```
┌─────────────────────────────────────────────────────────┐
│                   PRODUCTION ENVIRONMENT                 │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Application Server                  │   │
│  │  ┌─────────────────────────────────────────┐    │   │
│  │  │  Odoo 16.0 Process                      │    │   │
│  │  │  • Web workers (configurable)           │    │   │
│  │  │  • Cron worker (single)                 │    │   │
│  │  │  • Longpolling worker                   │    │   │
│  │  └─────────────────────────────────────────┘    │   │
│  │  ┌─────────────────────────────────────────┐    │   │
│  │  │  Python 3.10+ Runtime                   │    │   │
│  │  │  • 71 custom models                     │    │   │
│  │  │  • 13 cron jobs                         │    │   │
│  │  │  • 7 API endpoints                      │    │   │
│  │  └─────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         │ TCP 5432                      │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │              PostgreSQL 14+ Server               │   │
│  │  ┌─────────────────────────────────────────┐    │   │
│  │  │  Database: utility_erp                  │    │   │
│  │  │  • ~85 tables                           │    │   │
│  │  │  • ~113 ACL rules                       │    │   │
│  │  │  • Daily backups (pg_dump)              │    │   │
│  │  └─────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │              File Storage                        │   │
│  │  • /opt/odoo/filestore/ (attachments, images)   │   │
│  │  • /opt/odoo/addons/utility_erp/ (code)        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                         │
                         │ HTTPS (443)
                         ▼
┌─────────────────────────────────────────────────────────┐
│              REVERSE PROXY (Nginx)                       │
│  • SSL termination                                       │
│  • Static file serving                                   │
│  • Load balancing (if multi-worker)                      │
│  • Rate limiting for API endpoints                       │
└─────────────────────────────────────────────────────────┘
         │                 │                  │
         ▼                 ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Odoo Web UI │  │  REST API    │  │  POS Terminal │
│  (Browser)   │  │  (External)  │  │  (LAN)       │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 9.2 Configuration Parameters

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| `reading_upload_batch_size` | `res.config.settings` | 100 | Readings per batch processing cycle |
| `penalty_max_percentage` | `res.config.settings` | 30 | Max penalty as % of bill |
| `emergency_credit_limit` | `res.config.settings` | 500 | Max emergency credit per customer |
| `sms_provider_id` | `res.config.settings` | — | Active SMS provider |
| `ami_provider_id` | `res.config.settings` | — | Active AMI provider |
| `payment_gateway_id` | `res.config.settings` | — | Active payment gateway |
| `overdue_days_threshold` | `res.config.settings` | 30 | Days before disconnection |
| `consumption_alert_threshold` | `res.config.settings` | 200% | Alert if consumption > X% of previous |

### 9.3 Backup Strategy

| Component | Frequency | Retention | Method |
|-----------|-----------|-----------|--------|
| Database | Daily 02:00 | 30 days | `pg_dump` compressed |
| Filestore | Daily 03:00 | 30 days | tar.gz archive |
| Code repository | Git (continuous) | Unlimited | Git + remote push |
| Configuration | On change | 90 days | Version controlled |

---

## 10. Data Flow Diagrams

### 10.1 Bill Generation Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  AMI /   │──>│ Reading  │──>│  Reading  │──>│  Reading  │
│  Manual  │   │  Created │   │  Reviewed │   │ Approved  │
│  Upload  │   │ (draft)  │   │(under_    │   │          │
└──────────┘    └──────────┘   │ review)   │   └──────────┘
                               └──────────┘         │
                                                    ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Bill    │<──│  Lines   │<──│ Contract │<──│  _calc_  │
│ Created  │   │ Generated│   │ Template │   │ amounts()│
│ (draft)  │   │ (O2M)    │   │  Lines   │   │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      │
      ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Confirmed│──>│   Sent   │──>│  Posted  │
│          │   │          │   │(invoice) │
└──────────┘    └──────────┘    └──────────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
                    ▼          ▼          ▼
              ┌──────────┐ ┌────────┐ ┌──────────┐
              │ Payment  │ │Penalty │ │Overdue   │
              │ Received │ │Applied │ │Detected  │
              └──────────┘ └────────┘ └──────────┘
```

### 10.2 Prepaid Token Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Customer │──>│  POS     │──>│ Cashier  │
│ Requests │   │ Terminal │   │ Processes│
│ Token    │   │          │   │ Payment  │
└──────────┘    └──────────┘    └──────────┘
                                     │
                    ┌────────────────┤
                    │                │
                    ▼                ▼
              ┌──────────┐    ┌──────────┐
              │ Balance  │    │ Token    │
              │ Deducted │    │ Generated│
              │ (_apply_ │    │ (_gen_   │
              │ balance) │    │ token)   │
              └──────────┘    └──────────┘
                    │                │
                    ▼                ▼
              ┌──────────┐    ┌──────────┐
              │ Balance  │    │ STS API  │
              │ Transaction│  │ Call     │
              │ Logged   │    │ (outbound)│
              └──────────┘    └──────────┘
                                     │
                                     ▼
                               ┌──────────┐
                               │  Token   │
                               │  SMS to  │
                               │ Customer │
                               └──────────┘
```

### 10.3 Payment Reconciliation Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Payment  │──>│ Account  │──>│ Journal  │
│ Received │   │ Payment  │   │ Entry    │
│          │   │ Created  │   │ Created  │
└──────────┘    └──────────┘    └──────────┘
                                     │
                    ┌────────────────┤
                    │                │
                    ▼                ▼
              ┌──────────┐    ┌──────────┐
              │  action_ │    │  Find    │
              │  post()  │    │ Related  │
              │          │    │ Invoice  │
              └──────────┘    └──────────┘
                                     │
                                     ▼
                               ┌──────────┐
                               │  Match   │
                               │  Receiv- │
                               │  able    │
                               │  Lines   │
                               └──────────┘
                                     │
                              ┌──────┤
                              │      │
                              ▼      ▼
                        ┌────────┐ ┌────────┐
                        │Reconcile│ │ Partial│
                        │ (Full)  │ │(Partial)│
                        └────────┘ └────────┘
                              │      │
                              ▼      ▼
                        ┌────────────────┐
                        │  Update Bill   │
                        │  amount_paid   │
                        │  balance_due   │
                        │  bill_state    │
                        └────────────────┘
```

---

## 11. Development Standards

### 11.1 Python Code Standards

| Standard | Requirement |
|----------|------------|
| PEP 8 | Enforced via linter |
| Naming | `snake_case` for functions/variables, `PascalCase` for classes |
| Docstrings | Required for all public methods |
| Type Hints | Recommended for new code |
| Imports | Grouped: stdlib → odoo → local |
| Translation | All user-facing strings wrapped in `_()` |
| Logging | Use `_logger` (never `print()`) |
| Exceptions | `UserError`, `ValidationError`, `AccessError` only |
| Comments | Only for complex business logic |

### 11.2 XML Standards

| Standard | Requirement |
|----------|------------|
| IDs | `<model_name>_<purpose>_<suffix>` pattern |
| View inheritance | Minimal, targeted xpath operations |
| Labels | Arabic (using `string` attribute) |
| Domains | Explicit and documented |
| Context | Used intentionally, not as workaround |

### 11.3 File Organization

```
models/          — One file per model (or small related group)
views/           — Separate files per model's views
security/        — ACL CSV + XML groups/rules
data/            — Sequences, crons, seed data
wizards/         — One file per wizard
controllers/     — API endpoints (one file per domain)
static/description/ — Module icon + README assets
tests/           — Unit tests (mirrors models/ structure)
```

### 11.4 Git Branching Strategy

```
main          — Production-ready code
├── develop   — Integration branch
│   ├── feature/xxx  — Feature branches
│   ├── fix/xxx      — Bug fix branches
│   └── refactor/xxx — Refactor branches
└── release/x.x.x   — Release branches
```

---

## 12. Monitoring & Observability

### 12.1 Logging Strategy

| Log Type | Module | Destination | Retention |
|----------|--------|-------------|-----------|
| Integration API calls | utility_core | `utility.integration.log` | 90 days |
| Notification dispatch | utility_core | `utility.notification.log` | 90 days |
| Meter events | utility_core | `utility.meter.log` | Permanent |
| Migration import | utility_migration | `utility.migration.customer` | Permanent |
| Error logs | All | Odoo log file | 30 days |
| Audit trail | All | `mail.message` (chatter) | Permanent |

### 12.2 Key Health Indicators

| Indicator | Threshold | Alert |
|-----------|-----------|-------|
| Cron job failure | Any failure | Log + notification |
| API response time | > 1s | Performance warning |
| Batch processing queue | > 5000 pending | Capacity alert |
| Failed SMS notifications | > 10/hour | Integration alert |
| Failed payments | > 5/hour | Revenue alert |
| Database connections | > 80% pool | Infrastructure alert |
| Disk usage | > 80% | Infrastructure alert |

### 12.3 Debugging Tools

| Tool | Purpose |
|------|---------|
| Odoo Debug Mode | Developer tools, field inspection, view editing |
| `utility.integration.log` | API call history and responses |
| `utility.meter.log` | Meter event timeline |
| `utility.notification.log` | SMS dispatch history |
| Odoo Shell | Interactive Python for data queries |
| PostgreSQL logs | Slow query analysis |
| Odoo Profiler | Performance profiling |

---

*End of Technical Architecture Document*
