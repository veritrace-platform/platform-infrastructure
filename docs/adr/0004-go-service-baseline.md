# ADR-0004: Go service baseline

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

The three Go services should look alike so knowledge and tooling carry over. Tenant isolation depends on
every query running inside an explicit transaction with tenant context. An ORM that hides connection and
transaction handling makes that easy to get wrong.

## Decision

| Concern | Choice | Reason |
| --- | --- | --- |
| Language | Go 1.27 (`go` directive in `go.mod`, same version in CI and Docker) | Current stable release; supported through the project horizon |
| HTTP | `net/http` + `go-chi/chi/v5` | Standard-library handlers; composable middleware |
| PostgreSQL | `jackc/pgx/v5` with `pgxpool` | Native protocol, explicit transactions, `COPY` |
| Queries | `sqlc` (pgx/v5 output) | Type-safe Go generated from hand-written SQL |
| Migrations | `pressly/goose/v3`, embedded SQL | See ADR-0003 |
| Configuration | Environment variables → typed struct (`caarlos0/env/v11`), validated at startup | Twelve-factor; fail fast |
| Logging | `log/slog` JSON | Standard library |
| Metrics | `prometheus/client_golang` | See ADR-0017 |
| Kafka | `twmb/franz-go` | Pure Go, idempotent producer, cooperative rebalancing |
| MQTT | `eclipse/paho.golang` (`autopaho`) | MQTT 5 shared subscriptions |
| Redis | `redis/go-redis/v9` | M2 relayer |
| WebSocket | `coder/websocket` | Context-aware, minimal |
| JWT | `golang-jwt/jwt/v5` (EdDSA) | See ADR-0007 |
| Password hashing | `golang.org/x/crypto/argon2` (Argon2id, m=19 MiB, t=2, p=1) | OWASP baseline |
| Canonical JSON | RFC 8785 implementation `github.com/gowebpki/jcs` | See ADR-0006 |
| Ethereum | `ethereum/go-ethereum` | M2 relayer |
| Tests | `testing`, `testcontainers-go` | Real PostgreSQL, Kafka, and Mosquitto in integration tests |
| Lint | `golangci-lint` v2 (config in each repo) | |
| Vulnerabilities | `govulncheck` in CI | |

Repository layout:

```
cmd/<service>/main.go       # entry point: subcommands `serve` and `migrate`
internal/<domain>/          # domain packages: model, service, repository interfaces, adapters
internal/platform/          # config, logging, database, HTTP server, admin server, trace context
migrations/                 # goose SQL migrations (embedded)
api/openapi.yaml            # REST contract
```

Rules:

- Handlers depend on service interfaces, and services depend on repository interfaces. Interfaces are
  declared where they are consumed, and implementations are wired in `main`.
- Tenant-scoped database access goes through a single `WithTenantTx(ctx, tenantID, fn)` helper.
  Repositories never open transactions themselves.
- Integration tests use the build tag `integration` and run in CI.

## Consequences

- SQL stays visible and reviewable. `sqlc` removes the boilerplate without hiding what runs.
- The single transaction helper is the one place to audit for tenant isolation.
- There are more libraries than a batteries-included framework, but each does one job.
