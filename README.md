# platform-infrastructure

Shared infrastructure and documentation for the VeriTrace platform:

- **Local environment:** a Docker Compose stack with pinned versions of PostgreSQL 18 + TimescaleDB,
  Kafka (KRaft), Mosquitto, Redis, and a Caddy gateway.
- **Bootstrap:** per-service databases and least-privilege roles, Kafka topics, and MQTT credentials
  and ACLs.
- **Documentation:** architecture, domain rules, contracts, ADRs, roadmap, and guides in [`docs/`](docs/README.md).

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

Every host port can be changed in `.env`. Run `make help` for all targets, and see the
[development setup guide](docs/guides/development-setup.md) for the full workflow.

## Profiles

| Command | Adds |
| --- | --- |
| `make up-apps` | Go services built from sibling repositories, with migrations applied first |
| `make up-tools` | Kafka UI on `http://localhost:8085` |

## Layout

```
compose.yaml                 local stack (pinned images, profiles)
postgres/initdb/             first-start bootstrap: databases and roles
kafka/create-topics.sh       topic definitions
mosquitto/config/            broker config, ACL, credential generation
gateway/Caddyfile            routing table shared with deployment
docs/                        platform documentation
```

## License

[MIT](LICENSE)
