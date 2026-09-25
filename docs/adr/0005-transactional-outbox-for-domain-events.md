# ADR-0005: Transactional outbox for domain events

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

Other components react to shipment state changes:

- real-time notifications,
- the telemetry service's shipment projection,
- Merkle batching in M2.

Writing to PostgreSQL and then publishing to Kafka as two separate steps loses events if the process
crashes in between. It can also publish an event for a transaction that rolled back.

## Decision

- Every state-changing transaction in `core-business-service` inserts its domain event into an `outbox`
  table **in the same transaction**.
- A relay worker inside the service reads unpublished rows in order and produces them to Kafka with an
  idempotent producer. It then marks the rows as published.
- Consumers treat delivery as **at-least-once** and deduplicate on `event_id`.
- The Kafka topic is `shipment.events`, keyed by SSCC so that each shipment's events stay ordered.

## Consequences

- A state change and its event are atomic.
- Events reach Kafka slightly after the commit, and consumers must be idempotent.
- The outbox table needs periodic cleanup of rows that have already been published.
