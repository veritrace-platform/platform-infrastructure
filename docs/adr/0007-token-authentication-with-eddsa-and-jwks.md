# ADR-0007: Token authentication with EdDSA and JWKS

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

`core-business-service` authenticates users, but `telemetry-stream-service` (its WebSocket hub) and later
the relayer must also verify them. Sharing an HMAC secret across services means any service could mint
tokens.

## Decision

- The core service signs access tokens with **Ed25519 (EdDSA)** and publishes its public keys at
  `GET /.well-known/jwks.json`. Keys carry a `kid` so they can be rotated.
- Access tokens are short-lived (15 minutes) and carry `sub` (user), `tid` (tenant), `role`, `iat`, `exp`,
  and `jti`.
- Refresh tokens are opaque random values. They are stored as hashes, rotated on every use, and revoked
  when reuse is detected.
- Other services verify tokens with the cached JWKS and never hold signing keys.
- Browsers cannot set headers on WebSocket connections, so WebSocket clients present the access token in
  the `Sec-WebSocket-Protocol` header. It is never passed in the query string, because query strings end
  up in logs.

## Consequences

- Only the core service can issue tokens. Verification is local and fast everywhere else.
- Revoking an access token takes effect when it expires (at most 15 minutes). Disabling a user takes
  effect at the next refresh.
