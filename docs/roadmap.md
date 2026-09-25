# Roadmap

## Milestones

| Milestone | Theme | Epics | Status |
| --- | --- | --- | --- |
| **M1 — Operational Core** | Multi-tenant WMS/TMS on GS1 identifiers with real-time cold-chain monitoring | EP0–EP3 | In progress |
| **M2 — Decentralized Trust** | Encrypted documents, on-chain commitments, public verification, operations | EP4–EP7 | Planned |

**Status values:** `TODO` · `IN_PROGRESS` · `BLOCKED` · `DONE`. A story is `DONE` when it meets the
[Definition of Done](guides/engineering-workflow.md#4-definition-of-done).

**Owners:** **BE** means backend and platform; **FE** means frontend. The story IDs are used in branch
names and commit footers.

---

## M1 — Operational Core

### EP0 — Platform foundation

| ID | Story | Repos | Owner | Status |
| --- | --- | --- | --- | --- |
| SCM-EP0-US01 | Architecture, domain rules, contracts, and ADRs for both milestones | platform-infrastructure | BE | DONE |
| SCM-EP0-US02 | Local environment: pinned compose stack, database bootstrap, Kafka topics, MQTT auth, gateway | platform-infrastructure | BE | DONE |
| SCM-EP0-US03 | Go service skeleton: config, logging, trace context, problem responses, admin server, graceful shutdown, migrations, Docker image, CI | core-business-service, telemetry-stream-service | BE | DONE |
| SCM-EP0-US04 | Organization-wide contribution files and repository hygiene | .github, all | BE | DONE |

### EP1 — Multi-tenancy, identity, and access control

| ID | Story | Repos | Owner | Status |
| --- | --- | --- | --- | --- |
| SCM-EP1-US01 | Tenant isolation foundation: tenant transaction helper, `SECURITY DEFINER` conventions, RLS isolation test harness | core-business-service | BE | TODO |
| SCM-EP1-US02 | Tenant registration with company prefix, headquarters GLN, and first admin | core-business-service | BE | TODO |
| SCM-EP1-US03 | Authentication: login, EdDSA access tokens, rotating refresh tokens, logout, JWKS, rate limiting | core-business-service | BE | TODO |
| SCM-EP1-US04 | User management and own-password change | core-business-service | BE | TODO |
| SCM-EP1-US05 | Access control policy function (per-action party, role, state, and context) | core-business-service | BE | TODO |
| SCM-EP1-US06 | Registration, login, session handling, and user management screens | enterprise-dashboard | FE | TODO |

### EP2 — GS1 warehouse and transport management

| ID | Story | Repos | Owner | Status |
| --- | --- | --- | --- | --- |
| SCM-EP2-US01 | GS1 library: Modulo 10, key validation with prefix ownership, SSCC issuance | core-business-service | BE | TODO |
| SCM-EP2-US02 | Location catalog (GLN, geo-fence) and GLN/tenant directory lookups | core-business-service | BE | TODO |
| SCM-EP2-US03 | Product catalog (GTIN-14, temperature bounds) | core-business-service | BE | TODO |
| SCM-EP2-US04 | Lot commissioning and inventory ledger (balances, movements) | core-business-service | BE | TODO |
| SCM-EP2-US05 | Shipment event log (RFC 8785, hash chain), outbox relay to `shipment.events`, integrity endpoint | core-business-service | BE | TODO |
| SCM-EP2-US06 | Shipment creation (SSCC, participants, snapshots, allocation), carrier and driver assignment, cancellation | core-business-service | BE | TODO |
| SCM-EP2-US07 | Pickup handover: pickup code issuance and confirmation with SSCC scan and origin geo-fence | core-business-service | BE | TODO |
| SCM-EP2-US08 | Transit checkpoints and delivery confirmation with destination geo-fence | core-business-service | BE | TODO |
| SCM-EP2-US09 | Emergency lot recall across tenants with operational lock | core-business-service | BE | TODO |
| SCM-EP2-US10 | Catalog, lot, inventory, shipment, delivery, and recall screens with GS1 barcode rendering | enterprise-dashboard | FE | TODO |
| SCM-EP2-US11 | Driver flows: assignments, camera SSCC scan, pickup code entry, checkpoints, GPS capture | driver-mobile-pwa | FE | TODO |

### EP3 — Real-time cold-chain monitoring

| ID | Story | Repos | Owner | Status |
| --- | --- | --- | --- | --- |
| SCM-EP3-US01 | IoT fleet simulator with scripted scenarios (normal, short excursion, sustained breach, sensor gap) | platform-infrastructure | BE | TODO |
| SCM-EP3-US02 | MQTT ingestion (shared subscription, validation) → `iot.telemetry.raw` | telemetry-stream-service | BE | TODO |
| SCM-EP3-US03 | Reading persistence: hypertable, idempotent batch insert, 15-minute continuous aggregate, dead-letter topic | telemetry-stream-service | BE | TODO |
| SCM-EP3-US04 | Shipment projection from `shipment.events` | telemetry-stream-service | BE | TODO |
| SCM-EP3-US05 | Breach detection engine: episodes, incidents with hashes, `telemetry.incidents` | telemetry-stream-service | BE | TODO |
| SCM-EP3-US06 | WebSocket notification hub: breaches, recalls, live reading subscriptions | telemetry-stream-service | BE | TODO |
| SCM-EP3-US07 | Telemetry read API: readings and incidents | telemetry-stream-service | BE | TODO |
| SCM-EP3-US08 | Live temperature charts and alert center | enterprise-dashboard, driver-mobile-pwa | FE | TODO |

---

## M2 — Decentralized Trust

### EP4 — Encrypted document vault

| ID | Story | Repos | Owner | Status |
| --- | --- | --- | --- | --- |
| SCM-EP4-US01 | `VTENC1` envelope encryption module and `BlobStore` (Kubo locally, Pinata deployed) | core-business-service | BE | TODO |
| SCM-EP4-US02 | Document upload: type and size checks, plaintext SHA-256, pinning, `shipment.document_attached` | core-business-service | BE | TODO |
| SCM-EP4-US03 | Authorized streaming decryption | core-business-service | BE | TODO |
| SCM-EP4-US04 | Inspector role and inspector participants | core-business-service | BE | TODO |
| SCM-EP4-US05 | Document vault UI | enterprise-dashboard | FE | TODO |

### EP5 — On-chain commitments and gasless relayer

| ID | Story | Repos | Owner | Status |
| --- | --- | --- | --- | --- |
| SCM-EP5-US01 | `SupplyChainTraceability` contract, Foundry tests, Amoy deployment script | smart-contracts | BE | TODO |
| SCM-EP5-US02 | Relayer skeleton, leaf ingestion from Kafka, Merkle batcher, proofs, manifest pinning | blockchain-relayer-service | BE | TODO |
| SCM-EP5-US03 | Redis Stream job queue, nonce lock, signing and broadcast worker | blockchain-relayer-service | BE | TODO |
| SCM-EP5-US04 | Stuck-transaction speed-up tracker | blockchain-relayer-service | BE | TODO |
| SCM-EP5-US05 | Chain indexer with finality tracking | blockchain-relayer-service | BE | TODO |
| SCM-EP5-US06 | Proof API (public and authenticated) | blockchain-relayer-service | BE | TODO |

### EP6 — Public verification and anti-counterfeiting

| ID | Story | Repos | Owner | Status |
| --- | --- | --- | --- | --- |
| SCM-EP6-US01 | Label signing keys, label series, and Digital Link URIs | core-business-service | BE | TODO |
| SCM-EP6-US02 | Public scan verification with verdicts and impossible-travel detection | core-business-service | BE | TODO |
| SCM-EP6-US03 | Public timeline API (core) and public telemetry summary (telemetry) | core-business-service, telemetry-stream-service | BE | TODO |
| SCM-EP6-US04 | Label series management and QR printing | enterprise-dashboard | FE | TODO |
| SCM-EP6-US05 | Public portal: verdict, timeline, temperature chart, on-chain proof links | public-trace-portal | FE | TODO |

### EP7 — Observability and deployment

| ID | Story | Repos | Owner | Status |
| --- | --- | --- | --- | --- |
| SCM-EP7-US01 | Domain metrics (lag, detection latency, outbox backlog, relayer queue) | Go services | BE | TODO |
| SCM-EP7-US02 | Prometheus, Alloy, Loki, and Grafana with a unified dashboard (`observability` profile) | platform-infrastructure | BE | TODO |
| SCM-EP7-US03 | Release pipelines: images to GHCR on tag | Go services | BE | TODO |
| SCM-EP7-US04 | VM deployment: production compose overrides, Caddy TLS, backups, SSH deploy workflow | platform-infrastructure | BE | TODO |
| SCM-EP7-US05 | Frontend deployments on Vercel | frontends | FE | TODO |
