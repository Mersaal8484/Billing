---
name: utility-deployment-operations
description: Use for Utility ERP deployment, production configuration, NGINX/Odoo topology, backup and restore, cutover, rollback, annual database rotation, Filestore consistency, or go-live operations.
---

# Utility deployment operations

Use this skill for operational changes and release decisions affecting the running Odoo system, PostgreSQL, Filestore, integrations, or cutover process.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/DEPLOYMENT.md`
- `docs/BACKUP_RESTORE.md`
- `docs/GO_LIVE_RUNBOOK.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `AGENTS.md`

## Boundaries

- Treat Odoo PostgreSQL plus its matching Filestore/media recovery point as one recoverable unit.
- Distinguish CURRENT V1 runtime facts from TARGET V2 topology such as PgBouncer, Redis, Temporal, read replicas, and annual database rotation.
- Do not claim deployment, restore, monitoring, or rollback success from configuration files or a runbook alone; require command output, timestamps, and named evidence.
- Do not expose secrets in configuration, logs, backup artifacts, or evidence reports.

## Workflow

1. Establish the reviewed commit, environment, module dependency order, database, Filestore path, and change window.
2. Inspect versioned configuration, addon manifests, service processes, reverse proxy rules, scheduled jobs, integrations, and storage dependencies.
3. For backup or restore, define recovery point, database/media/config consistency, retention, integrity checks, RPO/RTO targets, and isolated restore destination.
4. For cutover, record freeze time, source export, target snapshot, migration evidence, integration pause/resume, smoke tests, business sign-off, and rollback trigger.
5. Keep rollback reversible and explicit: identify the exact snapshot or routing change, post-cutover writes, and authorizing owner.
6. Report static, runtime, restore, UAT, and post-cutover evidence separately, then hand off monitoring and recovery instructions.

## Validation checklist

- Verify module installation order: `date_range`, `utility_core`, `utility_inventory`, `utility_operations`, `utility_billing`.
- Verify database and Filestore are backed up at compatible points and restored in isolation.
- Verify certificates, DNS, request limits, workers, cron ownership, attachment access, time zone, and secret injection.
- Run proportional Odoo tests and smoke tests for login, reading, billing, invoice, payment, media, and API paths.
- Capture exact commands and outputs; mark unavailable runtime or CI proof as unavailable rather than passing.
