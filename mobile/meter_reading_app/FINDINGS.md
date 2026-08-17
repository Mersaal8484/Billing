# FINDINGS.md — Phase 2 Verification

## Scope

This file documents step zero for phase 2 and the subsequent user decisions. No Flutter API repository, authentication flow, or image-size code change has been implemented yet.

The previous no-GPS decision remains in force: the mobile app should not add GPS/location capture as a product feature.

## Files Read

Odoo backend:

- `utility_erp/utility_erp/utility_core/models/utility_route.py`
- `utility_erp/utility_erp/utility_billing/models/utility_collector_shift.py`
- `utility_erp/utility_erp/utility_billing/controllers/utility_reader_api.py`
- `utility_erp/utility_erp/utility_portal/api/utility_api_main.py`
- Additional focused check: `utility_erp/utility_erp/utility_billing/models/account_payment.py`

Flutter mobile app:

- `lib/app/providers.dart`
- `lib/core/sync/sync_engine.dart`
- `lib/core/image/image_processing_service.dart`
- all files under `lib/features/readings/`
- all files under `lib/features/collections/`

## Confirmed Existing Backend API

`utility_billing/controllers/utility_reader_api.py` already provides the reading batch flow:

- `POST /api/v1/utility/reading/batch/create`
- `POST /api/v1/utility/reading/batch/upload_data`
- `POST /api/v1/utility/reading/batch/upload_image`
- `POST /api/v1/utility/reading/batch/confirm`
- `POST /api/v1/utility/reading/batch/status`
- `POST /api/v1/utility/reading/periods`
- `POST /api/v1/utility/reading/meter/lookup`
- `POST /api/v1/utility/reading/batch/my`

`utility_portal/api/utility_api_main.py` already provides portal-style billing endpoints:

- `POST /api/v1/utility/billing/balance`
- `POST /api/v1/utility/billing/bills`
- `POST /api/v1/utility/billing/pay`
- `POST /api/v1/utility/billing/payment_intent`
- `POST /api/v1/utility/operations/service_request`
- `POST /api/v1/utility/reports/daily`

`account.payment` already has:

- `utility_sale_order_id`
- `utility_payment_method`
- `collector_shift_id`
- default shift lookup through `_default_collector_shift()`

This is useful, but the API must still enforce the field-collection workflow explicitly.

## Gap 1 — QR Resolve Endpoint

Confirmed.

There is no endpoint matching:

```text
POST /api/v1/utility/collection/resolve_qr
```

The mobile app currently assumes QR payload format:

```text
UTILITY:{account_number}
```

Example:

```text
UTILITY:ACC-220000
```

Recommended implementation:

- Add the endpoint under `utility_billing/controllers/`, because this is an internal field-collector workflow, not a portal/customer workflow.
- Keep the QR format as `UTILITY:{account_number}`.
- Reuse the authorization/account lookup approach from `utility_portal/api/utility_api_main.py` without blindly duplicating the whole portal controller.
- Return one response containing account, customer, meter, balance/debt, and invoices so Flutter can fill `CollectionAccount`.

## Gap 2 — Field Collection Payment Must Require Open Collector Shift

Confirmed, with nuance.

`POST /api/v1/utility/billing/pay` creates and posts `account.payment`, but it does not explicitly require an open `utility.collector.shift`. The model-level default may assign `collector_shift_id` when an open shift exists, but the API currently does not:

- reject when no open shift exists,
- explicitly pass `collector_shift_id`,
- return the receipt/account shape expected by Flutter's `CollectionRepository.collect()`.

`utility.collector.shift` exists and already prevents overlapping open shifts per collector.

Recommended implementation:

- Add field-collection endpoints in `utility_billing/controllers/`:

```text
POST /api/v1/utility/collector/shift/current
POST /api/v1/utility/collector/shift/open
POST /api/v1/utility/collector/shift/close
POST /api/v1/utility/collection/collect
```

- `collection/collect` must reject payment when the current user has no open collector shift.
- `collection/collect` should create/post `account.payment` with explicit context or value for `collector_shift_id`.
- Response should match Flutter's receipt needs: reference, account, amount, method, paid date.

## Gap 3 — Reader Route Assignments Endpoint

Confirmed.

There is no endpoint matching:

```text
POST /api/v1/utility/reading/route/assignments
```

`utility.route` contains:

- `customer_ids`
- `inspector_ids`
- `cashier_ids`
- `supervisor_id`

`utility.customer` contains:

- `account_number` related to `customer_number`
- `route_id`
- `last_reading_date`
- `last_reading_value`
- `balance`

`utility.meter` contains:

- `meter_number`
- `serial_number`
- `customer_id`
- related `route_id`

Recommended implementation:

- Add `POST /api/v1/utility/reading/route/assignments` under `utility_billing/controllers/`.
- Input should require `date_range_id`; `route_id` may be optional.
- Filter routes by `inspector_ids` for the current user where possible.
- Return the customer/meter fields needed by Flutter's reader assignment model.
- Do not add GPS/location fields.

## Gap 4 — Authentication and Image Size

Confirmed.

### Authentication

All relevant endpoints currently use `auth='user'`, which means Odoo session authentication. The Flutter login is still mock and does not store a real token.

Recommendation:

- Use Odoo 16 `res.users.apikeys` as the approved mobile authentication basis.
- Implement a small mobile auth flow that exchanges user credentials for an API key/token or validates a generated key, then stores it with `flutter_secure_storage`.
- Use the token through `Dio` in a new `ApiClient`.

This is preferred over a custom token table because it leans on Odoo's built-in API key mechanism and reduces security surface area.

User decision on 2026-07-15:

```text
Approved: res.users.apikeys-based mobile token
```

### Image Size

Server endpoint `reading/batch/upload_image` uses:

```text
utility.max_image_size_kb = 100
```

Flutter currently compresses to:

```text
60 KB
```

User decision on 2026-07-15:

- Allowed image target must be either `60 KB` or `80 KB` only.
- Selected implementation target: `80 KB`.
- Rationale: `80 KB` stays under the server's current `100 KB` limit and should preserve better digit readability than `60 KB`.
- Keep EXIF/metadata stripping.
- Do not add GPS capture.

```text
Approved image target: 80 KB app compression
```

## Flutter Wiring Findings

The Flutter repository boundaries are clean enough for phase 2:

- `ReadingRepository` signature should remain unchanged.
- `CollectionRepository` signature should remain unchanged.
- `SyncEngine` should keep the same public surface, but its internal simulation can be replaced with real batch API calls.
- `providers.dart` is the correct composition root to swap mock repositories for API-backed implementations.

Important constraint:

`ReadingSyncStatus` is a local sync status only. It must not be confused with Odoo's reading/batch state machine.

## Next-Step Recommendation

Stop here and get approval before any implementation.

After approval, the implementation order should be:

1. Add backend endpoints for gaps 1-3 only.
2. Add Flutter `ApiClient`, `ApiReadingRepository`, and `ApiCollectionRepository`.
3. Replace sync simulation with the real batch sequence.
4. Implement the approved mobile authentication approach.

Do not start step 4 until the authentication decision is explicitly approved.
