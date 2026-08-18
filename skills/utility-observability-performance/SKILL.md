---
name: utility-observability-performance
description: Use for Utility ERP logging, correlation IDs, metrics, alerts, queue health, database health, profiling, load tests, capacity planning, N+1 investigation, or performance evidence.
---

# Utility observability and performance

Use this skill when diagnosing runtime behavior or proving throughput, latency, reliability, capacity, or operational visibility. Keep measured facts separate from planning assumptions and TARGET V2 architecture.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/OBSERVABILITY.md`
- `docs/CAPACITY_AND_PERFORMANCE.md`
- `docs/DEPLOYMENT.md`
- `docs/UAT_PLAN.md`
- `skills/odoo-framework-best-practices/SKILL.md`

## Rules

- Correlate logs and evidence with `request_id`, `batch_uuid`, `command_uuid`, `workflow_run_id`, payment reference, asset UUID, or period code as applicable.
- Never log passwords, tokens, secrets, or unnecessary personal data. Preserve useful error codes, model/res_id, operation, duration, and safe scope identifiers.
- Measure reading ingestion, review queues, billing, invoices, payments, API latency/errors, media processing, cron backlog, and database health where relevant.
- Treat N+1 suspicion as a hypothesis until query counts, timings, or production-like profiling demonstrate impact. Do not optimize by duplicating business truth.
- Use bounded batches and explicit lock, WAL, memory, transaction-duration, queue-depth, and retry measurements. Never extrapolate a million-subscriber claim from a static test file.
- Treat metrics, dashboards, and alert definitions as implementation only when present and runtime-verified.

## Workflow

1. Define the symptom, workload, environment, baseline, and success threshold.
2. Trace the operation across Odoo models, SQL/ORM calls, jobs, integrations, media, and database transactions.
3. Choose the smallest safe measurement: structured logs, query count, profiler, representative benchmark, queue-age sample, or database statistics.
4. Run comparable control and changed measurements with realistic data volume and concurrency; record hardware, configuration, dataset, and exact command.
5. Diagnose bottleneck class—ORM/query, locks, CPU, memory, WAL/IO, network, media, external provider, or queue scheduling—before changing code.
6. Re-run focused tests and the same measurement, then document residual risk and the next evidence gate.

## Release evidence

Separate Static Evidence, Runtime Evidence, UAT Evidence, and Load/Profiling Evidence. A green unit test, an empty CI status, or a visible dashboard does not prove runtime health or capacity.
