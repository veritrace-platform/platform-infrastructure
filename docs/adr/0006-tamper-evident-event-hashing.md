# ADR-0006: Tamper-evident event hashing

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

In M2, shipment events and cold-chain incidents are committed on-chain as Merkle roots. For that to work:

- the leaf hashes must be reproducible by anyone who holds the same data;
- history must already be tamper-evident in M1, before any blockchain exists.

Hashing raw JSON is not reproducible, because key order and number formatting vary between serializers.

## Decision

- Event payloads are serialized with **JSON Canonicalization Scheme (RFC 8785)** before they are hashed.
- Each shipment event stores:
  - `event_hash = SHA-256(canonical(event))`, where the canonical event includes the payload, type,
    shipment, actor, timestamp, and `prev_event_hash`;
  - `prev_event_hash`, which points to the previous event of the same shipment. The first event uses
    32 zero bytes.
- Each telemetry incident stores `incident_hash`, computed the same way.
- Hashes are stored as lowercase hex (64 characters). Event tables are append-only for the runtime role.

## Consequences

- Rewriting or deleting any past event breaks the per-shipment chain, which is detectable offline.
- M2 Merkle batching uses these stored hashes directly as leaves.
- Every producer of hashed records must use the same canonicalization. This is covered by shared test
  vectors in `docs/contracts/test-vectors/`, added with SCM-EP2-US05: canonical JSON inputs, expected
  canonical bytes, and expected hashes.
