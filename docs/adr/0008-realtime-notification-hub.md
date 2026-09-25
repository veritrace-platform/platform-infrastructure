# ADR-0008: Real-time notification hub

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

The dashboard and the driver PWA need push notifications for:

- cold-chain breaches, detected in the telemetry service;
- emergency recalls, decided in the core service.

Each notification must reach only the tenants that participate in the affected shipment. The breach
detector also needs each shipment's temperature bounds, but it must not query the core database
(see ADR-0003).

## Decision

- `telemetry-stream-service` hosts the single WebSocket endpoint for real-time notifications.
- It consumes `shipment.events` into a local **shipment projection** keyed by SSCC. The projection holds:
  - the participant tenant IDs,
  - the assigned driver,
  - the temperature bounds,
  - the current status.
- Breach incidents and recall events are routed through the projection. A connection receives an event
  only if its tenant is a participant, and a driver connection only for the shipments assigned to that
  driver.
- Incidents are also produced to the `telemetry.incidents` topic for downstream consumers such as M2
  Merkle batching.

## Consequences

- Frontends open one WebSocket connection, with one authentication scheme.
- The projection is eventually consistent. Telemetry for an SSCC that is not yet known is stored but not
  evaluated until the shipment appears.
- If the projection is lost, it can be rebuilt by replaying `shipment.events`, which therefore needs a
  long retention period (or compaction with snapshots).
