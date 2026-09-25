# ADR-0012: Cold-chain detection engine

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

A breach is a temperature excursion that lasts at least 30 seconds. Readings arrive at least once, may be
duplicated or delayed, and are processed by several consumer instances whose partition assignments change.
An alert must reach users within one second of the confirming reading.

## Decision

- `telemetry-stream-service` runs two roles, in one binary with independently enabled components:
  - **ingest:** MQTT → validation → Kafka `iot.telemetry.raw`;
  - **processor:** Kafka → TimescaleDB, detection, and notification.
- The processor consumes with franz-go using cooperative-sticky rebalancing. For each fetched batch it:
  1. inserts readings with `COPY` into a staging table, then `INSERT … ON CONFLICT DO NOTHING`;
  2. runs the episode state machine per SSCC in memory (rules in
     [cold-chain-monitoring.md](../domain/cold-chain-monitoring.md));
  3. persists incidents and produces to `telemetry.incidents`;
  4. pushes notifications to the WebSocket hub;
  5. commits offsets.
- Offsets are committed only after persistence, which gives at-least-once processing. Incident uniqueness
  on `(sscc, started_at)` makes reprocessing safe.
- On partition revocation, in-memory state for the lost partitions is dropped. State is rebuilt lazily
  from the database.
- A record that fails validation or persistence after 3 retries goes to `iot.telemetry.dlq`.
- The WebSocket hub runs in the same process. Across instances, notifications are fanned out through a
  Kafka consumer group per instance on `telemetry.incidents` and `shipment.events`, so every instance
  delivers to its own connected clients.

## Consequences

- Detection latency is bounded by batch polling (configured at ≤ 200 ms) plus the database write, which
  keeps it well under one second.
- Horizontal scaling works per partition (6 partitions means up to 6 processors).
- Running several instances of the hub requires the per-instance consumer groups described above.
  Documented and implemented from the start, so no redesign is needed later.
