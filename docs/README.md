# VeriTrace Documentation

Product and engineering documentation for the VeriTrace platform. It is the reference for the whole
`veritrace-platform` organization. Each service repository documents only its own internals.

## Start here

1. [Architecture overview](architecture/overview.md): what the system is and how the pieces fit together.
2. [Roadmap](roadmap.md): milestones, epics, stories, and their status.
3. [Development setup](guides/development-setup.md): run everything locally.

## Contents

| Section | Documents |
| --- | --- |
| **Architecture** | [Overview](architecture/overview.md) · [Data model](architecture/data-model.md) · [Security](architecture/security.md) |
| **Domain rules** | [GS1 identifiers](domain/gs1-identifiers.md) · [Lots, inventory and shipment lifecycle](domain/shipment-lifecycle.md) · [Access control](domain/access-control.md) · [Cold-chain monitoring](domain/cold-chain-monitoring.md) · [Public verification (M2)](domain/public-verification.md) |
| **Contracts** | [REST API](contracts/rest-api.md) · [Messaging: MQTT, Kafka, WebSocket](contracts/messaging.md) · [Smart contract (M2)](contracts/smart-contract.md) |
| **Decisions** | [Architecture decision records](adr/README.md) |
| **Guides** | [Development setup](guides/development-setup.md) · [Engineering workflow](guides/engineering-workflow.md) · [Coding standards](guides/coding-standards.md) · [Frontend integration](guides/frontend-integration.md) |

## Sources of truth

| Concern | Location |
| --- | --- |
| Database schema | SQL migrations in the owning service (`migrations/`), designed in [data-model.md](architecture/data-model.md) |
| REST API | `api/openapi.yaml` in each service, following [rest-api.md](contracts/rest-api.md) |
| Messaging | [messaging.md](contracts/messaging.md) |
| Smart contract ABI | `smart-contracts` build artifacts, following [smart-contract.md](contracts/smart-contract.md) |

Code and documentation must agree. A change to one updates the other in the same pull request.
