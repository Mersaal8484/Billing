---
name: utility-api
description: Use for Utility ERP REST endpoints, reader callbacks, webhooks, media input, API error contracts, authentication, ownership, and exception handling.
---

# Utility API

Apply this skill to controllers and integrations. Treat the HTTP contract and the ORM transaction as one boundary.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/API_SPECIFICATION.md`
- `docs/INTEGRATION_ARCHITECTURE.md`
- `docs/SECURITY_MATRIX.md`
- `docs/READING_BATCH_ARCHITECTURE.md`
- `docs/UAT_PLAN.md`

## Rules

- Preserve endpoint names and success payloads unless a compatibility change is explicitly approved.
- Use the established error envelope: `success=false`, stable machine `code`, and human-readable `error`.
- Catch expected business exceptions explicitly; do not convert database, integrity, operational, or programming failures into business errors.
- Authenticate and validate ownership and geographic scope before using intentional `sudo()`.
- Keep webhook and callback processing idempotent, transactional, and safe on retries.

## Workflow

1. Inspect the current controller, route auth, model access, and tests before editing.
2. Specify status code, error code, payload compatibility, rollback, and retry behavior.
3. Add HTTP tests for success, validation, not-found, forbidden, malformed input, duplicate delivery, and unexpected failure propagation.
