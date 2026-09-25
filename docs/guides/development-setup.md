# Development Setup

## 1. Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| Docker Engine + Compose plugin | Docker 27+, Compose v2.27+ | Everything |
| GNU Make | 4+ | Task shortcuts |
| Go | 1.27 (`GOTOOLCHAIN=auto` downloads it on demand) | Go services |
| Node.js | 22 LTS | Frontends |
| Python + `uv` | 3.13 | IoT simulator (optional; it also runs in Docker) |
| Foundry | latest stable | Smart contracts (M2) |
| GitHub CLI (`gh`) | latest | Optional: pull requests from the terminal |

Clone every repository into one parent directory. The `apps` compose profile relies on this layout:

```
veritrace-platform/
├── platform-infrastructure/
├── core-business-service/
├── telemetry-stream-service/
├── blockchain-relayer-service/
├── smart-contracts/
├── enterprise-dashboard/
├── driver-mobile-pwa/
└── public-trace-portal/
```

## 2. Start the environment

```bash
cd platform-infrastructure
cp .env.example .env        # adjust passwords if you like
make up                     # PostgreSQL, Kafka (+ topics), Mosquitto, Redis, gateway
make ps                     # everything should be healthy
```

`make help` lists all targets. `make reset` deletes all volumes, so local data is lost.

## 3. Ports

Host ports are defaults. If a port is taken, override it in `platform-infrastructure/.env` (for example
`POSTGRES_HOST_PORT=15432`) and use the same port in the services' `.env` files.

| Port | Service |
| --- | --- |
| 8000 | Gateway: single entry point for REST and WebSocket |
| 5432 | PostgreSQL (`veritrace_core`, `veritrace_telemetry`, `veritrace_relayer`) |
| 9092 | Kafka (host listener) |
| 1883 | Mosquitto |
| 6379 | Redis |
| 8080 / 8081 | core-business-service (API / admin) when run on the host |
| 8090 / 8091 | telemetry-stream-service (API / admin) |
| 8100 / 8101 | blockchain-relayer-service (API / admin, M2) |
| 8085 | Kafka UI (`tools` profile) |

## 4. Backend workflow (Go on the host)

```bash
cd core-business-service
cp .env.example .env
make migrate-up             # applies migrations as the owner role
make run                    # serves on :8080, admin on :8081
make test                   # unit tests
make test-integration       # integration tests (needs Docker)
make lint
```

The gateway on `:8000` forwards to services on the host by default.

## 5. Frontend workflow (no Go toolchain)

```bash
cd platform-infrastructure
make up-apps                # also builds and runs the Go services from sibling repositories
```

Point the frontend at `http://localhost:8000`. See [frontend-integration.md](frontend-integration.md).
