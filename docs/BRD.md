# Utility ERP — Business Requirements Document (BRD)

> **Document Version:** 1.0  
> **Date:** July 2026  
> **Classification:** Internal — Business Analysis  
> **Platform:** Odoo 16.0  
> **Industry:** Electricity Distribution & Retail

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Business Objectives](#2-business-objectives)
3. [Business Processes & Workflows](#3-business-processes--workflows)
4. [Functional Requirements by Domain](#4-functional-requirements-by-domain)
5. [Business Rules & Constraints](#5-business-rules--constraints)
6. [Reports & Analytics](#6-reports--analytics)
7. [User Interface Requirements](#7-user-interface-requirements)
8. [Acceptance Criteria](#8-acceptance-criteria)

---

## 1. Introduction

### 1.1 Purpose

This document defines all business requirements for the Utility ERP system. It describes the business processes, workflows, rules, and functional requirements that the system must support to replace the legacy PEC (Pastoral Energy Company) system.

### 1.2 Business Problem

The legacy system suffers from:
- **Fragmented modules** — customer management, billing, and metering operate in silos
- **Manual processes** — reading collection, bill generation, and payment reconciliation require manual intervention
- **Limited reporting** — no real-time dashboards, transformer balance analysis, or customer statement views
- **No prepaid integration** — STS token vending operates on a separate system
- **No field operations tracking** — service orders, inspections, and tamper cases managed on paper
- **No self-service** — customers cannot view bills or make payments online

### 1.3 Business Goals

| Goal | Metric | Target |
|------|--------|--------|
| Reduce bill generation time | Monthly cycle completion | < 3 days (from 10+) |
| Increase collection rate | Payments / billed amount | > 90% |
| Reduce unbilled consumption | Unbilled readings / total | < 5% |
| Improve customer satisfaction | Portal adoption | > 30% of customers |
| Reduce field operation response time | Average resolution time | < 48 hours |
| Eliminate manual meter reading errors | Reading rejection rate | < 1% |

---

## 2. Business Objectives

### 2.1 Primary Objectives

1. **Unified Customer Management** — Single source of truth for all customer data, contracts, and account histories
2. **Automated Billing** — Formula-driven bill generation with configurable tariffs, block pricing, and fee structures
3. **Prepaid Vending** — STS-compliant token generation and POS-based sales with wallet management
4. **Field Operations** — Digital service orders, inspections, and tamper case management with GPS tracking
5. **Revenue Protection** — Automated penalty calculation, consumption monitoring, and tamper detection
6. **Customer Self-Service** — Portal for bill viewing, payment, and service requests
7. **Real-Time Visibility** — Dashboards for management decision-making

### 2.2 Secondary Objectives

- Legacy data migration with validation and audit trails
- Integration with AMI for automated reading collection
- Payment gateway integration for online payments
- SMS notifications for bills, alerts, and token deliveries
- Inventory management for meter stock and field equipment

---

## 3. Business Processes & Workflows

### 3.1 Customer Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│Registration│──>│ Contract  │──>│   Meter  │──>│ Active   │──>│ Account  │
│           │   │  Signing  │   │Installation│  │ Service  │   │ Closure  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
      │                                              │
      │                                              ▼
      │                                       ┌──────────┐
      │                                       │ Suspended│
      │                                       │(Discon.) │
      │                                       └──────────┘
      │                                              │
      └──────────────────────────────────────────────┘
                    (Reconnection)
```

**BR-CL-001:** Customer registration requires: name, address, region/area, subscriber category/type, contract template, and meter assignment.

**BR-CL-002:** Contract template must be compatible with both the selected subscriber category AND subscriber type.

**BR-CL-003:** Each customer is assigned exactly one meter at a time. Meter replacement creates a new meter record and archives the old one.

**BR-CL-004:** Customer states: `draft → active → suspended → closed`. Reactivation from suspended requires payment of outstanding balance.

**BR-CL-005:** Customer number is auto-generated using a configurable sequence.

**BR-CL-006:** Each customer is linked to a geographic location (region, area) and a distribution cell (transformer).

### 3.2 Meter Reading Workflow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Reading  │──>│  Under   │──>│ Approved │──>│  Billed  │
│  Draft   │   │ Review   │   │          │   │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      │              │
      │              ▼
      │         ┌──────────┐
      └─────────│ Rejected │──> (back to Draft)
                └──────────┘
```

**Input Methods:**
1. **Manual Entry** — Field inspector enters reading via mobile/tablet
2. **Batch Upload** — JSON file uploaded with multiple readings (offset-based batch processing)
3. **AMI Callback** — Automated reading from AMI system via REST webhook

**BR-MR-001:** Readings are classified by type: `subscriber`, `cell`, `feeder`, `transformer` (reading_category).

**BR-MR-002:** Reading state machine: `draft → under_review → approved → billed`. Rejection returns to `draft`.

**BR-MR-003:** Consumption is auto-calculated: `consumption = current_reading - previous_reading`.

**BR-MR-004:** Consumption alerts trigger when consumption exceeds configurable thresholds.

**BR-MR-005:** Post-billed readings can only be corrected via `utility.reading.settlement` (not direct editing).

**BR-MR-006:** Batch processing uses configurable batch size (`reading_upload_batch_size`) with offset-based pagination.

**BR-MR-007:** Image attachments from batch uploads are automatically matched to readings by meter number.

### 3.3 Prepaid Token Workflow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Customer │──>│   POS    │──>│  Token   │──>│  Token   │
│ Request  │   │   Sale   │   │Generation│   │ Delivered│
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                       │
                                       ▼
                                ┌──────────┐
                                │  Meter   │
                                │  Loaded  │
                                └──────────┘
```

**BR-PT-001:** Token generation is triggered automatically when a POS order is completed (paid).

**BR-PT-002:** Each token is a 20-digit numeric STS code with status tracking (`draft → active → used → expired → blocked`).

**BR-PT-003:** Idempotent token generation — system checks for existing successful tokens before re-generating.

**BR-PT-004:** Token amounts are deducted from customer's prepaid balance via `utility.customer.balance.transaction`.

**BR-PT-005:** Emergency credit is available when main balance is depleted (configurable limit per customer).

**BR-PT-006:** Transaction reversals require approval workflow: `draft → approved → completed`.

**BR-PT-007:** Cashier shifts enforce single-open-shift-per-user constraint via `@api.constrains`.

### 3.4 Postpaid Billing Workflow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Reading  │──>│  Bill    │──>│   Bill   │──>│  Bill    │──>│ Payment  │
│ Approved │   │Generated │   │  Sent    │   │  Paid    │   │Recorded  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
      │              │               │               │
      │              │               │               ▼
      │              │               │         ┌──────────┐
      │              │               │         │ Overdue  │
      │              │               │         └──────────┘
      │              │               │               │
      │              │               │               ▼
      │              │               │         ┌──────────┐
      │              │               │         │Penalty / │
      │              │               │         │Disconnect│
      │              │               │         └──────────┘
      │              ▼               │
      │         ┌──────────┐        │
      └─────────│Cancelled │        │
                └──────────┘        │
                                    ▼
                              ┌──────────┐
                              │ Write-off │
                              └──────────┘
```

**BR-PB-001:** Bills are generated from approved readings via `_calculate_amounts()` which dynamically creates `sale.order.line` records from the contract template.

**BR-PB-002:** Bill lifecycle (`bill_state`): `draft → confirmed → sent → paid → overdue → cancelled`. This is a computed field, not manually editable.

**BR-PB-003:** `_calculate_amounts()` supports:
- Consumption-based charges (per kWh)
- Block pricing (from/to kWh ranges with different prices)
- Tier pricing (progressive rates)
- Fixed fees (monthly, quarterly, annually)
- Service charges
- Local fees: العامل (mu_allim), النظافة (cleaning), البلدية (municipality)
- Subsidized subscriber discounts with block details
- Minimum charge enforcement
- Maximum charge cap

**BR-PB-004:** Penalty calculation is automated via `cron_calculate_late_penalties()`:
- Searches for overdue bills (posted + past due date + unpaid)
- Creates `utility.penalty` records
- Generates separate `account.move` invoices for penalties
- Enforces maximum penalty cap (default: 30% of bill amount)

**BR-PB-005:** Automatic disconnection order creation for severely overdue accounts via `cron_create_disconnection_orders()`.

**BR-PB-006:** Due bill reminders sent via `cron_send_due_reminders()`.

**BR-PB-007:** Bill protection — confirmed/sent bills cannot have financial/technical fields edited (`BILL_PROTECTED_FIELDS`).

**BR-PB-008:** Payment reconciliation is automatic — `account.payment.action_post()` reconciles utility payment journal entries with posted invoices.

**BR-PB-009:** Recurring invoices generated hourly via `cron_generate_recurring_invoices()` based on contract template schedule.

**BR-PB-010:** Installment plans allow spreading a bill's remaining balance across configurable periods.

### 3.5 Service Order Workflow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   Draft  │──>│Assigned  │──>│In Progress│──>│Completed │──>│ Approved │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
      │              │               │               │
      ▼              ▼               ▼               ▼
┌──────────┐  ┌──────────┐    ┌──────────┐    ┌──────────┐
│Cancelled │  │  On Hold │    │  Rejected│    │  Failed  │
└──────────┘  └──────────┘    └──────────┘    └──────────┘
```

**Service Types:**
1. New Connection (اتصال جديد)
2. Disconnection (فصل)
3. Reconnection (اعادة التوصيل)
4. Meter Replacement (استبدال العدّاد)
5. Meter Inspection (فحص العدّاد)
6. Tamper Investigation (تحقيق تلاعب)
7. Complaint Resolution (شكوى)
8. Emergency Repair (اصلاح طارئ)
9. Maintenance (صيانة)
10. Reading (قراءة)
11. Other (اخرى)

**BR-SO-001:** State machine enforced via `_check_state_transition()` — only valid transitions allowed.

**BR-SO-002:** Completing a meter replacement order automatically:
- Creates old meter final reading
- Creates new meter initial reading
- Updates customer's meter assignment
- Logs both events to meter history

**BR-SO-003:** All service orders log creation/completion events to `utility.meter.log`.

### 3.6 Tamper Case Workflow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Reported │──>│Investigating│>│  Proven  │──>│  Legal   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      │              │               │
      │              ▼               ▼
      │         ┌──────────┐   ┌──────────┐
      └─────────│Dismissed │   │ Settled  │
                └──────────┘   └──────────┘
```

**Tamper Types:**
1. Meter Bypass (تجاوز العدّاد)
2. Meter Tampering (تلاعب بالعدّاد)
3. Connection Tampering (تلاعب بالاتصال)
4. Seal Broken (خلع الختم)
5. Wiring Fraud (تلاعب بالأسلاك)
6. Other (اخرى)

**Severity Levels:** low, medium, high, critical

### 3.7 Alarm Monitoring

**BR-AM-001:** 13 alarm types monitored:
- Low credit balance
- Tamper detected
- Communication failure
- Meter failure
- Over-voltage
- Under-voltage
- Over-current
- Power failure
- Reverse energy
- Demand exceedance
- Frequency deviation
- Meter disconnect
- Other

**BR-AM-002:** `cron_check_low_credit()` runs every 30 minutes to check prepaid customer balances.

**BR-AM-003:** Alarms can auto-create service orders via `action_create_service_order()`.

### 3.8 Inventory Management Workflow (Standard Odoo Stock)

```text
┌──────────┐       ┌──────────┐       ┌──────────┐
│ Supplier │ ────> │  Stock   │ ────> │ Customer │
│ Location │ (In)  │ Location │ (Out) │ Location │
└──────────┘       └──────────┘       └──────────┘
                         │
                         ▼
                   ┌──────────┐
                   │  Scrap   │
                   │ Location │
                   └──────────┘
```

**BR-INV-001:** Inventory tracking relies entirely on the standard Odoo `stock` module (picking, moves, locations).

**BR-INV-002:** Meter models are defined as `product.product`. Meter serials are tracked via `stock.lot`.

**BR-INV-003:** Field Operations (Service Orders and Replacements) automatically generate and validate `stock.picking` records to maintain accurate physical stock.

---

## 4. Functional Requirements by Domain

### 4.1 Customer Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CM-001 | Register new customers with full profile | Must Have | Done |
| CM-002 | Assign contract template based on category/type/location | Must Have | Done |
| CM-003 | Auto-generate customer numbers via sequence | Must Have | Done |
| CM-004 | Manage customer wallet (prepaid balance) | Must Have | Done |
| CM-005 | Emergency credit allocation | Should Have | Done |
| CM-006 | Customer balance transaction ledger | Must Have | Done |
| CM-007 | Low credit alerts via SMS | Should Have | Done |
| CM-008 | Customer creation wizard for guided setup | Could Have | Done |
| CM-009 | Link customer to geographic hierarchy (region, area) | Must Have | Done |
| CM-010 | Link customer to distribution cell/transformer | Must Have | Done |
| CM-011 | Track customer contract state separately from bill state | Must Have | Done |
| CM-012 | Subscriber category + type mandatory on customer | Must Have | Done |

### 4.2 Metering

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| MT-001 | Meter catalog (type, model, status) | Must Have | Done |
| MT-002 | QR code generation for each meter | Could Have | Done |
| MT-003 | Meter installation tracking | Must Have | Done |
| MT-004 | Meter event logging (install, remove, tamper, etc.) | Must Have | Done |
| MT-005 | Meter replacement workflow (old → new) | Must Have | Done |
| MT-006 | AMI reading integration | Should Have | Done |
| MT-007 | Meter link to transformer/cell | Must Have | Done |
| MT-008 | Meter serialization via inventory module | Should Have | Done |

### 4.3 Reading Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| RD-001 | Manual reading entry with validation | Must Have | Done |
| RD-002 | Batch JSON file upload | Must Have | Done |
| RD-003 | AMI callback endpoint | Should Have | Done |
| RD-004 | Reading review/approval workflow | Must Have | Done |
| RD-005 | Reading classification (subscriber, cell, transformer) | Must Have | Done |
| RD-006 | Consumption auto-calculation | Must Have | Done |
| RD-007 | Consumption anomaly alerts | Should Have | Done |
| RD-008 | Post-billed reading correction via settlement | Must Have | Done |
| RD-009 | Batch processing with configurable batch size | Must Have | Done |
| RD-010 | Automatic image attachment matching | Could Have | Done |
| RD-011 | Reject reading (return to draft) | Must Have | Done |
| RD-012 | Restrict edits on billed readings | Must Have | Done |

### 4.4 Prepaid Vending

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PV-001 | STS token generation (20-digit) | Must Have | Done |
| PV-002 | POS-based token sales | Must Have | Done |
| PV-003 | Cashier shift management | Must Have | Done |
| PV-004 | Transaction ledger (wallet) | Must Have | Done |
| PV-005 | Balance adjustments (credit/debit/emergency) | Must Have | Done |
| PV-006 | Transaction reversals with approval | Must Have | Done |
| PV-007 | Token status tracking | Must Have | Done |
| PV-008 | Single-open-shift constraint | Should Have | Done |
| PV-009 | Idempotent token generation | Should Have | Done |
| PV-010 | Emergency credit with limits | Should Have | Done |

### 4.5 Postpaid Billing

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PB-001 | Dynamic formula-based bill calculation | Must Have | Done |
| PB-002 | Block/tier pricing support | Must Have | Done |
| PB-003 | Billing cycle management | Must Have | Done |
| PB-004 | Automated bill generation from readings | Must Have | Done |
| PB-005 | Late payment penalty calculation | Must Have | Done |
| PB-006 | Penalty cap (max percentage) | Should Have | Done |
| PB-007 | Debt write-off with credit note | Must Have | Done |
| PB-008 | Customer deposit management | Should Have | Done |
| PB-009 | Installment payment plans | Should Have | Done |
| PB-010 | Bill state lifecycle (computed) | Must Have | Done |
| PB-011 | Bill field protection on confirmation | Must Have | Done |
| PB-012 | Automatic payment reconciliation | Must Have | Done |
| PB-013 | Recurring invoice generation | Should Have | Done |
| PB-014 | Automatic disconnection order creation | Should Have | Done |
| PB-015 | Due bill reminders (SMS) | Should Have | Done |
| PB-016 | Overdue order auto-update | Must Have | Done |
| PB-017 | Financial settlements (credit/debit) | Should Have | Done |
| PB-018 | Automated workflow engine | Could Have | Done |

### 4.6 Field Operations

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FO-001 | Service order management (11 types) | Must Have | Done |
| FO-002 | State machine with transition validation | Must Have | Done |
| FO-003 | Meter inspection with 6 inspection types | Must Have | Done |
| FO-004 | Tamper case management with evidence | Must Have | Done |
| FO-005 | 13 alarm types with monitoring | Should Have | Done |
| FO-006 | Auto-create service orders from alarms | Could Have | Done |
| FO-007 | Work orders with GPS check-in/out | Should Have | Done |
| FO-008 | Work order parts and labor tracking | Should Have | Done |
| FO-009 | Inspector signature capture | Could Have | Done |
| FO-010 | Reading settlement (post-bill correction) | Must Have | Done |

### 4.7 Inventory Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| IM-001 | Hierarchical storage locations (warehouse → room → shelf) | Should Have | Done |
| IM-002 | Stock item tracking with meter serial linkage | Should Have | Done |
| IM-003 | Stock movements (in/out/adjustment) | Should Have | Done |
| IM-004 | Physical count with variance analysis | Could Have | Done |

### 4.8 Customer Portal & API

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CP-001 | Customer self-service portal | Should Have | Done |
| CP-002 | Account balance and bill history API | Must Have | Done |
| CP-003 | Online payment initiation | Must Have | Done |
| CP-004 | Payment gateway webhook processing | Must Have | Done |
| CP-005 | Service request submission via API | Should Have | Done |
| CP-006 | Daily report endpoint | Could Have | Done |
| CP-007 | API token-based authentication | Must Have | Done |
| CP-008 | Partner ownership validation on all endpoints | Must Have | Done |

### 4.9 Notifications

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NT-001 | SMS notification dispatch | Must Have | Done |
| NT-002 | Portal notification (in-app) | Should Have | Done |
| NT-003 | Cron-based dispatch (10-minute intervals) | Must Have | Done |
| NT-004 | Notification audit log | Must Have | Done |
| NT-005 | External provider integration (HTTP) | Must Have | Done |
| NT-006 | NO email notifications (architecture decision) | Must Have | Done |

### 4.10 Migration

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| MG-001 | Legacy data staging table | Must Have | Done |
| MG-002 | Code mapping (region, area, category, subscriber, contract) | Must Have | Done |
| MG-003 | Excel import wizard | Should Have | Done |
| MG-004 | Create Odoo records from staged data | Must Have | Done |
| MG-005 | Opening balance generation | Must Have | Done |

---

## 5. Business Rules & Constraints

### 5.1 Customer Rules

| Rule | Description |
|------|-------------|
| BR-C01 | Customer number is unique and auto-generated |
| BR-C02 | Subscriber category and type are mandatory |
| BR-C03 | Selected subscriber type must belong to the selected category |
| BR-C04 | Contract template must be compatible with both category AND type |
| BR-C05 | Contract template must match the customer's geographic location |
| BR-C06 | Each customer links to exactly one active meter |
| BR-C07 | Customer cannot be closed with outstanding balance |

### 5.2 Billing Rules

| Rule | Description |
|------|-------------|
| BR-B01 | Bills are only generated from approved readings |
| BR-B02 | Bill amount is computed, not manually entered |
| BR-B03 | Confirmed/sent bills cannot have financial fields edited |
| BR-B04 | Bill state is computed from payment status and overdue flag |
| BR-B05 | Maximum charge cap enforced per contract template |
| BR-B06 | Minimum charge floor enforced per contract template |
| BR-B07 | Subsidized discounts applied per subscriber category |
| BR-B08 | Block pricing calculated from contract template blocks |
| BR-B09 | Penalties capped at configurable maximum percentage |
| BR-B10 | Penalty generates separate accounting invoice |
| BR-B11 | Write-off creates credit note and reconciles |

### 5.3 Meter Reading Rules

| Rule | Description |
|------|-------------|
| BR-R01 | Previous reading must be less than current reading |
| BR-R02 | Cannot edit a billed reading (use settlement instead) |
| BR-R03 | Reading classification determines which entity is being read |
| BR-R04 | Batch upload processes in configurable batch sizes |
| BR-R05 | Rejected readings return to draft state |
| BR-R06 | Post-bill corrections use settlement model with audit trail |

### 5.4 Prepaid Rules

| Rule | Description |
|------|-------------|
| BR-P01 | Token generation is idempotent (no duplicates) |
| BR-P02 | Emergency credit cannot exceed configured limit |
| BR-P03 | Reversals require approval workflow |
| BR-P04 | Only one open cashier shift per user at a time |
| BR-P05 | Token status tracked through full lifecycle |
| BR-P06 | POS order completion triggers token generation |

### 5.5 Security Rules

| Rule | Description |
|------|-------------|
| BR-S01 | All API endpoints validate partner ownership |
| BR-S02 | Formula execution sandboxed (no ORM access) |
| BR-S03 | All operations audited via chatter/logging |
| BR-S04 | Multi-company record isolation enforced |
| BR-S05 | No email-based notifications (SMS + portal only) |

### 5.6 Geographic Rules

| Rule | Description |
|------|-------------|
| BR-G01 | Dual-pathway hierarchy converging at Route: Commercial (`Region→Area→Zone→Route`), Network (`Substation→Feeder→Transformer→Route`) |
| BR-G02 | Parent-child relationships via `parent_id` field |
| BR-G03 | Customers linked to area and transformer/cell |
| BR-G04 | Transformers can be cells (is_cell=True) with child transformers |

---

## 6. Reports & Analytics

### 6.1 Standard Reports

| Report | Module | Description | Filters |
|--------|--------|-------------|---------|
| Customer Statement | billing | Full customer account statement | Date range, customer |
| Transformer Balance | billing | Balance summary by transformer | Date, transformer |
| Daily Summary | billing | Daily collections and bills | Date |
| Monthly Summary | billing | Monthly revenue by category | Month, category |
| Outstanding Balances | billing | All unpaid bills | Date, customer, area |
| Consumption Analysis | core | Consumption trends by area/feeder | Date, geography |
| Reading Reconciliation | core | Reading accuracy and coverage | Date, batch |
| Meter Status Report | core | Meter inventory and status | Status, location |
| Tamper Cases | operations | Open and resolved cases | Date, severity |
| Service Order Summary | operations | Orders by type and status | Date, type, status |
| Inventory Stock Levels | inventory | Current stock by location | Location, product |
| Penalty Summary | billing | Penalties by period | Date, customer |

### 6.2 Dashboard KPIs

| KPI | Source | Visualization |
|-----|--------|---------------|
| Today's Collections | account.payment | Number card |
| Monthly Revenue | sale.order | Number card |
| Pending Bills | sale.order (bill_state=sent) | Number card |
| Overdue Bills | sale.order (is_overdue=True) | Number card |
| Active Customers | utility.customer | Number card |
| Bills by Status | sale.order | Pie chart |
| Revenue by Month | sale.order | Line chart |
| Collections vs Billed | sale.order | Bar chart |
| Top Outstanding Customers | sale.order | Top list |
| Service Orders Open | utility.service.order | Kanban |

---

## 7. User Interface Requirements

### 7.1 Language

All UI labels, menu names, field strings, model descriptions, and view content are in **Arabic** (using `translate=True` on model fields).

### 7.2 UI Principles

- Minimal clicks for daily operations (target: < 5 clicks for common tasks)
- Clear workflow indicators (statusbar, badges, decorations)
- Smart buttons for drill-down navigation
- Search views with pre-defined filters and group-by options
- Kanban views for operational tracking
- Tree views with proper column ordering and monetary widgets

### 7.3 Key Views

| View | Type | Key Features |
|------|------|-------------|
| Customer Form | Form | Smart buttons (meter, bills, readings, balance), statusbar, notebook tabs |
| Customer List | Tree | Customer number, name, area, status, balance |
| Bill Form | Form | Amount breakdown, payment history, penalty tracker, settlement link |
| Bill List | Tree | Decorations by state, monetary columns, overdue highlighting |
| Reading Form | Form | Previous/current reading, consumption, approval workflow |
| Token List | Tree | Token number, status badge, amount, meter reference |
| Service Order | Form/Kanban | State machine, type selector, GPS, work orders |
| Dashboard | Dashboard | KPI cards, charts, pending action lists |

### 7.4 Navigation Structure

```
الرئيسية (Home)
├── الفواتير (Billing)
│   ├── الفواتير (Bills)
│   ├── دورات الفوترة (Billing Cycles)
│   ├── دفعات القراءة (Reading Batches)
│   ├── العقوبات (Penalties)
│   ├── الشطب (Write-offs)
│   ├── الودائع (Deposits)
│   ├── خطط التقسيط (Installment Plans)
│   └── التسويات المالية (Financial Settlements)
├── الشحن المسبق (Prepaid)
│   ├── الرموز (Tokens)
│   ├── المعاملات (Transactions)
│   ├── الإلغاءات (Reversals)
│   ├── التعديلات (Adjustments)
│   └── ورديات الصندوق (Cashier Shifts)
├── العمليات الميدانية (Field Operations)
│   ├── أوامر الخدمة (Service Orders)
│   ├── الفحوصات (Inspections)
│   ├── قضايا التلاعب (Tamper Cases)
│   ├── الإنذارات (Alarms)
│   └── أوامر العمل (Work Orders)
├── البيانات الرئيسية (Master Data)
│   ├── المشتركين (Customers)
│   ├── العدّادات (Meters)
│   ├── القراءات (Readings)
│   ├── العقود (Contracts)
│   ├── التعريفات (Tariffs)
│   ├── المناطق (Regions)
│   ├── المخازن (Storage Locations)
│   └── الموظفين (Staff/Teams)
├── التقارير (Reports)
├── الإعدادات (Configuration)
└── الهجرة (Migration)
```

---

## 8. Acceptance Criteria

### 8.1 General Criteria

- All user stories for each functional requirement are demonstrable
- All business rules are enforced with appropriate error messages
- Arabic UI is complete and consistent across all views
- All cron jobs execute without errors
- All API endpoints return proper JSON responses
- Security groups restrict access as defined
- Multi-company isolation is verified

### 8.2 Performance Criteria

- Single bill generation completes in < 2 seconds
- Batch generation of 1000 bills completes in < 5 minutes
- Reading batch upload of 1000 readings completes in < 3 minutes
- Token generation completes in < 5 seconds
- API response time < 500ms (95th percentile)
- No N+1 query issues in critical paths

### 8.3 Data Integrity Criteria

- All financial amounts reconcile (bills = sum of lines, payments = sum of allocations)
- Meter readings are monotonically increasing per meter
- Customer wallet transactions balance (recharges - consumption = balance)
- All journal entries have balanced debits/credits
- No orphaned records (customer without partner, bill without customer, etc.)

---

*End of Business Requirements Document*
