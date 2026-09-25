# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

VeriTrace is split across several repositories and will change over a long development period. Decisions
that live only in chat threads or in people's heads get lost. Cross-repository concerns also need one home.

## Decision

- Keep product and cross-repository documentation in `platform-infrastructure/docs/`.
- Record significant decisions as numbered ADRs in `docs/adr/`.
- Keep executable contracts next to the code that implements them:
  - SQL migrations in the owning service
  - the OpenAPI document in `core-business-service`
- Documentation describes intent and rules. It does not duplicate DDL or the full API.

## Consequences

- Reviewers can trace why a design exists.
- Changing a decision means writing a superseding ADR, which costs a little effort on purpose.
- Contracts cannot drift silently between prose and code, because each concern has one source of truth.
