# Production Sizing Implementation Plan

**Scope:** 300,000 customers, 600–750 concurrent users, up to 7.2 million readings/year, annual operational database rotation, `ir.attachment` with shared Filestore, 365-day image-byte retention, no initial DR site, and no initial MinIO cluster.

**Classification:** TARGET V2 / CONDITIONAL. This plan does not claim that the target topology is deployed or that the capacity numbers are runtime-proven.

## Priority 0 — Decisions and safeguards

1. Approve the annual active-database boundary and archive-retention policy.
2. Approve the 365-day image-byte retention policy with legal holds and exception handling.
3. Approve RPO/RTO and explicitly record acceptance of no DR.
4. Register ADR-023 and the sizing document as the governing target baseline.
5. Define ownership for database close, archive, Filestore retention, restore, and go/no-go approval.

**Exit:** signed policy decisions, named owners, rollback authority, and no unresolved contradiction between database archive retention and media retention.

## Priority 1 — Evidence and sizing baseline

1. Measure current PostgreSQL, WAL, index, bloat, and Filestore usage.
2. Measure real image size distribution and Original/Review/Thumbnail ratios.
3. Establish production-like data for 300k customers and 7.2m annual readings.
4. Benchmark reading batches, reviewer media access, billing micro-batches, payments, and reports.
5. Size PostgreSQL at 2 TB initially; promote to 4 TB only when measurements require it.
6. Validate 4 TB usable active Filestore and 12 TB initial archive/backup capacity.

**Exit:** measured growth model, bottleneck report, capacity reserve decision, and approved test results.

## Priority 2 — Media and retention controls

1. Verify `utility.media.asset` remains the metadata/audit owner.
2. Standardize `ir.attachment` Filestore paths and shared-storage access across Odoo nodes.
3. Verify variant generation and authorized delivery.
4. Build a dry-run retention scanner for `uploaded_at + 365 days`.
5. Implement bounded, resumable, audited deletion of bytes only.
6. Test expired evidence, legal holds, orphan files, failed deletion, and retry behavior.

**Exit:** no unauthorized media access, successful dry-run report, safe deletion test, and preserved reading/audit history.

## Priority 3 — Annual close and archive workflow

1. Freeze new writes at the close boundary.
2. Drain or explicitly account for pending readings, billing, payments, integrations, and jobs.
3. Run integrity checks, `VACUUM/ANALYZE` as appropriate, and the final backup.
4. Register archive metadata, checksum, code version, module versions, and database state.
5. Enforce read-only access to the closed database.
6. Provision and validate the next operational database.
7. Execute a rollback rehearsal before enabling the new year.

**Exit:** repeatable close runbook, successful staging rehearsal, no duplicate financial effects, and successful cross-year smoke tests.

## Priority 4 — HA and production topology

1. Deploy two PostgreSQL hosts with local HA and a witness.
2. Deploy shared protected Filestore and archive storage.
3. Deploy load balancers and multiple Odoo application/job nodes.
4. Add PgBouncer only after connection measurements justify it.
5. Add Redis and Temporal only for validated shared-cache or long-running orchestration needs.
6. Keep MinIO and a DR site out of the initial deployment unless an approved trigger is met.

**Exit:** node-failure tests, stable connection pools, media consistency across nodes, and security review passed.

## Priority 5 — Backup, restore, and release gate

1. Back up PostgreSQL, Filestore, configuration, and archive metadata.
2. Test restore to an isolated environment using a matching database/media recovery point.
3. Validate invoices, payments, readings, workflows, and authorized media samples.
4. Measure actual restore duration and data loss against approved RPO/RTO.
5. Execute load tests and annual-close rehearsal together.
6. Approve go-live only when static, runtime, restore, and UAT evidence are separately recorded.

**Exit:** signed restore report, release verdict, rollback plan, monitoring/alerting, and operational handover.

## Priority order summary

```text
P0 Policy/ADR
  → P1 Measurement
  → P2 Media/Retention
  → P3 Annual Close/Archive
  → P4 HA Topology
  → P5 Restore/Load/Go-Live
```

## Deferred triggers

- Reintroduce MinIO for multi-class large objects, public presigned uploads, multi-year image retention, immutability, or measured shared-Filestore limits.
- Add a DR site when approved continuity requirements exceed local HA and backup/restore capability.
- Increase PostgreSQL or Filestore capacity only from measured growth, reserve, and performance evidence.
- Introduce partitioning, Temporal, or additional workers only after a documented trigger, rehearsal, and rollback plan.
