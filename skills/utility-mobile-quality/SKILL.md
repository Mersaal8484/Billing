---
name: utility-mobile-quality
description: Use when adding or repairing Flutter/Dart unit, widget, integration, offline-sync, mock, static-analysis, coverage, or release tests in `mobile/meter_reading_app`.
---

# Utility mobile quality

Use official Flutter/Dart testing and analysis patterns, adapted to this project's Riverpod, Drift, Dio, offline queue, media, QR, and printer integrations. Keep the mobile API contract aligned with the Odoo server tests.

## Read first

- `mobile/meter_reading_app/pubspec.yaml`
- `mobile/meter_reading_app/README.md`
- `mobile/meter_reading_app/lib/core/sync/sync_engine.dart`
- `mobile/meter_reading_app/lib/core/network/odoo_api_client.dart`
- `mobile/meter_reading_app/test/`
- `skills/utility-mobile-integration/SKILL.md`
- `docs/API_SPECIFICATION.md`

## Test layers

- Unit-test archive builders, parsers, validators, retry/backoff, idempotency, and state transitions without Flutter bindings where possible.
- Widget-test loading, empty, error, Arabic/RTL, permission, form validation, and user interaction states with deterministic repositories.
- Integration-test online capture, offline capture, restart with queued work, acknowledgement, duplicate retry, partial failure, media upload, and receipt/printer fallback.
- Use mocks or fakes at external boundaries; never make tests depend on a live Odoo database, provider, Bluetooth printer, camera, or network unless explicitly marked as an environment test.

## Workflow

1. Reproduce the behavior with the smallest failing test and identify the state transition or contract under test.
2. Inspect existing test conventions, generated Drift/Riverpod code, fixtures, and repository interfaces before adding helpers.
3. Add the narrowest test that proves the invariant, including failure, retry, duplicate, and restart paths for sync behavior.
4. Run `flutter analyze` and focused `flutter test`; collect coverage when a release or regression review requires it.
5. Use integration tests only for cross-layer behavior that unit/widget tests cannot prove. Record device, emulator, Flutter/Dart versions, and unavailable capabilities.
6. Keep test data synthetic and non-sensitive. Do not weaken assertions to make platform or timing failures disappear.

## Release checks

- A passing widget test does not prove API compatibility, offline durability, device permissions, or printer support.
- A coverage percentage is not a quality verdict; prioritize authentication, sync, media, financial navigation, and error recovery paths.
- Pair mobile evidence with the corresponding Odoo HTTP/integration test and classify static, runtime, and device evidence separately.
