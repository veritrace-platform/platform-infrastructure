# ADR-0010: REST API style and error model

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

Three services and three client applications must agree on how requests, responses, errors, and
pagination look. The frontend is built in parallel by a separate developer and needs a contract it can
generate types from, before the backend is finished.

## Decision

- **Contract-first OpenAPI 3.1.** Each service keeps `api/openapi.yaml`. An endpoint's schema is merged
  before or together with its implementation. The frontend generates TypeScript types with
  `openapi-typescript` and may mock the API with Prism.
- **No success envelope.** Responses return the resource itself. Collections return
  `{ "items": [...], "next_cursor": ... }`.
- **Errors use RFC 9457 Problem Details**, extended with a stable machine-readable `code`, a `trace_id`,
  and per-field `errors[]`. Codes are listed in [rest-api.md](../contracts/rest-api.md#11-errors-rfc-9457-problem-details).
- **Cursor pagination** over UUIDv7 or time ordering. It stays stable while rows are inserted, and it
  performs the same at any depth.
- **Commands as `POST` sub-resources** for state transitions (`/pickup`, `/delivery`, `/recall`). This
  keeps each business action explicit and auditable, instead of hiding it behind a generic
  `PATCH status`.
- **Non-disclosure:** resources outside the caller's visibility return `404`, never `403`.
- **Retries:** commands are safe to retry. A repeated transition fails with `409` and does not apply twice.
  Creation endpoints are not idempotent, so clients must not blindly retry a `POST /shipments`.

## Consequences

- Error handling in clients is uniform: branch on `code`.
- The draft's `{success, data}` wrapper is dropped. Frontend code relies on HTTP status plus the problem
  document instead.
- The OpenAPI documents must be kept exact. CI lints them.
