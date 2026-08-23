# TECHNICAL ARCHITECTURE

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

**Document Type:** Detailed Technical Architecture

> تفصيل الطبقات والمكونات والحدود التقنية التي تنفذ Master Architecture V2.

---


## المبادئ المعمارية الملزمة

- Odoo 16 Community هو **System of Record** للـUtility Domain والمحاسبة.
- التشغيل المستهدف لمؤسسة تشغيلية واحدة؛ النطاق الأمني والتشغيلي يعتمد على Geography وليس Business Multi-Company.
- لا توجد Customer Wallet في Postpaid Utility.
- لا توجد Taxes في Utility Billing Flow الحالي.
- Reading + Review مرحلة تشغيلية واحدة.
- لكل Cycle فترة Reading وفترة Payment مستقلة مرتبطة بنفس `cycle_key`.
- `utility.bill.reading.component` هو Immutable Billing Segment Snapshot ولا يعاد تصميمه.
- `periodic` هو Billing Anchor، و`replacement_closing` و`opening` يحتفظان بدلالتهما.
- عدة عمليات Replacement داخل نفس Cycle تنتهي إلى **فاتورة واحدة** للحساب/الفترة مع عدة Reading Components.
- `utility.media.asset` هو Canonical Media Model.
- Payment Reconciliation يجب أن يكون Targeted/Explicit، وليس Partner-wide.
- التصحيحات التاريخية تتم بواسطة Correction/Reversal Documents، وليس بتعديل السجل التاريخي المنشور.
- Hybrid Workflow: المعاملات القصيرة داخل Odoo؛ Temporal للعمليات الطويلة وReading Batch orchestration عند Target Scale.
- Redis مساعد للـRate Limiting/Cache فقط، وليس Source of Truth.
- PgBouncer جزء من Target Production Scale عند تعدد العقد والـWorkers.
- Persistent Staging + Idempotency + Partial Failure هي القاعدة لدفعات القراءات.


## 1. Logical Architecture

```text
Presentation
├── Odoo Backend Views
├── OWL Review Workspace
├── Portal
├── Reports
└── JSON/HTTP APIs
        ↓
Application Services
├── Billing
├── Media
├── Workflow/Outbox
├── Payment Allocation
├── Operations Orchestration
└── Migration/Repair
        ↓
Domain Models
├── Customer/Meter/Network
├── Contract Template & Version (utility.contract.template.version)
├── Period/Reading
├── Bill & Reading Component (utility.bill.reading.component)
├── Pricing Snapshot & Applied Blocks (utility.bill.pricing.snapshot, utility.bill.pricing.block)
├── Replacement
├── Service Order
└── Financial Adjustment
        ↓
Infrastructure Adapters
├── Odoo Accounting
├── Odoo Stock
├── Media Storage
├── HTTP Providers
└── Local/Temporal Workflow
        ↓
Persistence
├── PostgreSQL
└── Media Filesystem / Compatibility Attachments
```

---

## 2. Component Ownership

### Core
لا ينفذ Payment Posting أو Stock Picking business orchestration.

### Billing
يملك القراءة الدفعية، Review، Billing، Payment Allocation، Revenue adjustments.

### Operations
يملك orchestration الميداني، وليس canonical replacement calculations.

### Inventory
يملك physical movement/custody للعدادات.

---

## 3. Transaction Boundaries

### Atomic Odoo Transactions
- Single bill generation.
- Accounting posting.
- Payment posting/allocation.
- Replacement domain commit.
- Period transition.

### Durable Long-Running Workflows
- Field operation waiting days/human actions.
- Large reading batch coordination.
- Large-scale billing coordination if needed.

### External Side Effects
يتم عزلها خلف Outbox/command عند قابلية التأخير.

---

## 4. Data Architecture

### High-Growth Tables
- `utility_reading`
- `utility_reading_batch_line`
- `account_move_line`
- integration logs
- audit logs

### Partition Candidates
الأولوية لـReading/Staging حسب `reading_date` أو cycle month.

Partitioning للجداول القياسية مثل `account_move_line` لا ينفذ دون Proof-of-Compatibility واختبارات Upgrade.

---

## 5. Caching

Redis فقط لـ:

- rate limiting counters.
- short-lived reference data.
- expensive repeated reviewer lookups.

لا يستخدم لـ:

- balances.
- bill state.
- payment state.
- canonical reading data.

---

## 6. Media Delivery

```text
Browser
 → authorized URL
 → Odoo checks access
 → X-Accel-Redirect/internal path
 → NGINX
 → organized filesystem
```

Odoo لا يصبح Streaming Server للصور الكبيرة في Target Production.

---

## 7. Workflow Execution Matrix

| Work | Engine |
|---|---|
| single bill | Odoo |
| payment | Odoo |
| accounting post | Odoo |
| notification | Outbox worker |
| long service order | Temporal target |
| reading batch | Temporal/batch orchestrator |
| one image processing | local worker unless benchmark favors Temporal |

---

## 8. Database Connectivity

Target scale:

```text
Application Nodes
Workers
Temporal Activities
       ↓
PgBouncer
       ↓
PostgreSQL
```

يحدد Pool mode بعد اختبار Odoo compatibility، مع ضبط max client/backend connections بناءً على الحمل الفعلي.

---

## 9. Deployment Topology

```text
NGINX / Load Balancer
   ├── Odoo Node A
   ├── Odoo Node B
   └── ...
          ↓
       PgBouncer
          ↓
    PostgreSQL Primary
          └── Optional Read Replica

Redis
Temporal Cluster (scoped) + separate DB
Reading/Billing/Operations Workers
Media Storage + NGINX internal delivery
```

---

## 10. Compatibility Strategy

Temporary compatibility fields:
- `meter_image`
- `attachment_id`
- old period aliases

Rules:
1. لا Features جديدة عليها.
2. لا تعتبر Source of Truth.
3. لها migration/removal milestone.
4. Telemetry تحدد آخر استخدام قبل الحذف.

---

## 11. Technical Acceptance Gates

- No unauthorized direct media storage bypass.
- No partner-wide reconciliation.
- Period state migration complete.
- Billing constraints active.
- Outbox idempotency tested.
- Database load test with PgBouncer.
- Media authorization and NGINX delivery validated.
- Partition strategy rehearsed.

## V3.2 Current vs Target Topology

**CURRENT V1:** Odoo 16 module dependencies, PostgreSQL persistence, local/Odoo transaction execution, standard Odoo accounting and stock, Billing API controllers, and persistent migration/reading staging are the implementation baseline.

**TARGET V2 / CONDITIONAL:** PgBouncer, horizontal workers/nodes, scoped Temporal, scalable media delivery, and partition strategy. The architecture preserves these decisions without claiming they are deployed or runtime-validated at the reviewed SHA.
