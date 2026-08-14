# Utility ERP Architecture V2.1 — Documentation Index

**Platform:** Odoo 16 Community
**Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Branch:** `development`
**Last Verified Implementation SHA:** `51e8dba5c47ed8ff9d1485b519e1b1586cb30522`
**Documentation Version:** 2.1
**Last Verified Date:** 2026-08-14
**Status:** Current V1 + Target V2

هذه الحزمة لا تستبدل المعمارية من الصفر؛ هي مزامنة V2.0 مع تنفيذ V1 الحالي، مع فصل واضح بين implementation evidence وTarget V2 scale decisions.

## Precedence

عند التعارض، اتبع الترتيب التالي:

1. دليل التنفيذ الحالي لـCURRENT V1 عند الـSHA المراجع.
2. ADR أحدث مقبول أو قرار معماري مقبول صراحة.
3. `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md` لقرارات Target V2.
4. وثيقة المجال المتخصصة.
5. وثائق UAT والتشغيل والـrunbook.

وثيقة Master قديمة لا تتغلب على قرار تنفيذ أحدث مقبول. وفي المقابل، لا يعيد التنفيذ الحالي تعريف Target V2 بصمت؛ عند الاختلاف يجب توثيق CURRENT وTARGET معًا.

**Rule:** A stale master document must not override a newer accepted implementation decision. Current implementation must not silently redefine TARGET V2 architecture.

## Documentation Status Matrix

| Document | Purpose | Current V1 | Target V2 | Status | Last Verified SHA | Owner/Domain |
|---|---|---|---|---|---|---|
| [CURRENT_V1_IMPLEMENTATION_BASELINE.md](CURRENT_V1_IMPLEMENTATION_BASELINE.md) | Implementation truth | نعم | لا | CURRENT | `51e8dba5` | Architecture/Engineering |
| [TARGET_V2_ARCHITECTURE_ROADMAP.md](TARGET_V2_ARCHITECTURE_ROADMAP.md) | Scale roadmap | لا | نعم | TARGET | `51e8dba5` | Architecture/Platform |
| [ARCHITECTURE_DECISION_LOG.md](ARCHITECTURE_DECISION_LOG.md) | ADR index | نعم/قرارات مقبولة | نعم | CURRENT + TARGET | `51e8dba5` | Architecture |
| [OPERATIONAL_UI_UX_ARCHITECTURE.md](OPERATIONAL_UI_UX_ARCHITECTURE.md) | Operational UX contract | نعم | محدود | CURRENT + TARGET | `51e8dba5` | Product/Operations |
| [RELEASE_TRACEABILITY_MATRIX.md](RELEASE_TRACEABILITY_MATRIX.md) | Capability traceability | نعم | محدود | CURRENT + TARGET | `51e8dba5` | QA/UAT |
| [ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION.md](ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION.md) | Role/scope isolation architecture | جزئي | نعم | CURRENT + TARGET | `51e8dba5` | Security/Architecture |
| [DOCUMENT_INDEX.md](DOCUMENT_INDEX.md) | Package index and precedence | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Documentation |
| [manifest.json](manifest.json) | Machine-readable metadata | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Documentation/Release |
| [UTILITY_ERP_MASTER_ARCHITECTURE_V2.md](UTILITY_ERP_MASTER_ARCHITECTURE_V2.md) | Master architecture | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Architecture |
| [MASTER_SPECIFICATION.md](MASTER_SPECIFICATION.md) | Master requirements | نعم | نعم | CURRENT + TARGET | `51e8dba5` | BA/Architecture |
| [SRS.md](SRS.md) | Software requirements | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Engineering/QA |
| [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) | Technical topology | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Platform |
| [BILLING_ENGINE.md](BILLING_ENGINE.md) | Billing lifecycle | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Billing |
| [PERIOD_LIFECYCLE.md](PERIOD_LIFECYCLE.md) | Period/cycle rules | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Core/Billing |
| [READING_BATCH_ARCHITECTURE.md](READING_BATCH_ARCHITECTURE.md) | Batch ingestion | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Billing/Integration |
| [API_SPECIFICATION.md](API_SPECIFICATION.md) | API contracts | نعم | نعم | CURRENT + TARGET | `51e8dba5` | API/Integration |
| [INTEGRATION_ARCHITECTURE.md](INTEGRATION_ARCHITECTURE.md) | External integration | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Integration |
| [ACCOUNTING_FLOWS.md](ACCOUNTING_FLOWS.md) | Accounting truth and flows | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Accounting |
| [PAYMENT_ALLOCATION.md](PAYMENT_ALLOCATION.md) | Explicit allocation | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Accounting/Billing |
| [METER_REPLACEMENT.md](METER_REPLACEMENT.md) | Replacement workflow | نعم | محدود | CURRENT + TARGET | `51e8dba5` | Operations/Inventory |
| [INVENTORY_CUSTODY.md](INVENTORY_CUSTODY.md) | Stock custody | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Inventory |
| [MEDIA_ARCHITECTURE.md](MEDIA_ARCHITECTURE.md) | Media ownership/storage | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Core/Platform |
| [SECURITY_MATRIX.md](SECURITY_MATRIX.md) | Access and security | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Security |
| [CAPACITY_AND_PERFORMANCE.md](CAPACITY_AND_PERFORMANCE.md) | Capacity and debt | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Performance |
| [DATA_MIGRATION.md](DATA_MIGRATION.md) | Migration controls | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Migration |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Supported/target topology | نعم | نعم | CURRENT + TARGET | `51e8dba5` | DevOps |
| [BACKUP_RESTORE.md](BACKUP_RESTORE.md) | Recovery | نعم | نعم | CURRENT + TARGET | `51e8dba5` | DBA/Operations |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Signals and operations | نعم | نعم | CURRENT + TARGET | `51e8dba5` | SRE/Operations |
| [UAT_PLAN.md](UAT_PLAN.md) | Acceptance scenarios | نعم | نعم | CURRENT + TARGET | `51e8dba5` | QA/UAT |
| [GO_LIVE_RUNBOOK.md](GO_LIVE_RUNBOOK.md) | Release operations | نعم | نعم | CURRENT + TARGET | `51e8dba5` | Release/Operations |

## Current V1 module chain

```text
date_range
    ↓
utility_core
    ↓
utility_inventory
    ↓
utility_operations
    ↓
utility_billing
```

`utility_prepaid` = **OUT OF SCOPE for V1**.

## Shared classification vocabulary

- **CURRENT V1:** verified in the implementation at the reviewed SHA.
- **TARGET V2:** accepted future architecture, not implied as deployed.
- **DEFERRED:** intentionally not proven or not implemented yet.
- **OUT OF SCOPE:** excluded from the current release boundary.
