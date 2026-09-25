# ADR-0003: Service-owned databases and migrations

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

Keeping all DDL in the infrastructure repository would force every feature to change two repositories and
would separate the schema from the code that depends on it. Letting services read each other's tables
couples their release cycles and hides dependencies.

## Decision

- **PostgreSQL 18** everywhere. It provides native `uuidv7()`. The telemetry database adds TimescaleDB.
- Each service owns a **separate database** with a single application schema:

  | Service | Database | Schema |
  | --- | --- | --- |
  | core-business-service | `veritrace_core` | `core` |
  | telemetry-stream-service | `veritrace_telemetry` | `telemetry` |
  | blockchain-relayer-service (M2) | `veritrace_relayer` | `relayer` |

- **Migrations:**
  - plain SQL files managed with **goose**;
  - stored in the service's `migrations/` directory and embedded in the binary;
  - applied by the service's `migrate` subcommand, run as the owner role;
  - goose tracks versions in `public.goose_db_version`.
- **Migration rules:**
  - Files are named `NNNNN_description.sql`, numbered sequentially.
  - Every migration has a working `Down` section for local use.
  - A migration that has been merged is never edited; changes are made in a new migration.
  - Destructive changes use expand–contract across releases.
- **Infrastructure bootstrap** (in `platform-infrastructure`) creates only what services cannot create
  themselves:
  - databases;
  - owner and runtime login roles, with passwords from the environment;
  - the TimescaleDB extension, which requires superuser.

  The first migration of each service creates its schema, grants, and default privileges.
- **Local development:** one PostgreSQL server built from the TimescaleDB image hosts all databases.
  Production may separate them without code changes.
- Services exchange data through REST and Kafka only.

## Consequences

- Schema and code change together in one reviewable pull request.
- Services that need another service's data maintain event-driven projections and handle eventual
  consistency.
- No cross-database foreign keys exist. Cross-service references are natural keys (SSCC), validated at
  the boundary.
