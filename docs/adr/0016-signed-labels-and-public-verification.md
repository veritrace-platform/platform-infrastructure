# ADR-0016: Signed labels and public verification (M2)

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

The draft put one signed URI per lot and SSCC on labels, and verified the HMAC in the edge runtime of the
portal. This has three problems:

- Every unit in a lot would carry the same code, so copies are indistinguishable from originals.
- SSCCs identify pallets, not consumer units.
- Verifying at the edge requires shipping tenant secrets to the frontend.

## Decision

- Labels carry a **per-unit serial** (GS1 AI 21) and a truncated HMAC-SHA256 signature over
  `GTIN|LOT|SERIAL` with a versioned per-tenant key. The details are in
  [public-verification.md](../domain/public-verification.md).
- **Verification happens only in core-business-service.** The portal is a presentation layer that calls
  the public API. Keys never leave the backend, and they are stored wrapped by the master key.
- Duplicate detection uses scan history per serial: impossible travel faster than 900 km/h, or more than
  20 scans in 24 hours.
- Public endpoints are unauthenticated, rate-limited per IP, and read only the public projections exposed
  through `SECURITY DEFINER` functions.

## Consequences

- Copied labels become detectable once the copies are scanned in different places.
- Label issuance scales to large series without storing every label.
- Location-based checks depend on consumer consent to geolocation. Without it, only the frequency rule
  applies.
