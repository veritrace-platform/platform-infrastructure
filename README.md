# platform-infrastructure

Runtime infrastructure for the VeriTrace platform:

- **Local environment:** a Docker Compose stack with pinned versions of PostgreSQL 18 + TimescaleDB,
  Kafka (KRaft), Mosquitto, Redis, and a Caddy gateway.
- **Bootstrap:** per-service databases and least-privilege roles, Kafka topics, and MQTT credentials
  and ACLs.

Project documentation (architecture, domain rules, contracts, decisions, roadmap, guides) lives in the
project home repository, [`veritrace`](https://github.com/veritrace-platform/veritrace).

## Quick start

```bash
make up        # creates .env from .env.example on first run, then starts the stack
make ps
```

| Endpoint | Address |
| --- | --- |
| Gateway (REST + WebSocket) | `http://localhost:8000` |
| PostgreSQL | `localhost:5432`, databases `veritrace_core`, `veritrace_telemetry`, `veritrace_relayer` |
| Kafka | `localhost:9092` |
| MQTT | `localhost:1883` |
| Redis | `localhost:6379` |

Every host port can be changed in `.env`. When `.env.example` gains variables, the next `make up` (or
`up-apps`, `up-tools`) adds them to `.env` with their example values and keeps the values you changed. Run
`make help` for all targets, and see the
[development setup guide](https://github.com/veritrace-platform/veritrace/blob/main/docs/guides/development-setup.md)
for the full workflow.

## Profiles

| Command | Adds |
| --- | --- |
| `make up-apps` | Go services built from sibling repositories, with migrations applied first |
| `make up-tools` | Kafka UI on `http://localhost:8085` |
| `make tunnel` | Temporary public HTTPS URL (Cloudflare quick tunnel) for testing on phones |

Stop the stack with `make down`. Containers never start automatically with Docker. `make reset` deletes
data, and `make clean` also removes locally built images.

## Layout

```
compose.yaml                 local stack (pinned images, profiles)
postgres/initdb/             first-start bootstrap: databases and roles
kafka/create-topics.sh       topic definitions
mosquitto/config/            broker config, ACL, credential generation
gateway/Caddyfile            routing table shared with deployment
```

## License

[MIT](LICENSE)
