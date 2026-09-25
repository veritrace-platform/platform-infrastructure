# ADR-0011: Messaging topology

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

The draft used SSCC-based MQTT topics that anyone could publish to. It had no event envelope and no rules
for keys, retention, or evolution.

## Decision

**MQTT (devices → platform)**

- Topics are device-scoped: `veritrace/v1/devices/{device_id}/telemetry`. ACLs restrict each device to
  its own topic, so one compromised device cannot inject readings for another. The SSCC travels in the
  payload.
- Ingestion uses an MQTT 5 shared subscription (`$share/telemetry-ingest/...`), so several ingest
  instances split the load without duplicating it.
- QoS 1. Duplicates are absorbed by the unique reading key.

**Kafka (service ↔ service)**

- There are four topics: `iot.telemetry.raw`, `iot.telemetry.dlq`, `shipment.events`, and
  `telemetry.incidents`. Topics are created explicitly by infrastructure, and automatic creation is
  disabled.
- Every topic is keyed by SSCC, so all data about one shipment is ordered and handled by one consumer.
- Domain events share one envelope with `event_id`, `event_type`, `event_version`, subject, actor, and
  data. Shipment events also carry the hash-chain fields.
- `shipment.events` and `telemetry.incidents` have unlimited retention, because they are the replay source
  for projections and for M2 anchoring.
- JSON encoding is used, documented in [messaging.md](../contracts/messaging.md). A schema registry is not
  used: there are few producers, and adding one later is possible without changing topics.
- Delivery is at least once. Every consumer is idempotent: it deduplicates on `event_id`, on
  per-shipment `sequence`, or on natural unique keys.
- W3C `traceparent` is propagated in Kafka headers.

**Redis (M2 only)** is used for the relayer's internal job queue and locks
([ADR-0015](0015-gasless-relayer.md)). It is not used for cross-service messaging.

## Consequences

- One broker technology for cross-service events keeps operations simple.
- Unlimited retention needs disk. The volumes are small (events, not readings), and
  `iot.telemetry.raw` keeps a 7-day retention.
- Schema evolution is disciplined by convention and review rather than enforced by a registry.
