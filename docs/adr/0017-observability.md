# ADR-0017: Observability

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

Diagnosing a flow that crosses REST, Kafka, and WebSocket needs correlated logs from day one. M2 adds
metrics and centralized dashboards. The draft named Promtail as the log shipper, but Promtail reached end
of life in 2026 and was superseded by Grafana Alloy.

## Decision

**From M1**

- Structured JSON logs on stdout via `log/slog`. Fields: `time`, `level`, `msg`, `service`, `version`,
  `trace_id`, and, when known, `tenant_id`, `user_id`, `sscc`.
- Access logs record `method`, `route` (the pattern, not the raw path), `status`, `duration_ms`, and
  `bytes`.
- **W3C Trace Context.** An incoming `traceparent` is honored, or a new one is generated. It is
  propagated to Kafka headers and outgoing HTTP calls, and echoed to clients as `X-Trace-Id`.
- Each service exposes `/healthz`, `/readyz`, and `/metrics` on a separate **admin port** that is never
  routed publicly.
- Metrics use `prometheus/client_golang` from the start: Go runtime metrics plus HTTP request
  duration and count by route and status.

**M2**

- A Prometheus server scrapes the admin ports. Domain metrics are added:
  - Kafka consumer lag;
  - readings ingested and rejected;
  - breach detection latency;
  - outbox backlog;
  - relayer queue depth, pending transactions, and speed-ups.
- **Grafana Alloy** collects container logs and ships them to **Loki**.
- **Grafana** provisions one dashboard that combines metrics panels with a live log panel filtered by
  service and trace ID.
- Metric names follow `veritrace_<service>_<subject>_<unit>`, for example
  `veritrace_telemetry_breach_detection_latency_seconds`.

## Consequences

- Any request can be followed across services by `trace_id` in M1 already, without a tracing backend.
- Adding distributed tracing later (OpenTelemetry SDK and Tempo) requires no change to propagation.
