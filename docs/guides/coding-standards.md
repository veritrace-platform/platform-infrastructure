# Coding Standards

## 1. General

- English everywhere: identifiers, comments, messages, logs, documentation.
- Comments explain **why**, not what. Exported Go identifiers have doc comments. Do not commit
  commented-out code or unowned `TODO`s. Track follow-ups as issues instead.
- Formatting is automated: `gofmt`/`goimports` for Go, `ruff format` for Python, `forge fmt` for Solidity,
  and `.editorconfig` for everything else.

## 2. Go

- Layout and libraries: [ADR-0004](../adr/0004-go-service-baseline.md).
- **Errors:**
  - Wrap with context: `fmt.Errorf("issue pickup code: %w", err)`.
  - Define domain errors as sentinel values or typed errors in the domain package.
  - Map them to problem codes only in the transport layer.
  - Never `panic` on a request path.
- **Context:** the first parameter of every I/O function is `ctx context.Context`. Do not store contexts
  in structs.
- **Concurrency:** goroutines have an owner and a stop condition (context cancellation or a closed
  channel). The process waits for them on shutdown.
- **Time:** use `time.Time` in UTC. Inject a clock (`func() time.Time`) wherever time affects logic
  (OTP expiry, breach windows), so tests are deterministic.
- **IDs:** database-generated UUIDv7, represented as `uuid.UUID` (`github.com/google/uuid`).
- **Decimals:** temperatures and coordinates are read from `numeric` into `pgtype.Numeric` and converted
  explicitly at the edges. Arithmetic uses `float64` only for geometry (haversine).
- **Tests:**
  - table-driven;
  - `package x_test` for black-box tests of exported behavior;
  - integration tests behind `//go:build integration`, using `testcontainers-go`;
  - no sleeps for synchronization: use channels, `eventually` helpers with deadlines, or injected
    clocks.
- **Naming:** packages are short, lower-case nouns (`shipment`, `gs1`, `tenancy`). Avoid `util`,
  `common`, and `helpers`.

## 3. SQL and migrations

- Conventions follow [data-model.md §1](../architecture/data-model.md#1-conventions).
- Keywords in upper case, identifiers in lower `snake_case`, one column per line in DDL.
- Every table with tenant data has RLS enabled in the migration that creates it, together with its
  policies and grants.
- `sqlc` query files live next to their repository (`internal/<domain>/queries/*.sql`). Queries are named
  `VerbNoun` (`GetShipmentByID`, `ListLotsByProduct`).
- Never build SQL by string concatenation. Session settings use `set_config($1, $2, true)`.

## 4. API

- Follow [rest-api.md](../contracts/rest-api.md) and [ADR-0010](../adr/0010-rest-api-style-and-error-model.md).
- Update `api/openapi.yaml` before or together with the handler. It is validated in CI.

## 5. Python (simulator)

- Python 3.13, `uv` for dependencies (`pyproject.toml` + `uv.lock`), `ruff` (lint and format),
  `pytest`, and type hints on public functions.

## 6. Solidity (M2)

- Solidity 0.8.30, Foundry, OpenZeppelin 5.
- Custom errors instead of revert strings, NatSpec on external functions, events for every state change.
- Foundry unit tests, fuzz tests for Merkle verification, and invariant tests for batch sequencing.
