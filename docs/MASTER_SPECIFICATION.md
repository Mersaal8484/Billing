# Utility ERP — Master Specification

> **Document Version:** 1.0  
> **Date:** July 2026  
> **Classification:** Internal — Engineering  
> **Platform:** Odoo 16.0 Community/Enterprise  
> **Industry:** Electricity Distribution & Retail (Utility)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Scope](#2-project-scope)
3. [Business Context](#3-business-context)
4. [Stakeholders](#4-stakeholders)
5. [Glossary & Terminology](#5-glossary--terminology)
6. [Module Architecture Overview](#6-module-architecture-overview)
7. [Module Dependency Map](#7-module-dependency-map)
8. [Data Domain Summary](#8-data-domain-summary)
9. [Integration Landscape](#9-integration-landscape)
10. [Non-Functional Requirements Summary](#10-non-functional-requirements-summary)
11. [Regulatory & Compliance](#11-regulatory--compliance)
12. [Deployment Model](#12-deployment-model)
13. [Open Items & Assumptions](#13-open-items--assumptions)

---

## 1. Executive Summary

**Utility ERP** is a comprehensive, purpose-built Enterprise Resource Planning system for **electricity distribution companies**, developed on the **Odoo 16.0** platform. It replaces the legacy PEC (Pastoral Energy Company) system with a modern, integrated solution covering the full utility lifecycle:

- **Customer Management** — subscriber registration, contracts, categories, and account lifecycle
- **Metering** — meter installation, tracking, readings (manual, batch upload, AMI), and replacement
- **Prepaid Vending** — STS token generation, POS-based sales, cashier shifts, and wallet management
- **Postpaid Billing** — dynamic formula-based billing, cycles, invoices, penalties, and collections
- **Field Operations** — service orders, inspections, tamper detection, installation, and work orders
- **Inventory & Warehouse** — standard Odoo stock integration, seamless field operations picking generation, meter serialization tracking
- **Customer Portal & API** — self-service portal, REST API for third-party integrations, payment gateways
- **Legacy Migration** — staged data import with mapping tables and validation

The system serves **10 security roles** from field technicians to revenue managers, supports **Arabic-first UI**, and handles dual-pathway hierarchies converging at the Route level:
- **Commercial/Sales (Geographic):** `Region → Area → Zone → Route`
- **Distribution (Network):** `Substation → Feeder → Transformer → Route`

---

## 2. Project Scope

### 2.1 In Scope

| Domain | Capabilities |
|--------|-------------|
| **Customer Management** | Customer registration, contracts, subscriber categories/types, balance management, credit control |
| **Metering** | Meter catalog (type/model/status), installation tracking, meter logs, QR codes, AMI integration, meter replacement workflow |
| **Hierarchies** | Dual pathways converging at Route: Commercial (`Region→Area→Zone→Route`) and Distribution (`Substation→Feeder→Transformer→Route`) |
| **Prepaid Vending** | STS token generation, POS sales, cashier shifts, wallet ledger (recharge/consumption/adjustment), emergency credit, reversals |
| **Postpaid Billing** | Dynamic billing formulas, consumption block/tier pricing, billing cycles, automated bill generation, penalties, write-offs, deposits, installment plans |
| **Collections** | Payment collection via POS, field collectors, bank transfer; automatic reconciliation |
| **Field Operations** | Service orders (11 types), meter inspection, tamper cases, alarm monitoring, installation orders, work orders with GPS tracking |
| **Reading Management** | Manual entry, batch JSON upload, AMI callbacks, reading review/approval, settlement corrections |
| **Inventory** | Standard Odoo stock module integration, automated picking creation, meter tracking via products and lots |
| **Notifications** | SMS dispatch via external providers, portal notifications, internal notifications |
| **Accounting Integration** | Journal entries, invoice generation, payment reconciliation, credit notes, write-offs |
| **Portal & API** | Customer self-service portal, 7 REST API endpoints, payment gateway integration |
| **Migration** | Legacy data staging, code mapping, Excel import, opening balance generation |
| **Automation** | 13+ cron jobs, automated workflow engine, batch processing |

### 2.2 Out of Scope

- SCADA / real-time grid monitoring (AMI only for reading callbacks)
- Revenue assurance / loss reduction analytics (future phase)
- HR / payroll modules
- Procurement / tendering
- GIS mapping / asset geo-location (GPS available on work orders only)
- Multi-currency (single currency per company)
- Multi-entity consolidation

### 2.3 Project Boundaries

```
┌──────────────────────────────────────────────────────────────────┐
│                        UTILITY ERP                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ utility  │  │ utility  │  │ utility  │  │ utility  │        │
│  │  _core   │→ │_inventory│→ │_prepaid  │→ │operations│        │
│  └────┬─────┘  └──────────┘  └────┬─────┘  └──────────┘        │
│       │                           │                             │
│       ↓                           ↓                             │
│  ┌──────────┐               ┌──────────┐                        │
│  │ utility  │               │ utility  │                        │
│  │ _billing │←──────────────│_portal   │                        │
│  └──────────┘               └──────────┘                        │
│       │                                                           │
│       ↓                                                           │
│  ┌──────────┐                                                    │
│  │ utility  │                                                    │
│  │_migration│                                                    │
│  └──────────┘                                                    │
└──────────────────────────────────────────────────────────────────┘
         ↕                    ↕                    ↕
    ┌─────────┐         ┌──────────┐         ┌──────────┐
    │  STS    │         │ Payment  │         │   SMS    │
    │ Token   │         │ Gateway  │         │ Provider │
    │ Server  │         │          │         │          │
    └─────────┘         └──────────┘         └──────────┘
```

---

## 3. Business Context

### 3.1 Industry Background

Electricity distribution companies operate in a highly regulated environment requiring:

- **Mass metering** — thousands to millions of customer meters requiring regular reading
- **Dual revenue models** — prepaid (token-based) and postpaid (invoice-based) customers
- **Complex tariff structures** — block pricing, tiered rates, subsidized categories, seasonal variations
- **Geographic dispersion** — operations spread across regions, areas, substations, and individual routes
- **Regulatory compliance** — energy authority reporting, consumer protection, tariff approval
- **Revenue protection** — tamper detection, consumption anomalies, loss accounting

### 3.2 Business Model

```
┌─────────────────────────────────────────────────────────┐
│                    REVENUE STREAMS                       │
├─────────────────────┬───────────────────────────────────┤
│  Prepaid Revenue    │  Postpaid Revenue                 │
│  • Token sales (POS)│  • Monthly bills                  │
│  • Emergency credit │  • Service charges                │
│  • Reconnections    │  • Penalty fees                   │
│                     │  • Connection/disconnection fees  │
├─────────────────────┴───────────────────────────────────┤
│                    COST CENTERS                          │
├─────────────────────┬───────────────────────────────────┤
│  Field Operations   │  Asset Management                 │
│  • Installations    │  • Meter lifecycle                 │
│  • Inspections      │  • Transformer maintenance        │
│  • Tamper cases     │  • Feeder monitoring              │
│  • Work orders      │  • Inventory management           │
└─────────────────────┴───────────────────────────────────┘
```

### 3.3 Subscriber Categories

| Category (فئات المشتركين) | Description | Billing Method |
|---------------------------|-------------|----------------|
| Residential (سكني) | Household customers | Postpaid or Prepaid |
| Commercial (تجاري) | Business customers | Postpaid |
| Industrial (صناعي) | Industrial facilities | Postpaid |
| Government (حكومي) | Government entities | Postpaid |
| Agricultural (زراعي) | Agricultural operations | Postpaid |
| Special (خاص) | Special agreements | Custom |

---

## 4. Stakeholders

### 4.1 User Roles (Security Groups)

| Role (Arabic) | Role (English) | Implies | Access Level |
|---------------|----------------|---------|--------------|
| م体量 فقط | Read-only | — | Read-only access to all modules |
| أمين صندوق | Cashier | Read-only | POS sales, token generation, payment collection |
| cobuctor | Collector | Read-only | Field collection, payment recording |
| فني | Technician | Read-only | Service orders, inspections, meter work |
| مفتتش | Field Inspector | Technician | Inspection oversight, approval |
| مشرف | Supervisor | Cashier + Collector + Technician | Order approval, shift management |
| مدير الفوترة | Billing Manager | Supervisor | Bill generation, batch processing, write-offs |
| مدير الإيرادات | Revenue Manager | Billing Manager | Financial reports, settlement, penalties |
| مراجع | Auditor | Read-only | Audit trail, log review, compliance |
| مدير النظام | Admin | Revenue Manager + Auditor + Field Inspector | Full system access, configuration |

### 4.2 External Actors

| Actor | Interface | Purpose |
|-------|-----------|---------|
| STS Token Server | HTTP API | Token generation/validation |
| Payment Gateway | REST API + Webhook | Online payment processing |
| SMS Provider | HTTP API | Customer notifications |
| AMI System | REST API | Automated meter reading |
| POS Terminal | Odoo POS | In-store prepaid sales |

---

## 5. Glossary & Terminology

| Term | Arabic | Definition |
|------|--------|------------|
| **STS** | رمز ر务务务 | Standard Transfer Specification — international protocol for prepaid electricity tokens |
| **AMI** | قراءة ذكية | Advanced Metering Infrastructure — automated meter reading system |
| **NUTS** | التقسيم الجغرافي | Nomenclature of Territorial Units — hierarchical geographic classification |
| **Token** | رمز شحن | 20-digit numeric code entered into prepaid meters to load credit |
| **Reading** | قراءة العدّاد | Meter consumption reading (kWh) at a point in time |
| **Bill** | فاتورة | Postpaid invoice generated from meter readings and tariff calculations |
| **Tariff** |تعريفة | Price schedule for electricity consumption (per kWh, block/tier pricing) |
| **Formula** | صيغة حسابية | Dynamic Python formula for bill calculation using `safe_eval()` |
| **Contract Template** | نموذج العقد | Defines billing rules, lines, and fee structure for a subscriber category |
| **Subscriber Category** | فئة المشترك | Main classification of customers (residential, commercial, etc.) |
| **Subscriber Type** | نوع المشترك | Sub-classification within a category (e.g., villa, apartment) |
| **Cell** | خلية | Distribution cell — group of transformers serving a geographic zone |
| **Feeder** | خط تغذية | High-voltage line from substation to transformers |
| **Substation** | محطة فرعية | Transformer station stepping down voltage |
| **Route** | خط مسرب | Physical meter reading route/area |
| **Wallet** | المحفظة | Customer prepaid balance ledger |
| **Emergency Credit** | رصيد طارئ | Emergency balance available when main balance is depleted |
| **Tamper** | تلاعب | Unauthorized meter interference or bypass |
| **Write-off** | شطب | Cancellation of uncollectible debt |
| **Settlement** | تسوية | Financial adjustment to correct billing errors |
| **Installment Plan** | خطة التقسيط | Payment plan spreading a bill across multiple periods |
| **Cashier Shift** | وردية أمين الصندوق | POS cashier work session with opening/closing balances |
| **Collector Shift** | وردية cobuctor | Field collection work session |
| **Bill State** | حالة الفاتورة | Computed lifecycle state: draft → confirmed → sent → paid → overdue → cancelled |
| **Balance Due** | المبلغ المستحق | Outstanding amount owed by customer |
| **Previous Balance** | الرصيد السابق | Carried-forward balance from prior billing period |

---

## 6. Module Architecture Overview

### 6.1 Module Summary

| # | Module | Models | Purpose | Lines (est.) |
|---|--------|--------|---------|-------------|
| 1 | `utility_core` | 32+ | Master data, customers, meters, readings, regions, tariffs, formulas, contracts, notifications, settings | ~5,000 |
| 2 | `utility_inventory` | 5 | Storage locations, items, movements, physical counts | ~800 |
| 3 | `utility_prepaid` | 6 | POS integration, STS tokens, transactions, reversals, cashier shifts | ~1,200 |
| 4 | `utility_operations` | 8 | Service orders, inspections, tamper cases, alarms, work orders, meter replacement, settlements | ~2,000 |
| 5 | `utility_billing` | 16 | Sale order billing, batch processing, cycles, penalties, write-offs, deposits, installments, workflow automation | ~4,000 |
| 6 | `utility_portal` | 1 + 7 endpoints | Customer portal, REST API, payment gateway | ~1,500 |
| 7 | `utility_migration` | 3 + 1 wizard | Legacy data import, staging, mapping | ~600 |

### 6.2 Core Models by Domain

#### Geographic Hierarchy (utility_core)
```
utility.region (type=region)
  └── utility.region (type=area)
        └── utility.region (type=zone)
              └── utility.region (type=office)
                    └── utility.region (type=substation)
                          └── utility.region (type=feeder)
                                └── utility.region (type=transformer)
                                      └── utility.region (type=route)

utility.office        — Office with staff and phone
utility.substation    — Substation linked to office
utility.feeder        — Feeder linked to substation
utility.transformer   — Transformer with cell/parent hierarchy
utility.route         — Reading route with assigned transformers
```

#### Customer Domain (utility_core)
```
utility.subscriber.category  — Subscriber category (residential, commercial...)
utility.subscriber           — Subscriber type (belongs to category)
utility.customer             — Customer account (linked to res.partner)
utility.customer.wizard      — Customer creation wizard
utility.customer.balance.transaction — Wallet ledger
utility.connection           — Connection record
utility.connection.type      — Connection type catalog
```

#### Metering Domain (utility_core + utility_operations + utility_inventory)
```
utility.meter              — Meter device (linked to customer, transformer)
utility.meter.type         — Meter type catalog
utility.meter.model        — Meter model catalog
utility.meter.status       — Meter status catalog
utility.meter.log          — Meter event log
utility.meter.replacement  — Meter replacement workflow
utility.reading            — Unified reading model (customer/cell/transformer)
utility.reading.batch      — JSON file batch upload processor
utility.reading.settlement — Post-billed reading correction
```

#### Billing Domain (utility_billing)
```
sale.order (inherited)           — Main billing document (bill_state, amounts, calculations)
sale.order.line (inherited)      — Bill line items (meter_line_type, sponsor, contract)
account.move (inherited)         — Accounting journal entry with utility fields
account.payment (inherited)      — Payment with utility reconciliation
utility.reading.batch            — Reading batch upload
utility.billing.cycle            — Billing cycle management
utility.recurring.invoice        — Recurring invoice generation
utility.penalty                  — Late payment penalty
utility.penalty.type             — Penalty type catalog
utility.writeoff                 — Debt write-off with credit note
utility.deposit                  — Customer deposit management
utility.financial.settlement     — Credit/debit financial adjustments
utility.installment.plan         — Installment payment plans
utility.installment.plan.line    — Individual installment lines
utility.cashier.shift (extended) — POS cashier shifts with bill collections
utility.collector.shift          — Field collector shifts
sale.workflow.process            — Automated workflow configuration
automatic.workflow.job           — Workflow job runner
```

#### Operations Domain (utility_operations)
```
utility.service.order      — 11 service types with state machine
utility.installation       — Installation orders
utility.inspection         — 6 inspection types with signatures
utility.tamper.case        — 6 tamper types with evidence
utility.alarm              — 13 alarm types with auto-service-order
utility.work.order         — GPS-tracked work orders with parts/labor
```

#### Prepaid Domain (utility_prepaid)
```
pos.order (inherited)      — POS sale with utility fields and token generation
utility.token              — STS token (20-digit, status tracking)
utility.transaction        — Wallet transaction ledger
utility.reversal           — Transaction reversal workflow
utility.adjustment         — Balance adjustment (credit/debit/emergency)
utility.cashier.shift      — POS cashier shift management
```

#### Integration Domain (utility_core + utility_portal)
```
utility.integration.provider — External provider config (SMS, AMI, payment)
utility.integration.log     — API call audit log
utility.notification.log    — SMS/portal notification dispatch
utility.payment.gateway.transaction — Payment gateway integration
```

---

## 7. Module Dependency Map

```
                    ┌──────────────┐
                    │  date_range  │  (OCA module)
                    │   (OCA)      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ utility_core │  ← First to install
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
     ┌────────▼───────┐   │   ┌────────▼───────┐
     │utility_inventory│   │   │utility_operations│
     └────────┬───────┘   │   └────────┬───────┘
              │            │            │
              │     ┌──────▼───────┐   │
              │     │utility_prepaid│   │
              │     └──────┬───────┘   │
              │            │            │
              └────────┬───┴────────────┘
                       │
                ┌──────▼───────┐
                │utility_billing│
                └──────┬───────┘
                       │
              ┌────────┼────────┐
              │        │        │
     ┌────────▼───────┐│ ┌─────▼────────┐
     │utility_portal  ││ │utility_migration│
     └────────────────┘│ └──────────────┘
                       │
              ┌────────▼───────┐
              │  Standard Odoo │
              │ (sale, account, │
              │  pos, stock)    │
              └────────────────┘
```

**Installation Order:** `date_range` → `utility_core` → `utility_inventory` → `utility_prepaid` → `utility_operations` → `utility_billing` → `utility_portal` → `utility_migration`

---

## 8. Data Domain Summary

### 8.1 Total Model Count

| Module | New Models | Inherited Models | Transient (Wizards) |
|--------|-----------|-----------------|-------------------|
| utility_core | 28 | 4 (res.partner, res.company, res.users, sale.order.type) | 1 |
| utility_inventory | 4 | 1 (utility.meter) | 0 |
| utility_prepaid | 5 | 2 (pos.order, pos.order.line) | 0 |
| utility_operations | 7 | 1 (utility.meter.replacement) | 0 |
| utility_billing | 12 | 4 (sale.order, sale.order.line, account.move, account.payment) | 0 |
| utility_portal | 1 | 0 | 0 |
| utility_migration | 2 | 0 | 1 |
| **Total** | **59** | **12** | **2** |

### 8.2 Key Relationships

```
res.partner ──1:1──> utility.customer ──1:1──> utility.meter ──N:1──> utility.transformer
                                                              │
                                                              └──N:1──> utility.meter.type
                                                              └──N:1──> utility.meter.model
                                                              └──N:1──> utility.meter.status

utility.customer ──N:1──> utility.subscriber.category
utility.customer ──N:1──> utility.subscriber
utility.customer ──N:1──> utility.contract.template
utility.customer ──N:1──> utility.region (area)
utility.customer ──N:1──> utility.transformer (cell_id)

sale.order ──N:1──> utility.customer (account_id)
sale.order ──N:1──> utility.meter
sale.order ──N:1──> date.range
sale.order ──N:1──> utility.contract.template
sale.order ──1:N──> sale.order.line
sale.order ──1:N──> account.payment
sale.order ──1:N──> utility.penalty
sale.order ──1:N──> utility.installment.plan

account.payment ──N:1──> utility.cashier.shift
account.payment ──N:1──> utility.collector.shift
account.payment ──N:1──> utility.reading.batch

utility.reading ──N:1──> utility.meter
utility.reading ──N:1──> utility.customer
utility.reading ──N:1──> date.range
utility.reading ──N:1──> utility.reading.batch

utility.service.order ──N:1──> utility.customer
utility.service.order ──N:1──> utility.meter
utility.service.order ──1:N──> utility.work.order

pos.order ──N:1──> utility.customer
pos.order ──1:N──> utility.token
pos.order ──N:1──> utility.cashier.shift
```

---

## 9. Integration Landscape

### 9.1 External System Integrations

| System | Direction | Protocol | Purpose | Module |
|--------|-----------|----------|---------|--------|
| STS Token Server | Outbound | HTTP/REST | Generate & validate prepaid tokens | utility_prepaid |
| Payment Gateway | Bidirectional | REST + Webhook | Process online payments | utility_portal |
| SMS Provider | Outbound | HTTP/REST | Send customer notifications | utility_core |
| AMI System | Inbound | REST Webhook | Receive automated readings | utility_portal |
| POS Terminal | Internal | Odoo POS | Prepaid sales interface | utility_prepaid |

### 9.2 Standard Odoo Module Dependencies

| Odoo Module | Used By | Purpose |
|-------------|---------|---------|
| `sale` | billing | Sale order framework (base for bills) |
| `account` | billing | Invoices, payments, reconciliation |
| `pos` | prepaid | POS terminal interface |
| `stock` | inventory | Lot tracking for meters |
| `mail` | all | Chatter (limited use — no email) |
| `date_range` | core, billing | Billing periods and cycles |
| `product` | billing | Products for fees and charges |
| `base_setup` | core | Settings framework |

---

## 10. Non-Functional Requirements Summary

### 10.1 Performance

| Metric | Target |
|--------|--------|
| Bill generation (single) | < 2 seconds |
| Batch bill generation (1000 bills) | < 5 minutes |
| Reading upload (1000 readings) | < 3 minutes |
| Token generation | < 5 seconds |
| API response time (95th percentile) | < 500ms |
| Dashboard load time | < 3 seconds |

### 10.2 Scalability

| Dimension | Target |
|-----------|--------|
| Concurrent users | 100+ |
| Customer accounts | 500,000+ |
| Meter records | 500,000+ |
| Historical readings | 10,000,000+ |
| Monthly transactions | 100,000+ |
| API requests/hour | 10,000+ |

### 10.3 Security

- Role-based access control (10 groups)
- Record-level security (multi-company rules)
- API token authentication (portal endpoints)
- `safe_eval()` sandbox for formula execution
- Input validation (regex patterns on phone, meter numbers)
- Audit logging for all critical operations
- No email-based notifications (SMS + portal only)

### 10.4 Availability

- Database backups: daily automated
- Zero-downtime deployment for code updates
- Graceful degradation for external integrations (retry queues)

---

## 11. Regulatory & Compliance

| Requirement | Implementation |
|-------------|---------------|
| Consumer data protection | Multi-company record rules, portal ownership validation |
| Financial audit trail | `account.move` journal entries for all financial transactions |
| Meter accuracy | Meter log tracking, tamper case management |
| Tariff regulation | Configurable contract templates with approval workflow |
| Revenue protection | Tamper detection, consumption anomaly alerts, emergency credit limits |
| Reporting | Daily/monthly summaries, outstanding balance reports, transformer balance reports |

---

## 12. Deployment Model

| Component | Technology |
|-----------|-----------|
| Application Server | Odoo 16.0 (Python 3.10+) |
| Database | PostgreSQL 14+ |
| Frontend | Odoo Web Client (OWL 2.0) |
| POS | Odoo POS (local network) |
| API Layer | Odoo HTTP Controllers (JSON REST) |
| External Integrations | `requests` library (outbound HTTP) |
| Notifications | SMS via HTTP API (no email) |
| Payments | Payment gateway REST API + webhook |

---

## 13. Open Items & Assumptions

### 13.1 Assumptions

1. All customers have unique 11-digit customer numbers
2. All meters have unique meter numbers with QR codes
3. STS token server is available on the local network
4. SMS provider supports Arabic text messages
5. Payment gateway supports the local currency
6. AMI system provides REST API for reading callbacks
7. Internet connectivity is available at all office locations
8. POS terminals are on a local network with the Odoo server

### 13.2 Open Items

| Item | Status | Priority |
|------|--------|----------|
| Barcode OCR service integration | Pending | Low |
| Multi-language UI (English toggle) | Not Started | Low |
| Advanced analytics dashboard | Not Started | Medium |
| Mobile app for field technicians | Not Started | Medium |
| Real-time SCADA integration | Out of Scope | — |

---

*End of Master Specification*
