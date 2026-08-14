# Release Traceability Matrix

**Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Reviewed SHA:** `51e8dba5c47ed8ff9d1485b519e1b1586cb30522`
**Documentation Version:** 2.1
**Rule:** Test coverage below means test files/scenarios exist; it does not claim execution passed.

| Business Capability | Module | Primary Model | Accounting/Inventory Artifact | Security Group | UI Entry Point | Test Coverage Exists | Documentation |
|---|---|---|---|---|---|---|---|
| Customer/master data | `utility_core` | `utility.customer` | Customer/account records | Core operational roles | Customers | `utility_core/tests` | MASTER_SPECIFICATION, SECURITY_MATRIX |
| Meter custody | `utility_core`/`utility_inventory` | `utility.meter` | `stock.lot`, stock moves | Technician/Supervisor | Meters/Stock | meter operational tests | INVENTORY_CUSTODY |
| Reading | `utility_core` + Billing extension | `utility.reading` | Reading components / bill links | Reader/Reviewer/Billing | Readings | `test_core_billing_ownership.py`, reading review tests | SRS, BILLING_ENGINE |
| Reading Batch | `utility_billing` | `utility.reading.batch` | `utility.reading` | Meter Reader/Billing Manager | Reading Batch UI/API | reader API + concurrency tests | READING_BATCH_ARCHITECTURE |
| Installation | `utility_operations` | `utility.installation` | Stock context where applicable | Technician/Supervisor | Installations | operations tests where present | METER_REPLACEMENT, UAT_PLAN |
| Work Order | `utility_operations` | `utility.work.order` | Operational task | Technician/Supervisor | Work Orders | operations tests where present | SRS, UAT_PLAN |
| Alarm/service request | `utility_operations`/Billing API | `utility.alarm`, `utility.service.order` | Service/work links | Supervisor/Technician | Alarms/Service Orders | alarm and API tests | SECURITY_MATRIX, UAT_PLAN |
| Meter Replacement | `utility_operations` | `utility.meter.replacement` | Standard stock pickings/moves | Technician/Supervisor | Replacement wizard | meter replacement tests | METER_REPLACEMENT, INVENTORY_CUSTODY |
| Bill | `utility_billing` | `sale.order` | Commercial bill context | Billing User/Manager | Bills | financial UAT tests | BILLING_ENGINE |
| Accounting Invoice | `utility_billing`/Odoo Accounting | `account.move` | Canonical invoice/credit note | Billing/Admin/Accounting | Bill smart button | financial lifecycle tests | ACCOUNTING_FLOWS |
| Payment | `utility_billing`/Odoo Accounting | `account.payment` | Receivable/payment entry | Cashier/Collector/Billing | Bill smart button/payment form | payment allocation/concurrency tests | PAYMENT_ALLOCATION |
| Gateway callback | `utility_billing` | `utility.payment.gateway.transaction` | Exactly one payment on success | API auth/provider | REST endpoint | gateway idempotency tests | API_SPECIFICATION, INTEGRATION_ARCHITECTURE |
| Write-off | `utility_billing` | `utility.writeoff` | `account.move` out_refund/Credit Note | Billing Manager/Admin | Write-off form | financial lifecycle/write-off tests | ACCOUNTING_FLOWS, UAT_PLAN |
| Migration | `utility_core` staging | `utility.migration.*` | Created master records | Admin | Migration batches | migration tests where present | DATA_MIGRATION |
| Sensitive wizard | `utility_core` | Customer/route/network wizards | Master mutations | Supervisor/Admin | Wizard forms | `test_sensitive_wizard_permissions.py` | SECURITY_MATRIX |
| Organizational data isolation | `utility_core` security | `res.users`, `utility.region`, scoped business relations | No accounting/inventory artifact | Role groups + target scope policy | User settings/record rules | Partial role/region/route coverage exists; complete Region/Branch UAT is planned | ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION, SECURITY_MATRIX |

## Current vs target note

The matrix maps current V1 entry points and artifacts. PgBouncer, horizontal workers, partitioning, scalable media, and Temporal orchestration are documented in `TARGET_V2_ARCHITECTURE_ROADMAP.md` and are not current UI or runtime dependencies.
