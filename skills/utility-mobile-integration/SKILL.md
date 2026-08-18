---
name: utility-mobile-integration
description: Use for the Flutter meter-reading app, offline-first readings, sync queues, Odoo REST integration, authentication, captured media, QR scanning, thermal printing, or mobile release validation.
---

# Utility mobile integration

Use this skill for changes under `mobile/meter_reading_app` or for any contract shared by the mobile client and Utility ERP APIs. Treat the server API and local offline state machine as one integration boundary.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/API_SPECIFICATION.md`
- `docs/INTEGRATION_ARCHITECTURE.md`
- `docs/READING_BATCH_ARCHITECTURE.md`
- `docs/MEDIA_ARCHITECTURE.md`
- `mobile/meter_reading_app/README.md`
- `mobile/meter_reading_app/pubspec.yaml`

## Rules

- Preserve established API authentication, ownership/geographic scope, error envelope, idempotency key, retry semantics, and backward compatibility.
- Model offline work explicitly: local draft, queued, in-flight, acknowledged, rejected, and retryable failure. Never silently discard a reading or duplicate a server-side financial effect.
- Keep server validation authoritative for meter ownership, reading lifecycle, period, duplicate submission, and media constraints.
- Store only minimum sensitive data locally; protect tokens and queued media, and avoid logging credentials or full customer data.
- Treat captured photos as evidence: validate size/type/orientation, preserve linkage, retry safely, and distinguish upload failure from reading rejection.
- Keep printer, QR, camera, and network permissions justified and testable; do not claim device support without real-device or documented emulator evidence.
- Do not add prepaid vending behavior to the V1 postpaid mobile flow.

## Workflow

1. Inspect the Flutter feature, repository, local database schema, sync engine, API client/service, and corresponding Odoo controller/model tests.
2. Write the contract impact before editing: request/response, status mapping, idempotency, ownership, error recovery, and compatibility.
3. Implement state transitions in one place and make retries deterministic. Use the server identifier after acknowledgement.
4. Test online success, offline capture, restart with queued work, timeout, duplicate retry, forbidden/not-found, malformed input, media failure, and partial sync.
5. Verify Arabic/RTL usability, loading/error/empty states, permissions, camera/QR behavior, receipt formatting, and printer fallback when UI is affected.
6. Run Flutter analysis/tests plus focused Odoo HTTP/integration tests, and record device/build/runtime evidence separately.
