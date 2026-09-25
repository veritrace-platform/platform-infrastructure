# REST API Contract

The rationale behind these conventions is in [ADR-0010](../adr/0010-rest-api-style-and-error-model.md).
Request and response schemas live in each service's OpenAPI document, which is the executable contract:

| Service | OpenAPI document |
| --- | --- |
| core-business-service | `api/openapi.yaml` |
| telemetry-stream-service | `api/openapi.yaml` |
| blockchain-relayer-service (M2) | `api/openapi.yaml` |

## 1. Conventions

| Topic | Rule |
| --- | --- |
| Base URL | One origin through the gateway. Local: `http://localhost:8000`. |
| Versioning | Path prefix `/api/v1`. Breaking changes require `/api/v2`. |
| Format | `application/json; charset=utf-8`, `snake_case` fields. `null` means an explicitly empty optional field; optional fields may also be omitted. |
| Identifiers | UUID strings. GS1 keys are strings, never numbers. |
| Time | RFC 3339 UTC timestamps; `YYYY-MM-DD` dates |
| Numbers | Temperatures and coordinates are JSON numbers. Temperatures have at most 2 decimals, coordinates at most 6. |
| Authentication | `Authorization: Bearer <access_token>` (EdDSA JWT, [ADR-0007](../adr/0007-token-authentication-with-eddsa-and-jwks.md)) |
| Collections | `GET` returns `{ "items": [...], "next_cursor": "opaque" \| null }`. Query `limit` defaults to 20 (max 100); pass `cursor` for the next page. Items are ordered newest first unless stated otherwise. |
| Creation | `201 Created`, a `Location` header, and the created resource in the body |
| Commands | State-changing actions are `POST` sub-resources (for example `/shipments/{id}/pickup`) that return the updated resource |
| Partial update | `PATCH` with a JSON merge patch (RFC 7396) of the mutable fields |
| Tracing | Clients may send `traceparent`. Every response carries `X-Trace-Id`. |
| Limits | JSON bodies up to 1 MiB. Document uploads up to 25 MiB (M2). |
| Rate limits | Login and registration: 10/min per IP. Public endpoints: 60/min per IP. `429` responses include `Retry-After`. |

### 1.1 Errors (RFC 9457 Problem Details)

`Content-Type: application/problem+json`

```json
{
  "type": "about:blank",
  "title": "Unprocessable Content",
  "status": 422,
  "code": "INVALID_GS1_IDENTIFIER",
  "detail": "gtin has an invalid check digit",
  "instance": "/api/v1/products",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "errors": [
    { "field": "gtin", "code": "CHECK_DIGIT", "message": "expected check digit 8" }
  ]
}
```

Clients branch on `code`, never on `detail` or `title`.

| Code | HTTP | Meaning |
| --- | --- | --- |
| `VALIDATION_FAILED` | 400 | Malformed JSON, missing or invalid fields (`errors[]` lists them) |
| `UNAUTHENTICATED` | 401 | Missing or invalid access token |
| `TOKEN_EXPIRED` | 401 | Access token expired; refresh and retry |
| `INVALID_CREDENTIALS` | 401 | Login failed. The message is the same for unknown email and wrong password. |
| `REFRESH_TOKEN_INVALID` | 401 | Refresh token unknown, expired, revoked, or reused (reuse revokes the family) |
| `FORBIDDEN` | 403 | Visible resource, action not permitted |
| `NOT_FOUND` | 404 | Resource does not exist or is not visible to the caller |
| `METHOD_NOT_ALLOWED` | 405 | Route exists but does not support the HTTP method |
| `IDENTIFIER_ALREADY_REGISTERED` | 409 | Unique key taken (GLN, GTIN, GCP, tax code, tenant code, email, lot number) |
| `INVALID_STATE_TRANSITION` | 409 | Command not allowed in the current status |
| `SHIPMENT_RECALLED_LOCKED` | 409 | Command on a recalled shipment |
| `LOT_RECALLED` | 409 | New shipment or label series for a recalled lot |
| `INSUFFICIENT_STOCK` | 409 | Origin balance lower than the requested quantity |
| `SSCC_SERIAL_EXHAUSTED` | 409 | The tenant's SSCC serial space is used up |
| `INVALID_GS1_IDENTIFIER` | 422 | Length, non-numeric, check digit, or prefix mismatch (see `errors[].code`) |
| `SSCC_MISMATCH` | 422 | Scanned SSCC differs from the shipment |
| `OUTSIDE_GEOFENCE` | 422 | Reported position outside the facility geo-fence |
| `PICKUP_CODE_INVALID` | 422 | Wrong code (consumes one attempt) |
| `PICKUP_CODE_EXPIRED` | 422 | No active code, or code expired |
| `PICKUP_CODE_LOCKED` | 423 | Attempt limit reached; a new code must be issued |
| `PAYLOAD_TOO_LARGE` | 413 | Body over the limit |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Wrong `Content-Type` or document type |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unexpected failure (details only in logs, correlated by `trace_id`) |
| `SERVICE_UNAVAILABLE` | 503 | Dependency down or shutting down |

## 2. Gateway routing

| Path prefix | Service |
| --- | --- |
| `/ws/` | telemetry-stream-service |
| `/api/v1/telemetry/`, `/api/v1/public/telemetry/` | telemetry-stream-service |
| `/api/v1/proofs/`, `/api/v1/public/proofs/`, `/api/v1/public/batches/` | blockchain-relayer-service (M2) |
| `/.well-known/jwks.json`, everything else under `/api/v1/` | core-business-service |

## 3. Endpoint inventory

Roles and parties follow [access-control.md](../domain/access-control.md).

### 3.1 core-business-service (M1)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/tenants` | public | Register a tenant with its headquarters location and first admin |
| `POST` | `/api/v1/auth/login` | public | Email and password → access token and refresh token |
| `POST` | `/api/v1/auth/refresh` | public | Rotate the refresh token and issue a new access token |
| `POST` | `/api/v1/auth/logout` | public | Revoke a refresh token family |
| `GET` | `/.well-known/jwks.json` | public | Token verification keys |
| `GET` | `/api/v1/me` | bearer | Current user and tenant summary |
| `POST` | `/api/v1/me/password` | bearer | Change own password (revokes other sessions) |
| `GET`, `PATCH` | `/api/v1/tenant` | bearer | Read or update own tenant profile |
| `GET`, `POST` | `/api/v1/users` | ADMIN | List (filter: `role`, `is_active`) or create users |
| `GET`, `PATCH` | `/api/v1/users/{user_id}` | ADMIN | Read or update a user (name, phone, role, `is_active`) |
| `GET` | `/api/v1/directory/locations/{gln}` | bearer | Resolve any tenant's GLN to its public fields |
| `GET` | `/api/v1/directory/tenants/{code}` | bearer | Resolve a tenant code (carrier or inspector selection) |
| `GET`, `POST` | `/api/v1/locations` | bearer | List or create locations |
| `GET`, `PATCH` | `/api/v1/locations/{location_id}` | bearer | Read or update a location |
| `GET`, `POST` | `/api/v1/products` | bearer | List (filter: `q`, `is_active`) or create products |
| `GET`, `PATCH` | `/api/v1/products/{product_id}` | bearer | Read or update a product |
| `GET`, `POST` | `/api/v1/lots` | bearer | List (filter: `product_id`, `status`) or commission lots |
| `GET` | `/api/v1/lots/{lot_id}` | bearer | Read a lot |
| `POST` | `/api/v1/lots/{lot_id}/recall` | ADMIN | Emergency recall; returns the recall and the affected shipment count |
| `GET` | `/api/v1/inventory` | bearer | Balances (filter: `location_id`, `lot_id`) |
| `GET`, `POST` | `/api/v1/shipments` | bearer | List (filter: `status`, `party`, `sscc`, `lot_id`, `assigned_to_me`) or create shipments |
| `GET` | `/api/v1/shipments/{shipment_id}` | bearer | Read a shipment, including participants |
| `POST` | `/api/v1/shipments/{shipment_id}/carrier` | bearer | Assign a carrier tenant |
| `POST` | `/api/v1/shipments/{shipment_id}/driver` | bearer | Assign or reassign a driver |
| `POST` | `/api/v1/shipments/{shipment_id}/pickup-code` | bearer | Issue a pickup code (returned once) |
| `POST` | `/api/v1/shipments/{shipment_id}/pickup` | DRIVER | Confirm pickup (`sscc`, `code`, `position`) |
| `POST` | `/api/v1/shipments/{shipment_id}/checkpoints` | DRIVER | Record a transit checkpoint (`sscc`, `gln`, `position`) |
| `POST` | `/api/v1/shipments/{shipment_id}/delivery` | bearer | Confirm delivery (`sscc`, `position`) |
| `POST` | `/api/v1/shipments/{shipment_id}/cancel` | bearer | Cancel (`reason`) |
| `GET` | `/api/v1/shipments/{shipment_id}/events` | bearer | Event log with hashes, oldest first |
| `GET` | `/api/v1/shipments/{shipment_id}/integrity` | bearer | Recompute the hash chain: `{valid, event_count, head_hash, first_invalid_sequence}` |

### 3.2 core-business-service (M2)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/shipments/{shipment_id}/participants` | ADMIN | Add an inspector tenant |
| `GET`, `POST` | `/api/v1/shipments/{shipment_id}/documents` | bearer | List documents, or upload one (`multipart/form-data`: `file`, `document_type`) |
| `GET` | `/api/v1/documents/{document_id}` | bearer | Document metadata |
| `GET` | `/api/v1/documents/{document_id}/content` | bearer | Streamed decrypted content; `X-Content-SHA256` header |
| `GET`, `POST` | `/api/v1/lots/{lot_id}/label-series` | bearer | List series, or issue one (`label_count`) |
| `GET` | `/api/v1/lots/{lot_id}/label-series/{series_id}/labels` | bearer | Paginated `{serial, digital_link_uri}` for printing |
| `POST` | `/api/v1/public/scans` | public | Verify a scanned label and return the verdict and lot summary |
| `GET` | `/api/v1/public/lots/{gtin}/{lot_number}` | public | Public timeline ([public-verification.md §5](../domain/public-verification.md#5-public-timeline-content)) |

### 3.3 telemetry-stream-service

| Milestone | Method | Path | Auth | Purpose |
| --- | --- | --- | --- | --- |
| M1 | `GET` | `/api/v1/telemetry/shipments/{sscc}/readings` | bearer | Readings in `[from, to)`. `resolution` is `raw` (max 6 h window), `1m`, or `15m`. |
| M1 | `GET` | `/api/v1/telemetry/shipments/{sscc}/incidents` | bearer | Incidents of one shipment |
| M1 | `GET` | `/api/v1/telemetry/incidents` | bearer | Incidents across the caller's shipments (filter: `state=open\|resolved`) |
| M1 | `GET` | `/ws/v1/notifications` | subprotocol | WebSocket ([messaging.md §6](messaging.md#6-websocket-real-time-notifications)) |
| M2 | `GET` | `/api/v1/public/telemetry/shipments/{sscc}/summary` | public | 15-minute series and incident summary for the public timeline |

### 3.4 blockchain-relayer-service (M2)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/public/proofs/{leaf_hash}` | public | `{leaf_hash, status, batch_id, merkle_root, proof[], tx_hash, block_number, chain_id, contract_address, manifest_cid}` |
| `GET` | `/api/v1/public/batches/{batch_id}` | public | Batch metadata |
| `GET` | `/api/v1/proofs/status` | bearer | Anchoring status for a list of hashes (dashboard badges) |

## 4. Operational endpoints (every service, admin port only)

These endpoints are never routed through the gateway.

| Path | Purpose |
| --- | --- |
| `GET /healthz` | Liveness: the process is serving |
| `GET /readyz` | Readiness: dependencies (database, brokers) reachable |
| `GET /metrics` | Prometheus exposition |
