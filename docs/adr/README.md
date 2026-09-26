# Architecture Decision Records

Each ADR records one significant decision: its context, the choice made, and its consequences. An accepted
ADR is not rewritten. To change a decision, add a new ADR that supersedes it and set the old one's status
to `Superseded by ADR-XXXX`.

| ADR | Title | Scope |
| --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Process |
| [0002](0002-multi-party-tenancy-with-row-level-security.md) | Multi-party tenancy with row-level security | M1 |
| [0003](0003-service-owned-databases-and-migrations.md) | Service-owned databases and migrations | M1 |
| [0004](0004-go-service-baseline.md) | Go service baseline | M1 |
| [0005](0005-transactional-outbox-for-domain-events.md) | Transactional outbox for domain events | M1 |
| [0006](0006-tamper-evident-event-hashing.md) | Tamper-evident event hashing | M1 |
| [0007](0007-token-authentication-with-eddsa-and-jwks.md) | Token authentication with EdDSA and JWKS | M1 |
| [0008](0008-realtime-notification-hub.md) | Real-time notification hub | M1 |
| [0009](0009-access-control-policy-model.md) | Access control policy model | M1 |
| [0010](0010-rest-api-style-and-error-model.md) | REST API style and error model | M1 |
| [0011](0011-messaging-topology.md) | Messaging topology | M1 |
| [0012](0012-cold-chain-detection-engine.md) | Cold-chain detection engine | M1 |
| [0013](0013-document-vault-encryption.md) | Document vault encryption | M2 |
| [0014](0014-on-chain-commitments.md) | On-chain commitments | M2 |
| [0015](0015-gasless-relayer.md) | Gasless relayer and chain indexer | M2 |
| [0016](0016-signed-labels-and-public-verification.md) | Signed labels and public verification | M2 |
| [0017](0017-observability.md) | Observability | M1 + M2 |
| [0018](0018-deployment-topology.md) | Deployment topology and cost | M1 + M2 |
| [0019](0019-local-development-environment.md) | Local development environment | M1 |

New ADRs start from [the template](template.md). All ADRs above are `Accepted` unless marked otherwise.
